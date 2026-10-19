"""Review queue, fact history/approval, source registry and ingestion jobs (§5.10).

Review actions are append-only: versions are never mutated in value, only status,
reviewer and reason are recorded; every mutation writes a fact_review_event plus an
audit_event. The worker never fetches external content in MVP, so refresh jobs
finish honestly as ``partial`` with a sanitized explanation instead of a fake success.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import (
    AdmissionRequirement,
    AuditEvent,
    City,
    FactEvidence,
    FactRecord,
    FactReviewEvent,
    FactVersion,
    IngestionJob,
    IngestionJobItem,
    Program,
    ProgramFee,
    ProgramIntake,
    Scholarship,
    Source,
    SourceDocument,
    University,
    User,
)

REVIEWABLE_STATUSES = ("candidate", "in_review", "conflicted", "stale")
FACT_STATUSES = REVIEWABLE_STATUSES + ("verified", "estimated", "unavailable", "rejected", "superseded")
JOB_STATUSES = ("queued", "running", "succeeded", "partial", "failed", "cancelled")
JOB_TYPES = ("discover", "fetch", "parse", "normalize", "validate", "refresh")
# only sources whose policy permits automated fetching may be refreshed (rules.md)
REFRESHABLE_POLICIES = ("permitted_fetch", "licensed_api", "public_dataset")
SOURCE_TYPES = ("official_university", "government", "regulator", "statistical",
                "licensed_aggregator", "other")
USE_POLICIES = ("manual_reference", "permitted_fetch", "licensed_api", "public_dataset",
                "prohibited_automated_fetch", "review_required")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _check(value: str, allowed: tuple, field: str) -> str:
    if value not in allowed:
        raise ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       [{"field": field, "code": "invalid_choice",
                         "message": f"{field} must be one of {', '.join(allowed)}."}])
    return value


def _entity_label(db: Session, entity_type: str, entity_id: uuid.UUID | None) -> str | None:
    if entity_id is None:
        return None
    if entity_type in ("university", "program", "scholarship", "city"):
        row = db.get({"university": University, "program": Program,
                      "scholarship": Scholarship, "city": City}[entity_type], entity_id)
        return getattr(row, "canonical_name", None) or getattr(row, "name", None) if row else None
    parent = {"fee": ProgramFee, "requirement": AdmissionRequirement,
              "intake": ProgramIntake}.get(entity_type)
    if parent is not None:
        row = db.get(parent, entity_id)
        if row and row.program_id:
            program = db.get(Program, row.program_id)
            return program.canonical_name if program else None
    return None


# ---------------------------------------------------------------- review queue

def review_queue(db: Session, *, status: str | None = None, entity_type: str | None = None,
                 fact_key: str | None = None, page: int = 1, page_size: int = 20) -> dict:
    if status is not None:
        _check(status, FACT_STATUSES, "status")
        conds = [FactRecord.current_status == status]
    else:
        conds = [FactRecord.current_status.in_(REVIEWABLE_STATUSES)]
    if entity_type:
        conds.append(FactRecord.entity_type == entity_type)
    if fact_key:
        conds.append(FactRecord.fact_key == fact_key)

    total = db.scalar(select(func.count()).select_from(FactRecord).where(*conds)) or 0
    rows = db.scalars(select(FactRecord).where(*conds)
                      .order_by(FactRecord.updated_at.desc(), FactRecord.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    if not rows:
        return {"items": [], "page": page, "page_size": page_size,
                "total_items": total, "total_pages": (total + page_size - 1) // page_size}

    ids = [f.id for f in rows]
    version_counts = dict(db.execute(
        select(FactVersion.fact_record_id, func.count()).where(
            FactVersion.fact_record_id.in_(ids)).group_by(FactVersion.fact_record_id)).all())
    evidence_counts = dict(db.execute(
        select(FactVersion.fact_record_id, func.count())
        .select_from(FactEvidence).join(FactVersion, FactVersion.id == FactEvidence.fact_version_id)
        .where(FactVersion.fact_record_id.in_(ids)).group_by(FactVersion.fact_record_id)).all())
    latest: dict[uuid.UUID, FactReviewEvent] = {}
    for event in db.scalars(select(FactReviewEvent).where(
            FactReviewEvent.fact_record_id.in_(ids))
            .order_by(FactReviewEvent.created_at.desc(), FactReviewEvent.id)).all():
        latest.setdefault(event.fact_record_id, event)

    items = []
    for fact in rows:
        version = db.get(FactVersion, fact.current_version_id) if fact.current_version_id else None
        event = latest.get(fact.id)
        items.append({
            "fact_id": fact.id, "entity_type": fact.entity_type, "entity_id": fact.entity_id,
            "entity_label": _entity_label(db, fact.entity_type, fact.entity_id),
            "fact_key": fact.fact_key, "applicability_key": fact.applicability_key,
            "current_status": fact.current_status, "current_version_id": fact.current_version_id,
            "current_value": version.value_json if version else None,
            "version_count": version_counts.get(fact.id, 0),
            "evidence_count": evidence_counts.get(fact.id, 0),
            "last_review": ({"action": event.action, "reason": event.reason,
                             "reviewer_user_id": event.reviewer_user_id,
                             "created_at": event.created_at.isoformat()}
                            if event else None),
        })
    return {"items": items, "page": page, "page_size": page_size,
            "total_items": total, "total_pages": (total + page_size - 1) // page_size}


# ----------------------------------------------------------------- fact detail

def fact_detail(db: Session, fact_id: uuid.UUID) -> dict:
    fact = db.get(FactRecord, fact_id)
    if fact is None:
        raise ApiError(404, "NOT_FOUND", "Fact not found.")
    versions = db.scalars(select(FactVersion).where(FactVersion.fact_record_id == fact.id)
                          .order_by(FactVersion.version_number.desc())).all()
    evidence_by_version: dict[uuid.UUID, list] = {}
    if versions:
        pairs = db.execute(
            select(FactEvidence, SourceDocument)
            .join(SourceDocument, SourceDocument.id == FactEvidence.source_document_id)
            .where(FactEvidence.fact_version_id.in_([v.id for v in versions]))
            .order_by(FactEvidence.created_at)).all()
        for evidence, document in pairs:
            source = db.get(Source, document.source_id)
            evidence_by_version.setdefault(evidence.fact_version_id, []).append({
                "evidence_id": evidence.id, "supports_or_conflicts": evidence.supports_or_conflicts,
                "excerpt": evidence.evidence_excerpt, "locator": evidence.evidence_locator,
                "reviewer_note": evidence.reviewer_note,
                "source_document_id": document.id, "canonical_url": document.canonical_url,
                "retrieved_at": document.retrieved_at.isoformat(),
                "fetch_status": document.fetch_status,
                "source": ({"id": source.id, "name": source.name,
                            "authority_tier": source.authority_tier,
                            "allowed_use_policy": source.allowed_use_policy} if source else None),
            })
    events = db.scalars(select(FactReviewEvent).where(FactReviewEvent.fact_record_id == fact.id)
                        .order_by(FactReviewEvent.created_at.desc())).all()
    return {
        "fact_id": fact.id, "entity_type": fact.entity_type, "entity_id": fact.entity_id,
        "entity_label": _entity_label(db, fact.entity_type, fact.entity_id),
        "fact_key": fact.fact_key, "applicability_key": fact.applicability_key,
        "current_status": fact.current_status, "current_version_id": fact.current_version_id,
        "versions": [{
            "id": v.id, "version_number": v.version_number, "value": v.value_json,
            "normalized_value": v.normalized_value_json, "status": v.status,
            "effective_from": v.effective_from.isoformat() if v.effective_from else None,
            "effective_to": v.effective_to.isoformat() if v.effective_to else None,
            "applicable_intake_year": v.applicable_intake_year,
            "applicable_intake_term": v.applicable_intake_term,
            "extraction_method": v.extraction_method,
            "extraction_confidence": v.extraction_confidence,  # candidate signal, not truth
            "reviewed_by_user_id": v.reviewed_by_user_id,
            "reviewed_at": v.reviewed_at.isoformat() if v.reviewed_at else None,
            "review_reason": v.review_reason, "created_by_user_id": v.created_by_user_id,
            "created_at": v.created_at.isoformat(),
            "evidence": evidence_by_version.get(v.id, []),
        } for v in versions],
        "review_events": [{
            "id": e.id, "fact_version_id": e.fact_version_id, "action": e.action,
            "reason": e.reason, "reviewer_user_id": e.reviewer_user_id,
            "created_at": e.created_at.isoformat()} for e in events],
    }


# -------------------------------------------------------------- review actions

def _locked_fact(db: Session, fact_id: uuid.UUID) -> FactRecord:
    fact = db.execute(select(FactRecord).where(FactRecord.id == fact_id)
                      .with_for_update()).scalar_one_or_none()
    if fact is None:
        raise ApiError(404, "NOT_FOUND", "Fact not found.")
    return fact


def _target_version(db: Session, fact: FactRecord, version_id: uuid.UUID | None) -> FactVersion:
    if version_id is not None:
        version = db.get(FactVersion, version_id)
        if version is None or version.fact_record_id != fact.id:
            raise ApiError(404, "NOT_FOUND", "Version not found for this fact.")
        return version
    if fact.current_version_id is None:
        raise ApiError(409, "CONFLICT", "This fact has no current version to review.")
    return db.get(FactVersion, fact.current_version_id)


def _require_reason(reason: str | None, action: str) -> str:
    if not reason or not reason.strip():
        raise ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       [{"field": "reason", "code": "required",
                         "message": f"reason is required for {action}."}])
    return reason.strip()


def _audit(db: Session, user: User, action: str, entity_id: uuid.UUID,
           request_id: str | None, reason: str | None, before: dict, after: dict) -> None:
    db.add(AuditEvent(actor_user_id=user.id, actor_type="user", action=action,
                      entity_type="fact_record", entity_id=entity_id,
                      request_id=uuid.UUID(request_id) if request_id else None,
                      reason=reason, before_summary=before, after_summary=after))


def _review_event(db: Session, fact: FactRecord, version: FactVersion | None,
                  user: User, action: str, reason: str | None) -> FactReviewEvent:
    event = FactReviewEvent(fact_record_id=fact.id,
                            fact_version_id=version.id if version else None,
                            reviewer_user_id=user.id, action=action, reason=reason)
    db.add(event)
    return event


def approve_fact(db: Session, user: User, fact_id: uuid.UUID, version_id: uuid.UUID | None,
                 reason: str | None, request_id: str | None) -> dict:
    fact = _locked_fact(db, fact_id)
    version = _target_version(db, fact, version_id)
    if version.status == "verified":
        raise ApiError(409, "CONFLICT", "This version is already verified.")
    before = {"current_status": fact.current_status, "version_status": version.status}
    version.status = "verified"
    version.reviewed_by_user_id = user.id
    version.reviewed_at = _now()
    version.review_reason = reason.strip() if reason else None
    fact.current_version_id = version.id
    fact.current_status = "verified"
    _review_event(db, fact, version, user, "approve", version.review_reason)
    _audit(db, user, "fact_approved", fact.id, request_id, version.review_reason, before,
           {"current_status": fact.current_status, "version_status": version.status})
    db.flush()
    return {"fact_id": fact.id, "version_id": version.id, "action": "approve",
            "current_status": fact.current_status, "version_status": version.status,
            "reviewed_by_user_id": user.id}


def reject_fact(db: Session, user: User, fact_id: uuid.UUID, version_id: uuid.UUID | None,
                reason: str, request_id: str | None) -> dict:
    reason = _require_reason(reason, "reject")
    fact = _locked_fact(db, fact_id)
    version = _target_version(db, fact, version_id)
    if version.status == "rejected":
        raise ApiError(409, "CONFLICT", "This version is already rejected.")
    before = {"current_status": fact.current_status, "version_status": version.status}
    version.status = "rejected"
    version.reviewed_by_user_id = user.id
    version.reviewed_at = _now()
    version.review_reason = reason
    if fact.current_version_id == version.id:
        fact.current_status = "rejected"  # stays visible; value history is never erased
    _review_event(db, fact, version, user, "reject", reason)
    _audit(db, user, "fact_rejected", fact.id, request_id, reason, before,
           {"current_status": fact.current_status, "version_status": version.status})
    db.flush()
    return {"fact_id": fact.id, "version_id": version.id, "action": "reject",
            "current_status": fact.current_status, "version_status": version.status,
            "reviewed_by_user_id": user.id}


def request_evidence(db: Session, user: User, fact_id: uuid.UUID, reason: str,
                     request_id: str | None) -> dict:
    reason = _require_reason(reason, "request_evidence")
    fact = _locked_fact(db, fact_id)
    version = db.get(FactVersion, fact.current_version_id) if fact.current_version_id else None
    before = {"current_status": fact.current_status}
    fact.current_status = "in_review"
    _review_event(db, fact, version, user, "request_evidence", reason)
    _audit(db, user, "fact_evidence_requested", fact.id, request_id, reason, before,
           {"current_status": fact.current_status})
    db.flush()
    return {"fact_id": fact.id, "action": "request_evidence",
            "current_status": fact.current_status, "reviewed_by_user_id": user.id}


# -------------------------------------------------------------------- sources

def _source_out(source: Source) -> dict:
    return {
        "id": source.id, "name": source.name, "base_url": source.base_url,
        "source_type": source.source_type, "authority_tier": source.authority_tier,
        "owner_or_publisher": source.owner_or_publisher,
        "allowed_use_policy": source.allowed_use_policy, "terms_url": source.terms_url,
        "robots_policy_checked_at": (source.robots_policy_checked_at.isoformat()
                                     if source.robots_policy_checked_at else None),
        "rate_limit_notes": source.rate_limit_notes, "license_notes": source.license_notes,
        "refresh_interval_hours": source.refresh_interval_hours,
        "enabled": source.enabled, "metadata": source.metadata_json or {},
        "created_at": source.created_at.isoformat() if source.created_at else None,
        "updated_at": source.updated_at.isoformat() if source.updated_at else None,
    }


def list_sources(db: Session, *, enabled: bool | None = None,
                 page: int = 1, page_size: int = 20) -> dict:
    conds = []
    if enabled is not None:
        conds.append(Source.enabled.is_(enabled))
    total = db.scalar(select(func.count()).select_from(Source).where(*conds)) or 0
    rows = db.scalars(select(Source).where(*conds).order_by(Source.name, Source.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    items = []
    for source in rows:
        documents = db.scalar(select(func.count()).select_from(SourceDocument)
                              .where(SourceDocument.source_id == source.id)) or 0
        jobs = db.scalar(select(func.count()).select_from(IngestionJob)
                         .where(IngestionJob.source_id == source.id)) or 0
        items.append({**_source_out(source), "document_count": documents, "job_count": jobs})
    return {"items": items, "page": page, "page_size": page_size,
            "total_items": total, "total_pages": (total + page_size - 1) // page_size}


def create_source(db: Session, user: User, payload: dict, request_id: str | None) -> dict:
    base_url = str(payload["base_url"]).rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       [{"field": "base_url", "code": "invalid_url",
                         "message": "base_url must be an http(s) URL."}])
    _check(payload["source_type"], SOURCE_TYPES, "source_type")
    _check(payload["allowed_use_policy"], USE_POLICIES, "allowed_use_policy")
    source = Source(
        name=payload["name"], base_url=base_url, source_type=payload["source_type"],
        authority_tier=payload["authority_tier"],
        owner_or_publisher=payload.get("owner_or_publisher"),
        allowed_use_policy=payload["allowed_use_policy"], terms_url=payload.get("terms_url"),
        rate_limit_notes=payload.get("rate_limit_notes"),
        license_notes=payload.get("license_notes"),
        refresh_interval_hours=payload.get("refresh_interval_hours"),
        enabled=payload.get("enabled", True),
    )
    db.add(source)
    db.flush()
    db.add(AuditEvent(actor_user_id=user.id, actor_type="user", action="source_created",
                      entity_type="source", entity_id=source.id,
                      request_id=uuid.UUID(request_id) if request_id else None,
                      after_summary={"name": source.name, "base_url": source.base_url,
                                     "allowed_use_policy": source.allowed_use_policy}))
    db.flush()
    return _source_out(source)


def get_source(db: Session, source_id: uuid.UUID) -> dict:
    source = db.get(Source, source_id)
    if source is None:
        raise ApiError(404, "NOT_FOUND", "Source not found.")
    documents = db.scalars(select(SourceDocument).where(SourceDocument.source_id == source.id)
                           .order_by(SourceDocument.retrieved_at.desc()).limit(20)).all()
    jobs = db.scalars(select(IngestionJob).where(IngestionJob.source_id == source.id)
                      .order_by(IngestionJob.created_at.desc()).limit(10)).all()
    return {
        **_source_out(source),
        "documents": [{"id": d.id, "canonical_url": d.canonical_url, "title": d.title,
                       "document_type": d.document_type, "fetch_status": d.fetch_status,
                       "http_status": d.http_status,
                       "retrieved_at": d.retrieved_at.isoformat()} for d in documents],
        "recent_jobs": [_job_out(j) for j in jobs],
    }


_SOURCE_PATCHABLE = {
    # API field -> ORM attribute ("metadata" is a reserved SQLAlchemy name and is
    # mapped as metadata_json -> DB column "metadata")
    "name": "name", "owner_or_publisher": "owner_or_publisher", "terms_url": "terms_url",
    "rate_limit_notes": "rate_limit_notes", "license_notes": "license_notes",
    "refresh_interval_hours": "refresh_interval_hours", "enabled": "enabled",
    "authority_tier": "authority_tier", "metadata": "metadata_json",
}


def update_source(db: Session, user: User, source_id: uuid.UUID, payload: dict,
                  request_id: str | None) -> dict:
    source = db.get(Source, source_id)
    if source is None:
        raise ApiError(404, "NOT_FOUND", "Source not found.")
    unknown = [k for k in payload if k not in _SOURCE_PATCHABLE and payload[k] is not None]
    if unknown:
        raise ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       [{"field": unknown[0], "code": "not_patchable",
                         "message": f"{unknown[0]} cannot be updated after registration."}])
    before = {}
    for field, attr in _SOURCE_PATCHABLE.items():
        value = payload.get(field)
        if value is None:
            continue
        before[field] = getattr(source, attr)
        setattr(source, attr, value)
    if not before:
        raise ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       [{"field": "payload", "code": "empty",
                         "message": "Provide at least one field to update."}])
    db.add(AuditEvent(actor_user_id=user.id, actor_type="user", action="source_updated",
                      entity_type="source", entity_id=source.id,
                      request_id=uuid.UUID(request_id) if request_id else None,
                      before_summary=before,
                      after_summary={k: getattr(source, _SOURCE_PATCHABLE[k]) for k in before}))
    db.flush()
    return _source_out(source)


def enqueue_refresh(db: Session, user: User, source_id: uuid.UUID,
                    request_id: str | None) -> dict:
    source = db.get(Source, source_id)
    if source is None:
        raise ApiError(404, "NOT_FOUND", "Source not found.")
    return _enqueue(db, user, source, request_id)


def enqueue_refresh_by_key(db: Session, user: User, source_key: str,
                           request_id: str | None) -> dict:
    """Trigger ingestion by its stable registry key (country-agnostic)."""
    source = db.scalar(select(Source).where(
        Source.metadata_json["adapter_key"].astext == source_key))
    if source is None:
        raise ApiError(404, "NOT_FOUND",
                       f"No source is registered for key {source_key!r}. Run the CLI "
                       "'sources' command to see the registered connectors.")
    return _enqueue(db, user, source, request_id)


def _enqueue(db: Session, user: User, source: Source, request_id: str | None) -> dict:
    if source.allowed_use_policy not in REFRESHABLE_POLICIES:
        raise ApiError(403, "REFRESH_NOT_PERMITTED",
                       "This source's use policy does not permit automated refresh. "
                       "Update the policy only when terms/robots allow it.")
    if not source.enabled:
        raise ApiError(409, "CONFLICT", "This source is disabled.")
    existing = db.scalar(select(IngestionJob).where(
        IngestionJob.source_id == source.id, IngestionJob.job_type == "refresh",
        IngestionJob.status.in_(("queued", "running")))
        .order_by(IngestionJob.created_at).limit(1))
    if existing is not None:
        return {**_job_out(existing), "reused": True}  # idempotent enqueue
    job = IngestionJob(source_id=source.id, job_type="refresh", status="queued",
                       created_by_user_id=user.id)
    db.add(job)
    db.flush()
    db.add(AuditEvent(actor_user_id=user.id, actor_type="user", action="job_enqueued",
                      entity_type="ingestion_job", entity_id=job.id,
                      request_id=uuid.UUID(request_id) if request_id else None,
                      after_summary={"source_id": str(source.id), "job_type": "refresh"}))
    db.flush()
    return {**_job_out(job), "reused": False}


# ----------------------------------------------------------------------- jobs

def _job_out(job: IngestionJob) -> dict:
    return {
        "id": job.id, "source_id": job.source_id, "job_type": job.job_type,
        "status": job.status,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "records_seen": job.records_seen, "records_created": job.records_created,
        "records_updated": job.records_updated, "records_rejected": job.records_rejected,
        "records_unchanged": job.records_unchanged,
        "records_review_required": job.records_review_required,
        "checkpoint": job.checkpoint,
        "error_summary": job.error_summary, "worker_version": job.worker_version,
        "created_by_user_id": job.created_by_user_id,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


def list_jobs(db: Session, *, status: str | None = None, job_type: str | None = None,
              source_id: uuid.UUID | None = None, page: int = 1, page_size: int = 20) -> dict:
    if status:
        _check(status, JOB_STATUSES, "status")
    if job_type:
        _check(job_type, JOB_TYPES, "job_type")
    conds = []
    if status:
        conds.append(IngestionJob.status == status)
    if job_type:
        conds.append(IngestionJob.job_type == job_type)
    if source_id:
        conds.append(IngestionJob.source_id == source_id)
    total = db.scalar(select(func.count()).select_from(IngestionJob).where(*conds)) or 0
    rows = db.scalars(select(IngestionJob).where(*conds)
                      .order_by(IngestionJob.created_at.desc(), IngestionJob.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_job_out(j) for j in rows], "page": page, "page_size": page_size,
            "total_items": total, "total_pages": (total + page_size - 1) // page_size}


def get_job(db: Session, job_id: uuid.UUID) -> dict:
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise ApiError(404, "NOT_FOUND", "Job not found.")
    items = db.scalars(select(IngestionJobItem).where(IngestionJobItem.job_id == job.id)
                       .order_by(IngestionJobItem.created_at).limit(50)).all()
    return {
        **_job_out(job),
        # candidate payloads are intentionally excluded (privacy-safe, minimized output)
        "items": [{"id": i.id, "source_document_id": i.source_document_id,
                   "entity_type": i.entity_type, "external_key": i.external_key,
                   "status": i.status, "validation_errors": i.validation_errors,
                   "fact_record_id": i.fact_record_id} for i in items],
    }


def retry_job(db: Session, user: User, job_id: uuid.UUID, request_id: str | None) -> dict:
    job = db.execute(select(IngestionJob).where(IngestionJob.id == job_id)
                     .with_for_update()).scalar_one_or_none()
    if job is None:
        raise ApiError(404, "NOT_FOUND", "Job not found.")
    if job.status not in ("failed", "cancelled"):
        raise ApiError(409, "CONFLICT",
                       "Only failed or cancelled jobs can be retried.")
    before = {"status": job.status}
    job.status = "queued"
    job.started_at = None
    job.finished_at = None
    job.records_seen = job.records_created = job.records_updated = job.records_rejected = 0
    job.error_summary = None
    db.add(AuditEvent(actor_user_id=user.id, actor_type="user", action="job_retried",
                      entity_type="ingestion_job", entity_id=job.id,
                      request_id=uuid.UUID(request_id) if request_id else None,
                      before_summary=before, after_summary={"status": "queued"}))
    db.flush()
    return _job_out(job)


# -------------------------------------------------------------- audit events

def list_audit_events(db: Session, *, action: str | None = None,
                      actor_user_id: uuid.UUID | None = None,
                      entity_type: str | None = None, since: datetime | None = None,
                      page: int = 1, page_size: int = 20) -> dict:
    conds = []
    if action:
        conds.append(AuditEvent.action == action)
    if actor_user_id:
        conds.append(AuditEvent.actor_user_id == actor_user_id)
    if entity_type:
        conds.append(AuditEvent.entity_type == entity_type)
    if since:
        conds.append(AuditEvent.created_at >= since)
    total = db.scalar(select(func.count()).select_from(AuditEvent).where(*conds)) or 0
    rows = db.scalars(select(AuditEvent).where(*conds)
                      .order_by(AuditEvent.created_at.desc(), AuditEvent.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{
        "id": e.id, "actor_user_id": e.actor_user_id, "actor_type": e.actor_type,
        "action": e.action, "entity_type": e.entity_type, "entity_id": e.entity_id,
        "request_id": str(e.request_id) if e.request_id else None, "reason": e.reason,
        "before_summary": e.before_summary, "after_summary": e.after_summary,
        "created_at": e.created_at.isoformat()} for e in rows],
        "page": page, "page_size": page_size, "total_items": total,
        "total_pages": (total + page_size - 1) // page_size}
