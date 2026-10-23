"""End-to-end ingestion pipeline.

For each registered connector: check permission, create/claim the job, retrieve
source documents, parse to candidates, normalize, validate, resolve identity,
write entities and versioned facts with evidence, and finish the job with an
honest summary. Failures in one source never stop the others, retries are
bounded, and a whole run is transactional (a failed batch rolls back).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.ingestion import persist
from app.ingestion.adapters.base import RunContext, SourceAdapter
from app.ingestion.http import FetchError, Fetcher
from app.ingestion.persist import Counters
from app.ingestion.registry import FETCHABLE_POLICIES, all_specs, get_adapter, get_spec
from app.ingestion.types import AdapterBatch, SourceNotPermitted
from app.ingestion.validate import (
    institution_match_quality,
    validate_institution,
    validate_program,
)
from app.models import IngestionJob, IngestionJobItem, InstitutionIdentityReview, Source

logger = logging.getLogger("uni.ingestion")
WORKER_VERSION = "ingestion-worker-1"
USER_AGENT = ("UniShortlist/1.0 (university data ingestion; "
              "contact: set INGESTION_CONTACT env var)")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RunOptions:
    dry_run: bool = False
    max_records: int | None = None
    max_pages: int | None = None
    countries: list[str] | None = None
    offline: bool = False
    record_all_items: bool = False
    limit_pages_only: bool = False
    query: str | None = None


@dataclass
class RunSummary:
    source_key: str
    job_id: uuid.UUID | None = None
    status: str = "failed"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float = 0.0
    counters: Counters = None  # type: ignore[assignment]
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "source": self.source_key, "job_id": str(self.job_id) if self.job_id else None,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": round(self.duration_seconds, 2),
            "records": self.counters.as_dict() if self.counters else {},
            "validation_errors": (self.counters.validation_errors[:20]
                                  if self.counters else []),
            "http_failures": (self.counters.http_failures[:20] if self.counters else []),
            "entity_counts": ({name: getattr(self.counters, name) for name in (
                "institutions_seen", "institutions_created", "institutions_updated",
                "institutions_unchanged", "programs_seen", "programs_created",
                "programs_updated", "programs_unchanged", "programs_rejected",
                "programs_review_required") } if self.counters else {}),
            "fact_counts": ({name: getattr(self.counters, name) for name in (
                "created", "updated", "unchanged", "review", "conflicted")
                } if self.counters else {}),
            "quality_counts": ({"needs_review": self.counters.review,
                                "conflicted": self.counters.conflicted,
                                "rejected": self.counters.rejected,
                                "skipped": self.counters.skipped}
                               if self.counters else {}),
            "warnings": (self.counters.warnings[:20] if self.counters else []),
            "error": self.error,
        }


# ------------------------------------------------------------------ entrypoints

def run_source(source_key: str, options: RunOptions | None = None, *,
               db: Session | None = None, created_by: uuid.UUID | None = None,
               job_id: uuid.UUID | None = None) -> RunSummary:
    options = options or RunOptions()
    spec = get_spec(source_key)
    adapter = get_adapter(source_key)
    summary = RunSummary(source_key=source_key, counters=Counters())
    summary.started_at = _now()
    if spec is None:
        summary.error = f"unknown source key {source_key!r}"
        return summary
    if adapter is None:
        summary.error = (f"{source_key}: no adapter is registered "
                         f"(integration status: {spec.integration_status})")
        return summary
    if spec.requires_explicit_limit and options.max_records is None:
        summary.error = f"{source_key}: an explicit --limit is required for this source."
        return summary

    if options.max_records is not None and options.max_records <= 0:
        summary.error = "max_records must be positive."
        return summary
    owns_session = db is None
    session = db or SessionLocal()
    job = session.get(IngestionJob, job_id) if job_id is not None else None
    source = None
    try:
        source = persist.ensure_source(session, spec)
        if not source.enabled:
            raise SourceNotPermitted(
                f"{source_key}: source is disabled in the registry; enable it only when "
                "the licence and terms permit automated ingestion")
        if source.allowed_use_policy not in FETCHABLE_POLICIES:
            raise SourceNotPermitted(
                f"{source_key}: use policy {source.allowed_use_policy!r} does not permit "
                "automated retrieval")

        # A dry run is observational: it must not commit a durable running job
        # before the candidate writes are rolled back. Avoid creating/adopting
        # a persistent job entirely; the returned summary still contains the
        # bounded validation counters but intentionally has no job id.
        job = None if options.dry_run else _claim_job(session, job_id, source, created_by)
        if job is not None:
            job.checkpoint = {**(job.checkpoint or {}), "run_options": asdict(options)}
            summary.job_id = job.id
            job.status = "running"
            job.started_at = _now()
            job.worker_version = WORKER_VERSION
            session.flush()

        context = RunContext(
            fetcher=Fetcher(user_agent=_user_agent(), timeout=spec.timeout_seconds,
                            rps=spec.request_rps, max_workers=spec.max_workers),
            countries=options.countries, max_records=options.max_records,
            max_pages=options.max_pages or 10_000, dry_run=options.dry_run,
            offline=options.offline, query=options.query, checkpoint={})
        try:
            counters = _consume(session, source, adapter, context, options, job, counters=summary.counters)
        finally:
            context.fetcher.close()

        _finish_job(session, job, counters, status="succeeded")
        if not options.dry_run and not options.offline:
            persist.mark_source_health(session, source, ok=True)
        summary.status = "partial" if _has_partial_outcome(counters) else "succeeded"
        summary.counters = counters
        if options.dry_run:
            session.rollback()
            summary.status = "dry_run"
        else:
            session.commit()
    except SourceNotPermitted as exc:
        summary.error = str(exc)
        logger.warning("ingestion refused for %s: %s", source_key, exc)
        if options.dry_run:
            session.rollback()
        else:
            _fail_job(session, job, summary)
        if owns_session and not options.dry_run:
            session.commit()
    except Exception as exc:  # a broken source must not abort the other sources
        summary.error = f"{type(exc).__name__}: {exc}"
        logger.exception("ingestion failed for %s", source_key)
        session.rollback()
        if options.dry_run:
            # A dry run has no durable job to mark failed and must leave no
            # persistent state, including failure metadata or source health.
            pass
        else:
            if isinstance(exc, FetchError):
                source = session.get(Source, source.id) if source is not None else None
                if source is not None:
                    persist.record_failed_retrieval(
                        session, source, exc.url,
                        f"HTTP retrieval failed: {exc.reason}", http_status=exc.status,
                        attempt_count=exc.attempts)
            _fail_job(session, job, summary)
        if owns_session and not options.dry_run:
            session.commit()
    finally:
        summary.finished_at = _now()
        if summary.started_at:
            summary.duration_seconds = (summary.finished_at - summary.started_at).total_seconds()
        if owns_session:
            session.close()
    return summary


def run_all(options: RunOptions | None = None, *, only_enabled: bool = True) -> list[RunSummary]:
    """Run every registered connector; each is isolated in its own transaction."""
    keys = [k for k, spec in all_specs().items()
            if get_adapter(k) and (not only_enabled or spec.enabled)
            and (options and options.max_records is not None or not spec.requires_explicit_limit)]
    return [run_source(key, options) for key in keys]


def enqueue_due_refreshes(db: Session, *, now: datetime | None = None) -> list[IngestionJob]:
    """Queue a refresh for every enabled, fetchable source whose interval elapsed.

    Intervals are per source (``refresh_interval_hours``), so a source that only
    changes once a year is not refreshed as often as one with a daily feed.
    """
    now = now or _now()
    queued = []
    for spec in all_specs().values():
        if (not spec.enabled or spec.requires_explicit_limit
                or spec.allowed_use_policy not in FETCHABLE_POLICIES):
            continue
        source = db.scalar(select(Source).where(
            Source.metadata_json["adapter_key"].astext == spec.source_key))
        if source is None or not source.enabled:
            continue
        schedule = (source.metadata_json or {}).get("refresh_schedule") or {}
        if not schedule.get("approved") or not schedule.get("approval_reference"):
            continue
        limit = schedule.get("max_records")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            continue
        hours = source.refresh_interval_hours or spec.refresh_interval_hours
        if not hours:
            continue
        last = db.scalar(select(IngestionJob).where(
            IngestionJob.source_id == source.id,
            IngestionJob.status == "succeeded")
            .order_by(IngestionJob.finished_at.desc()).limit(1))
        last_at = getattr(last, "finished_at", None) or getattr(last, "started_at", None)
        if last is not None and last_at is not None:
            age_hours = (now - last_at).total_seconds() / 3600.0
            if age_hours < hours:
                continue
        existing = db.scalar(select(IngestionJob).where(
            IngestionJob.source_id == source.id, IngestionJob.status.in_(("queued", "running"))))
        if existing is not None:
            continue
        job = IngestionJob(source_id=source.id, job_type="refresh", status="queued",
                           checkpoint={"run_options": {"max_records": limit, "max_pages": 5}})
        db.add(job)
        queued.append(job)
    db.flush()
    return queued


# --------------------------------------------------------------------- internals

def _has_partial_outcome(counters: Counters) -> bool:
    """A run with rejected/reviewed items or source/batch warnings is not complete."""
    return bool(counters.rejected or counters.review or counters.conflicted
                or counters.http_failures or counters.warnings)

def _user_agent() -> str:
    import os
    contact = os.environ.get("INGESTION_CONTACT")
    base = "UniShortlist/1.0 (university data ingestion)"
    return f"{base}; +{contact}" if contact else base


def _claim_job(db: Session, job_id: uuid.UUID | None, source: Source,
               created_by: uuid.UUID | None) -> IngestionJob:
    """Adopt an already-queued job, or create a durable one for a direct run."""
    if job_id is not None:
        job = db.get(IngestionJob, job_id)
        if job is None:
            raise ValueError(f"ingestion job {job_id} does not exist")
        if (job.worker_version or '').startswith('ror-directory-'):
            raise ValueError('Directory jobs require their approved bulk import plan, not the source pipeline')
        if job.source_id != source.id or job.status not in ("queued", "running"):
            raise ValueError("ingestion job source or state does not match this run")
        return job
    job = IngestionJob(source_id=source.id, job_type="refresh", status="queued",
                       created_by_user_id=created_by, worker_version=WORKER_VERSION)
    db.add(job)
    db.flush()
    db.commit()  # the job row is durable before any external work starts
    return job


def _finish_job(db: Session, job: IngestionJob | None, counters: Counters,
                status: str = "succeeded") -> None:
    if job is None:
        return
    counters_dict = counters.as_dict()
    job.records_seen = counters.institutions_seen + counters.programs_seen
    job.records_created = counters.institutions_created + counters.programs_created
    job.records_updated = counters.institutions_updated + counters.programs_updated
    job.records_rejected = counters.rejected
    job.records_unchanged = counters.institutions_unchanged + counters.programs_unchanged
    job.records_review_required = counters_dict["review"]
    job.checkpoint = {**(job.checkpoint or {}), "documents": counters_dict["documents"],
                      "documents_unchanged": counters_dict["documents_unchanged"],
                      "fields": counters_dict["fields"],
                      "skipped": counters_dict["skipped"],
                      "entities": {name: getattr(counters, name) for name in (
                          "institutions_seen", "institutions_created", "institutions_updated",
                          "institutions_unchanged", "programs_seen", "programs_created",
                          "programs_updated", "programs_unchanged", "programs_rejected",
                          "programs_review_required")},
                      "facts": {"created": counters.created, "updated": counters.updated,
                                "unchanged": counters.unchanged, "review": counters.review,
                                "conflicted": counters.conflicted},
                      # Versioned details supplement, but do not redefine, the
                      # legacy aggregate IngestionJob counters above.
                      "metrics": {
                          "version": 2,
                          "institutions": {
                              "seen": counters.institutions_seen,
                              "created": counters.institutions_created,
                              "updated": counters.institutions_updated,
                              "unchanged": counters.institutions_unchanged,
                          },
                          "programs": {
                              "seen": counters.programs_seen,
                              "created": counters.programs_created,
                              "updated": counters.programs_updated,
                              "unchanged": counters.programs_unchanged,
                              "rejected": counters.programs_rejected,
                              "needs_review": counters.programs_review_required,
                          },
                          "facts": {
                              "created": counters.created,
                              "updated": counters.updated,
                              "unchanged": counters.unchanged,
                              "conflicted": counters.conflicted,
                          },
                          "documents": {
                              "created_or_changed": counters_dict["documents"],
                              "unchanged": counters_dict["documents_unchanged"],
                          },
                          "rejected": counters.rejected,
                          "conflicted": counters.conflicted,
                          "needs_review": counters.review,
                          "skipped": counters.skipped,
                          "fields_created": counters.fields,
                          "semantics": {
                              "legacy_records": "institutions_and_programs_combined",
                              "conflicted_is_subset_of_needs_review": True,
                              "program_rejections_are_subset_of_rejected": True,
                          },
                      }}
    job.status = status if status in ("succeeded", "partial") else "failed"
    if _has_partial_outcome(counters):
        job.status = "partial"
    job.finished_at = _now()
    details = [f"{key}={value}" for key, value in counters_dict.items()]
    if counters.validation_errors:
        details.append("validation_errors=" + "; ".join(
            f"{entry.get('external_key')}:{entry['errors'][0]['code']}"
            for entry in counters.validation_errors[:10] if entry.get("errors")))
    if counters.http_failures:
        details.append("http_failures=" + "; ".join(counters.http_failures[:10]))
    if counters.warnings:
        details.append("warnings=" + "; ".join(counters.warnings[:10]))
    job.error_summary = None if job.status == "succeeded" else " | ".join(details)


def _fail_job(db: Session, job: IngestionJob | None, summary: RunSummary) -> None:
    if job is None:
        return
    try:
        _finish_job(db, job, summary.counters, status="failed")
        job.status = "failed"
        job.finished_at = _now()
        job.error_summary = (summary.error or "unknown failure")[:2000]
        db.add(job)
        db.flush()
        source = db.get(Source, job.source_id) if job.source_id else None
        if source is not None:
            persist.mark_source_health(db, source, ok=False, error=job.error_summary)
    except Exception:  # pragma: no cover - never mask the original failure
        logger.exception("could not record job failure")


def _consume(db: Session, source: Source, adapter: SourceAdapter, context: RunContext,
             options: RunOptions, job: IngestionJob | None, *, counters: Counters | None = None) -> Counters:
    counters = counters if counters is not None else Counters()
    resolver = persist.InstitutionResolver(db)
    fields = persist.field_index(db)
    reference = {"countries": {}, "cities": {}, "evidence": [], "records": [], "facts": {}}
    try:
        for batch in adapter.iter_batches(context):
            batch_counters = Counters()
            # Keep the outer, uncommitted source registration alive across dry
            # pages; rolling back the whole session would orphan page two.
            batch_savepoint = db.begin_nested() if options.dry_run else None
            try:
                _persist_batch(db, source, batch, batch_counters, resolver, fields, options,
                               reference, job)
                db.flush()  # fact records + versions first (they reference each other)
                persist.finalize_records(db, reference["records"])
                db.flush()  # point each new record at its first version
                persist.add_evidence(db, reference["evidence"])
                db.flush()  # one write barrier per retrieved document, not per row
                if options.dry_run:
                    batch_savepoint.rollback()
                    resolver = persist.InstitutionResolver(db)
                    fields = persist.field_index(db)
                    reference = _reference_state()
                else:
                    db.commit()
                    reference["facts"].clear()
                counters.merge(batch_counters)
            except Exception as exc:  # one bad document cannot stop the source
                if batch_savepoint is not None:
                    batch_savepoint.rollback()
                else:
                    db.rollback()
                logger.exception("batch failed for %s", source.name)
                counters.warnings.append(f"batch failed and was rolled back: {exc}")
                counters.http_failures.append(f"batch:{type(exc).__name__}")
                resolver = persist.InstitutionResolver(db)
                fields = persist.field_index(db)
                reference = _reference_state()
    finally:
        if not options.dry_run:
            db.flush()
    return counters


def _reference_state() -> dict:
    return {"countries": {}, "cities": {}, "evidence": [], "records": [], "facts": {}}


def _persist_batch(db: Session, source: Source, batch: AdapterBatch, counters: Counters,
                   resolver, fields: dict[str, uuid.UUID], options: RunOptions,
                   reference: dict | None = None, job: IngestionJob | None = None) -> None:
    counters.warnings.extend(batch.warnings)
    counters.skipped += batch.skipped_records
    document = persist.store_document(db, source, batch.document, counters)
    documents = {id(batch.document): document}
    for entry in batch.fields:
        if fields.get(entry.key) is None:
            created = persist.ensure_field(db, entry.key, entry.display_name, entry.description)
            fields[entry.key] = created.id
            counters.fields += 1
    # Refresh the display-name aliases after source taxonomy entries are staged.
    # field_index omits non-unique labels, so a source label can only map when
    # exactly one controlled field has that normalized display name.
    fields.update(persist.field_index(db))
    for candidate in batch.institutions:
        counters.seen += 1
        counters.institutions_seen += 1
        counters.programs_seen += len(candidate.programs)
        issues = validate_institution(candidate)
        if issues:
            counters.rejected += 1
            counters.validation_errors.append(
                {"external_key": candidate.external_key, "name": candidate.name,
                 "errors": [i.as_dict() for i in issues]})
            _job_item(db, job, batch, candidate.external_key, "rejected",
                      {"errors": [i.as_dict() for i in issues]}, options)
            continue
        university, match = resolver.resolve(candidate, source.id)
        if candidate.require_existing and not university:
            counters.skipped += 1
            continue
        issues = institution_match_quality(candidate, match)
        if match in ("ambiguous_identifier", "conflicting_identifiers"):
            counters.review += 1
            if match == "conflicting_identifiers":
                counters.conflicted += 1
            counters.programs_review_required += len(candidate.programs)
            detail = {
                "identity_review": [{"code": match,
                                     "message": "Strong identifiers do not resolve to one institution."}],
                "candidate": _candidate_identity(candidate),
            }
            _job_item(db, job, batch, candidate.external_key, "processed", detail, options,
                      document.id)
            _queue_identity_review(db, source, document, candidate, None, detail)
            continue
        if issues:
            counters.review += 1
            counters.programs_review_required += len(candidate.programs)
            detail = {"identity_review": [i.as_dict() for i in issues],
                      "candidate": _candidate_identity(candidate),
                      "suggested_university_id": str(university) if university else None}
            _job_item(db, job, batch, candidate.external_key, "processed", detail, options,
                      document.id)
            _queue_identity_review(db, source, document, candidate, university, detail)
            continue
        university, action = persist.upsert_institution(db, candidate, resolver,
                                                  source=source, source_document=document,
                                                  country_cache=reference["countries"],
                                                  city_cache=reference["cities"])
        setattr(counters, f"institutions_{action}",
                getattr(counters, f"institutions_{action}") + 1)
        entity_is_new = action == "created"
        outcomes = persist.record_facts(db, entity_type="university",
                                        entity_id=university.id, source=source,
                                        document=document, facts=candidate.facts,
                                        counters=counters, entity_is_new=entity_is_new,
                                        evidence_queue=reference["evidence"], pending_records=reference["records"], memo=reference["facts"])
        if not entity_is_new:
            for fact, outcome in zip(candidate.facts, outcomes):
                if outcome == "review":
                    _job_item(db, job, batch, candidate.external_key, "processed",
                              {"fact": fact.fact_key, "outcome": outcome,
                               "reason": "another source published a different value"},
                              options)
        for program in candidate.programs:
            program_issues = validate_program(program)
            if program_issues:
                counters.rejected += 1
                counters.programs_rejected += 1
                counters.validation_errors.append(
                    {"external_key": program.external_key, "title": program.title,
                     "errors": [i.as_dict() for i in program_issues]})
                _job_item(db, job, batch, program.external_key, "rejected",
                          {"errors": [i.as_dict() for i in program_issues]}, options, document.id, entity_type="program")
                continue
            try:
                row, program_action = persist.upsert_program(
                    db, university, program, fields, source=source, source_document=document)
            except ValueError as exc:
                counters.review += 1
                counters.programs_review_required += 1
                if "conflicts" in str(exc).lower():
                    counters.conflicted += 1
                _job_item(db, job, batch, program.external_key, "processed",
                          {"program_identity_review": str(exc), "title": program.title,
                           "university_id": str(university.id)}, options, document.id, entity_type="program")
                continue
            setattr(counters, f"programs_{program_action}",
                    getattr(counters, f"programs_{program_action}") + 1)
            persist.record_facts(db, entity_type="program", entity_id=row.id,
                                 source=source, document=document, facts=program.facts,
                                 counters=counters,
                                 entity_is_new=program_action == "created",
                                 evidence_queue=reference["evidence"], pending_records=reference["records"], memo=reference["facts"])
            for supplement in program.documents:
                key = id(supplement.document)
                if key not in documents:
                    documents[key] = persist.store_document(db, source, supplement.document, counters)
                persist.record_facts(db, entity_type="program", entity_id=row.id,
                                     source=source, document=documents[key], facts=supplement.facts,
                                     counters=counters, entity_is_new=program_action == "created",
                                     evidence_queue=reference["evidence"], pending_records=reference["records"],
                                     memo=reference["facts"])
    if options.record_all_items:
        _job_item(db, job, batch, None, "processed",
                  {"batch": len(batch.institutions)}, options)


def _job_item(db: Session, job: IngestionJob | None, batch: AdapterBatch,
              external_key: str | None, status: str, payload: dict,
              options: RunOptions, source_document_id: uuid.UUID | None = None, entity_type: str = "university"
              ) -> IngestionJobItem | None:
    if job is None:
        return None
    key = external_key or f"batch-{stable(payload)}"
    item = db.scalar(select(IngestionJobItem).where(
        IngestionJobItem.job_id == job.id, IngestionJobItem.external_key == key))
    if item is None:
        item = IngestionJobItem(job_id=job.id, entity_type=entity_type, external_key=key,
                                source_document_id=source_document_id,
                                status=status, candidate_payload=payload,
                                validation_errors=payload.get("errors"))
        db.add(item)
    else:
        item.status = status
        item.source_document_id = source_document_id
        item.candidate_payload = payload
    db.flush()
    return item


def _queue_identity_review(db: Session, source: Source, document,
                           candidate, suggested_university_id, payload: dict) -> None:
    from app.services.archive import active_identity_clause

    row = db.scalar(select(InstitutionIdentityReview).where(
        active_identity_clause(db),
        InstitutionIdentityReview.source_id == source.id,
        InstitutionIdentityReview.external_key == candidate.external_key,
    ).with_for_update())
    if row is None:
        row = InstitutionIdentityReview(
            source_id=source.id, source_document_id=document.id,
            external_key=candidate.external_key, candidate_payload=payload,
            suggested_university_id=suggested_university_id, status="pending")
        db.add(row)
    elif row.status == "pending":
        row.source_document_id = document.id
        row.candidate_payload = payload
        row.suggested_university_id = suggested_university_id
    db.flush()


def stable(payload: dict) -> str:
    import hashlib
    from app.ingestion.normalize import stable_json
    return hashlib.sha256(stable_json(payload).encode()).hexdigest()[:16]


def _candidate_identity(candidate) -> dict:
    return {
        "external_key": candidate.external_key,
        "name": candidate.name,
        "country_code": candidate.country_code,
        "website": candidate.website,
        "identifiers": candidate.identifiers,
        "identifier_scopes": candidate.identifier_scopes,
        "identifier_campus_ids": candidate.identifier_campus_ids,
        "aliases": candidate.aliases,
        "city": candidate.city,
        "admin_region": candidate.admin_region,
        "program_candidates": [{"external_key": p.external_key, "title": p.title,
                                "discipline": p.discipline_name}
                               for p in candidate.programs[:100]],
        "program_candidate_count": len(candidate.programs),
    }
