"""Review queue, fact history/approval, source registry and ingestion jobs (§5.10).

Review actions are append-only: versions are never mutated in value, only status,
reviewer and reason are recorded; every mutation writes its review and audit events.
Permitted source refreshes run through the bounded ingestion pipeline.
"""
from __future__ import annotations

import uuid
import re
import json
from datetime import datetime, timezone
from datetime import timedelta

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
    Field,
    IngestionJob,
    IngestionJobItem,
    InstitutionIdentityReview,
    InstitutionIdentityReviewEvent,
    InstitutionIdentifier,
    InstitutionReview,
    InstitutionReviewEvent,
    Program,
    ProgramFee,
    ProgramIdentifier,
    ProgramIntake,
    Scholarship,
    Source,
    SourceDocument,
    SourceDocumentRetrieval,
    University,
    User,
)
from app.services.archive import active_identity_clause, record_context
from app.services.program_evidence import official_program_page, official_registry_page
from app.ingestion.normalize import normalize_url
from app.ingestion.persist import IDENTITY_NAMESPACES
from app.services.review_readiness import discovery_stage, program_package, program_semantics, supporting_evidence, title_key
from app.services.source_document_schema import (
    freshness_values,
    freshness_columns_available,
    retrieval_history_available,
    source_document_options,
)
from app.services.source_urls import classify_program_url

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


def _display_fact_value(value: object) -> dict:
    """Create a compact reviewer-friendly view while retaining the raw value."""
    def label(key: str) -> str:
        return key.replace("_", " ").strip().capitalize()

    def display(item: object) -> str:
        if item is None:
            return "Not provided"
        if isinstance(item, bool):
            return "Yes" if item else "No"
        if isinstance(item, (str, int, float)):
            return str(item)
        if isinstance(item, list):
            return ", ".join(display(part) for part in item) or "Not provided"
        return json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)

    if isinstance(value, dict):
        fields = [{"label": label(str(key)), "value": display(item)}
                  for key, item in value.items()]
        summary = " · ".join(f"{item['label']}: {item['value']}" for item in fields)
        return {"summary": summary or "Not provided", "fields": fields}
    return {"summary": display(value), "fields": []}


def _fact_entity_context(db: Session, entity_type: str, entity_id: uuid.UUID) -> dict | None:
    if entity_type == "university":
        university = db.get(University, entity_id)
        if university is None:
            return None
        return {"type": "university", "id": university.id, "name": university.canonical_name,
                "country_code": university.country_code,
                "official_website_url": university.official_website_url,
                "external_identifiers": university.external_identifiers or {},
                "is_demo": bool((university.external_identifiers or {}).get("demo_fixture"))}
    if entity_type == "program":
        program = db.get(Program, entity_id)
        if program is None:
            return None
        university = db.get(University, program.university_id)
        identifiers = db.scalars(select(ProgramIdentifier).where(
            ProgramIdentifier.program_id == program.id).order_by(
                ProgramIdentifier.source_key, ProgramIdentifier.external_key)).all()
        return {"type": "program", "id": program.id, "name": program.canonical_name,
                "degree_level": program.degree_level, "publication_status": program.publication_status,
                "official_program_url": program.official_program_url,
                "university": ({"id": university.id, "name": university.canonical_name,
                                "country_code": university.country_code,
                                "official_website_url": university.official_website_url}
                               if university else None),
                "source_identifiers": [{"source_key": i.source_key,
                                         "external_key": i.external_key,
                                         "claim_status": i.claim_status}
                                        for i in identifiers]}
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
            "display_value": _display_fact_value(version.value_json if version else None),
            "entity_context": _fact_entity_context(db, fact.entity_type, fact.entity_id),
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
            .options(*source_document_options(db))
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
                **freshness_values(db, document),
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
        "entity_context": _fact_entity_context(db, fact.entity_type, fact.entity_id),
        "fact_key": fact.fact_key, "applicability_key": fact.applicability_key,
        "current_status": fact.current_status, "current_version_id": fact.current_version_id,
        "versions": [{
            "id": v.id, "version_number": v.version_number, "value": v.value_json,
            "display_value": _display_fact_value(v.value_json),
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


def _require_publication_reason(reason: str | None, action: str) -> str:
    """Require a review-specific explanation while preserving its audit text."""
    normalized = " ".join((reason or "").split())
    words = re.findall(r"[a-z0-9]+", normalized.casefold())
    distinct_words = set(words)
    review_context = {
        "source", "evidence", "official", "identity", "document", "catalogue",
        "institution", "university", "record", "requirement", "page", "retrieval",
        "website", "site", "domain", "program", "programme", "course", "degree",
        "campus", "identifier", "location", "name", "url", "offering",
    }
    rationale_terms = {
        "confirm", "confirms", "confirmed", "support", "supports", "supported",
        "contradict", "contradicts", "contradicted", "match", "matches", "matched",
        "mismatch", "conflict", "conflicts", "conflicting", "missing", "changed", "failed", "requires", "needs", "because",
        "establishes", "indicates", "incomplete", "incorrect", "unavailable",
        "verify", "verifies", "verified", "verification", "cannot", "could", "unable",
        "not", "unresolved", "confirms", "confirmed", "shows", "supports",
    }
    if (len(normalized) < 30 or len(words) < 5 or len(distinct_words) < 4
            or not distinct_words.intersection(review_context)
            or not distinct_words.intersection(rationale_terms)):
        raise ApiError(
            422, "VALIDATION_ERROR",
            "The reviewer reason must describe the evidence reviewed and why it supports this decision.",
            [{"field": "reason", "code": "insufficient_detail",
              "message": ("Use at least 30 characters and five words; identify the source or "
                          "evidence considered and explain why it supports this decision. ")}],
        )
    return normalized


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
                 reason: str | None, request_id: str | None, *, description_summary: str | None = None) -> dict:
    fact = _locked_fact(db, fact_id)
    version = _target_version(db, fact, version_id)
    if version.status == "verified":
        raise ApiError(409, "CONFLICT", "This version is already verified.")
    if fact.entity_type == "program" and fact.fact_key == "program_description":
        reason = _require_reason(reason, "description verification")
        from app.services.program_descriptions import prepare_summary_version
        version = prepare_summary_version(db, user, fact, version, description_summary)
    elif description_summary is not None:
        raise ApiError(422, "VALIDATION_ERROR", "A description summary applies only to a programme description fact.")
    before = {"current_status": fact.current_status, "version_status": version.status}
    from app.services.fact_projection import apply_reviewed_fact
    projection = apply_reviewed_fact(db, fact, version)
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
            "projection_status": projection, "reviewed_by_user_id": user.id}


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


# ------------------------------------------------------ institution identities


def _identity_review_out(db: Session, review: InstitutionIdentityReview) -> dict:
    source = db.get(Source, review.source_id)
    suggested = (db.get(University, review.suggested_university_id)
                 if review.suggested_university_id else None)
    document = db.get(SourceDocument, review.source_document_id)
    linked_identifiers = []
    if suggested:
        linked_identifiers = [{"namespace": claim.namespace, "value": claim.identifier_value,
                               "scope": claim.scope, "source_key": claim.source_key,
                               "claim_status": claim.claim_status}
                              for claim in db.scalars(select(InstitutionIdentifier).where(
                                  InstitutionIdentifier.university_id == suggested.id,
                                  InstitutionIdentifier.claim_status == "accepted")
                                  .order_by(InstitutionIdentifier.namespace,
                                            InstitutionIdentifier.normalized_value)).all()]
    events = db.scalars(select(InstitutionIdentityReviewEvent).where(
        InstitutionIdentityReviewEvent.review_id == review.id)
        .order_by(InstitutionIdentityReviewEvent.created_at,
                   InstitutionIdentityReviewEvent.id)).all()
    return {
        "id": review.id, "status": review.status,
        "archive_context": record_context(db, "institution_identity_reviews", review.id),
        "source": {"id": source.id, "name": source.name,
                   "source_key": (source.metadata_json or {}).get("adapter_key"),
                   "owner_or_publisher": source.owner_or_publisher,
                   "allowed_use_policy": source.allowed_use_policy,
                   "license_notes": source.license_notes,
                   "terms_url": source.terms_url} if source else None,
        "external_key": review.external_key,
        "candidate": review.candidate_payload.get("candidate", {}),
        "identity_review": review.candidate_payload.get("identity_review", []),
        "suggested_university": {"id": suggested.id, "name": suggested.canonical_name,
                                  "country_code": suggested.country_code,
                                  "official_website_url": suggested.official_website_url,
                                  "external_identifiers": suggested.external_identifiers or {},
                                  "accepted_identifiers": linked_identifiers} if suggested else None,
        "resolved_university_id": review.resolved_university_id,
        "reviewed_by_user_id": review.reviewed_by_user_id,
        "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
        "review_reason": review.review_reason,
        "source_document": ({"title": document.title, "url": document.canonical_url,
                             "retrieved_at": document.retrieved_at.isoformat(),
                             "http_status": document.http_status,
                             "fetch_status": document.fetch_status,
                             "content_excerpt": (document.content_excerpt or "")[:2000],
                             "id": document.id} if document else None),
        "events": [{"id": event.id, "action": event.action,
                    "actor_user_id": event.actor_user_id, "reason": event.reason,
                    "before": event.before_summary, "after": event.after_summary,
                    "created_at": event.created_at.isoformat()} for event in events],
    }


def identity_review_queue(db: Session, *, status: str = "pending",
                          page: int = 1, page_size: int = 20) -> dict:
    _check(status, ("pending", "approved", "rejected", "deferred"), "status")
    query = select(InstitutionIdentityReview).where(
        InstitutionIdentityReview.status == status, active_identity_clause(db))
    total = db.scalar(select(func.count()).select_from(InstitutionIdentityReview).where(
        InstitutionIdentityReview.status == status, active_identity_clause(db))) or 0
    rows = db.scalars(query.order_by(InstitutionIdentityReview.created_at,
                                     InstitutionIdentityReview.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_identity_review_out(db, row) for row in rows],
            "page": page, "page_size": page_size, "total_items": total,
            "total_pages": (total + page_size - 1) // page_size}


def identity_review_detail(db: Session, review_id: uuid.UUID) -> dict:
    review = db.get(InstitutionIdentityReview, review_id)
    if review is None:
        raise ApiError(404, "NOT_FOUND", "Institution identity review not found.")
    result = _identity_review_out(db, review)
    return result


# -------------------------------------------------------- institution approval

def institution_review_queue(db: Session, *, status: str = "pending", stage: str = "all",
                             page: int = 1, page_size: int = 20) -> dict:
    _check(status, ("pending", "approved", "rejected", "deferred", "needs_evidence"), "status")
    _check(stage, ("all", "discovery", "evidence_collection", "ready_for_review"), "stage")
    rows = db.scalars(select(InstitutionReview).where(
        InstitutionReview.status == status, InstitutionReview.university_id.is_not(None))
        .order_by(InstitutionReview.created_at, InstitutionReview.id)).all()
    # An absent canonical website always blocks approval. For these institutions
    # the stage group depends only on whether any programmes exist; evidence for
    # off-page institutions need not be serialized to calculate exact counts.
    basic = {uid:(website,count) for uid,website,count in db.execute(
        select(University.id,University.official_website_url,func.count(Program.id))
        .outerjoin(Program,Program.university_id==University.id)
        .where(University.id.in_([r.university_id for r in rows]))
        .group_by(University.id,University.official_website_url))} if rows else {}
    summaries, groups = {}, {}
    counts = {"discovery": 0, "evidence_collection": 0, "ready_for_review": 0}
    for row in rows:
        website,program_count = basic.get(row.university_id,(None,0))
        if not website:
            group = 'discovery' if not program_count else 'evidence_collection'
        else:
            item = summaries[row.id] = _institution_review_out(db,row,detail=False)
            group = item['workflow_stage'] if item['workflow_stage'] in counts else 'evidence_collection'
        groups[row.id] = group
        counts[group] += 1
    matching = [row for row in rows if stage=='all' or groups[row.id]==stage]
    total = len(matching)
    items = [summaries.get(row.id) or _institution_review_out(db,row,detail=False)
             for row in matching[(page-1)*page_size:page*page_size]]
    return {"items": items,
            "stage_counts": counts, "page": page, "page_size": page_size,
            "total_items": total, "total_pages": (total + page_size - 1) // page_size}


def institution_review_detail(db: Session, university_id: uuid.UUID) -> dict:
    review = db.scalar(select(InstitutionReview).where(
        InstitutionReview.university_id == university_id))
    if review is None:
        raise ApiError(404, "NOT_FOUND", "Institution review not found.")
    return _institution_review_out(db, review, detail=True)


def _institution_review_out(db: Session, review: InstitutionReview, *, detail: bool) -> dict:
    from app.services.catalog import _page_context
    university = db.get(University, review.university_id)
    if university is None:
        raise ApiError(404, "NOT_FOUND", "Institution not found.")
    context = _institution_review_context(db, university)
    source_claims = db.execute(
        select(InstitutionIdentifier, Source, SourceDocument)
        .outerjoin(Source, Source.id == InstitutionIdentifier.source_id)
        .outerjoin(SourceDocument, SourceDocument.id == InstitutionIdentifier.source_document_id)
        .options(*source_document_options(db))
        .where(InstitutionIdentifier.university_id == university.id)
        .order_by(InstitutionIdentifier.source_key, InstitutionIdentifier.namespace,
                  InstitutionIdentifier.normalized_value)
    ).all()
    claims = [{
        "namespace": claim.namespace, "value": claim.identifier_value,
        "normalized_value": claim.normalized_value, "scope": claim.scope,
        "claim_status": claim.claim_status, "source_key": claim.source_key,
        "source_name": source.name if source else claim.source_key,
        "publisher": source.owner_or_publisher if source else None,
        "source_id": source.id if source else None,
        "allowed_use_policy": source.allowed_use_policy if source else None,
        "source_document": ({"id": document.id, "title": document.title,
                             "url": document.canonical_url,
                             "retrieved_at": document.retrieved_at.isoformat(),
                             "http_status": document.http_status,
                             "fetch_status": document.fetch_status}
                            if document else None),
    } for claim, source, document in source_claims]
    programs = db.execute(
        select(Program, ProgramIdentifier, Source, SourceDocument)
        .outerjoin(ProgramIdentifier, ProgramIdentifier.program_id == Program.id)
        .outerjoin(Source, Source.id == ProgramIdentifier.source_id)
        .outerjoin(SourceDocument, SourceDocument.id == ProgramIdentifier.source_document_id)
        .options(*source_document_options(db))
        .where(Program.university_id == university.id)
        .order_by(Program.canonical_name, Program.id, ProgramIdentifier.source_key,
                  ProgramIdentifier.external_key)
    ).all()
    by_program: dict[uuid.UUID, dict] = {}
    evidence_context = _page_context(db, list({row[0].id for row in programs}))
    source_links = {}
    names: dict[str, set[uuid.UUID]] = {}
    for program, identifier, source, document in programs:
        names.setdefault(" ".join(program.canonical_name.casefold().split()), set()).add(program.id)
        item = by_program.setdefault(program.id, {
            "id": program.id, "title": program.canonical_name,
            "degree_level": program.degree_level, "publication_status": program.publication_status,
            "is_active": program.is_active,
            "official_program_url": program.official_program_url,
            "duration_min_months": program.duration_min_months,
            "duration_max_months": program.duration_max_months,
            "delivery_language": program.delivery_language,
            "study_mode": program.study_mode,
            "source_identities": [],
        })
        if identifier:
            link_key = (identifier.source_id, identifier.source_key)
            if link_key not in source_links:
                source_links[link_key] = _source_institution_link(db, university.id, *link_key)
            item["source_identities"].append({
                "source_key": identifier.source_key, "external_key": identifier.external_key,
                "source_id": identifier.source_id,
                "institution_linked": source_links[link_key],
                "source_binding_valid": bool(source and document and document.source_id == source.id
                    and identifier.source_key == ((source.metadata_json or {}).get("adapter_key") or source.name)),
                "claim_status": identifier.claim_status,
                "source_name": source.name if source else identifier.source_key,
                "allowed_use_policy": source.allowed_use_policy if source else None,
                "source_document": ({"id": document.id, "title": document.title,
                                     "url": document.canonical_url,
                                     "retrieved_at": document.retrieved_at.isoformat(),
                                     "http_status": document.http_status,
                                     "fetch_status": document.fetch_status,
                                     **freshness_values(db, document)}
                                    if document else None),
            })
    for item in by_program.values():
        program = db.get(Program, item["id"])
        item["program_page_evidence"] = official_program_page(db, program, context=evidence_context, university=university)
        item["registry_page_evidence"] = official_registry_page(db, program, context=evidence_context)
        item["program_facts"] = _program_review_facts(db, program, context=evidence_context)
        item["identity_layers"] = program_semantics(item)
        item["review_readiness"] = program_package(item)
        item["evidence_backed"] = item["review_readiness"]["eligible"]
        item["missing_information"] = _program_missing_information(program, item["program_facts"])
        item["possible_same_title_program_ids"] = [str(other) for other in
            names[" ".join(item["title"].casefold().split())] if other != item["id"]]
    fact_rows = db.scalars(select(FactRecord).where(
        FactRecord.entity_type == "university", FactRecord.entity_id == university.id)
        .order_by(FactRecord.fact_key, FactRecord.applicability_key)).all()
    facts = []
    for fact in fact_rows:
        version = db.get(FactVersion, fact.current_version_id) if fact.current_version_id else None
        evidence_rows = db.execute(
            select(FactEvidence, SourceDocument, Source)
            .join(SourceDocument, SourceDocument.id == FactEvidence.source_document_id)
            .join(Source, Source.id == SourceDocument.source_id)
            .options(*source_document_options(db))
            .where(FactEvidence.fact_version_id == version.id)
            .order_by(FactEvidence.created_at, FactEvidence.id)
        ).all() if version else []
        facts.append({
            "id": fact.id, "fact_key": fact.fact_key,
            "applicability_key": fact.applicability_key, "status": fact.current_status,
            "value": version.value_json if version else None,
            "display_value": _display_fact_value(version.value_json if version else None),
            "version_count": db.scalar(select(func.count()).select_from(FactVersion).where(
                FactVersion.fact_record_id == fact.id)) or 0,
            "evidence": [{"source_name": source.name,
                          "source_id": source.id,
                          "publisher": source.owner_or_publisher,
                          "allowed_use_policy": source.allowed_use_policy,
                          "source_url": document.canonical_url,
                          "source_document_id": document.id,
                          "retrieved_at": document.retrieved_at.isoformat(),
                          "http_status": document.http_status,
                          "fetch_status": document.fetch_status,
                          "excerpt": ev.evidence_excerpt, "locator": ev.evidence_locator,
                          "supports_or_conflicts": ev.supports_or_conflicts,
                          **freshness_values(db, document)}
                         for ev, document, source in evidence_rows],
        })
    events = db.scalars(select(InstitutionReviewEvent).where(
        InstitutionReviewEvent.review_id == review.id)
        .order_by(InstitutionReviewEvent.created_at, InstitutionReviewEvent.id)).all()
    program_coverage = _institution_program_coverage(list(by_program.values()))
    approval_eligibility = _institution_approval_eligibility(
        university, context, claims, facts, program_coverage)
    summary = {
        "university_id": university.id, "name": university.canonical_name,
        "country_code": university.country_code,
        "official_website_url": university.official_website_url,
        "institution_type": context["institution_type"],
        "recognition_status": context["recognition_status"],
        "location": next((fact["display_value"]["summary"] for fact in facts
                          if fact["fact_key"] == "location"), None),
        "website_evidence_status": context["website_evidence_status"],
        "status": review.status, "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
        "reviewed_by_user_id": review.reviewed_by_user_id, "review_reason": review.review_reason,
        "identifier_count": len(claims), "fact_count": len(facts),
        "program_count": len(by_program), "source_keys": sorted({c["source_key"] for c in claims}),
        "is_demo": context["is_demo"], "program_coverage": program_coverage,
        "approval_eligibility": approval_eligibility,
        "workflow_stage": discovery_stage(approval_eligibility, program_coverage, context, claims),
    }
    if not detail:
        return summary
    return {
        **summary, "identifiers": context["identifiers"], "identifier_claims": claims,
        "website_evidence": context["website_evidence"], "facts": facts,
        "catalogue_sources": _catalogue_sources(list(by_program.values())),
        "source_discovery": _source_discovery(db, university, claims),
        "workflow": [
            {"step": "institution_discovered", "complete": True},
            {"step": "institution_identity_resolved", "complete": any(c["claim_status"] == "accepted" and c["namespace"] in IDENTITY_NAMESPACES for c in claims)},
            {"step": "masters_source_located", "complete": bool(_catalogue_sources(list(by_program.values())))},
            {"step": "catalogue_permissions_validated", "complete": any(c["allowed_use_policy"] in REFRESHABLE_POLICIES for c in _catalogue_sources(list(by_program.values())))},
            {"step": "named_masters_imported", "complete": bool(by_program)},
            {"step": "program_identities_linked", "complete": bool(by_program) and all(any(i["institution_linked"] for i in p["source_identities"]) for p in by_program.values())},
            {"step": "official_website_verified", "complete": context["website_evidence_status"] == "verified"},
            {"step": "program_evidence_available", "complete": program_coverage["evidence_backed_program_count"] > 0},
            {"step": "ready_for_human_review", "complete": approval_eligibility["eligible"]},
            {"step": "institution_approved", "complete": review.status == "approved"},
            {"step": "individual_programs_published", "complete": any(p["publication_status"] == "published" for p in by_program.values())},
        ],
        "programs": list(by_program.values()), "campuses": _campus_context(db, university.id),
        "events": [{"id": event.id, "action": event.action, "actor_user_id": event.actor_user_id,
                    "reason": event.reason, "before": event.before_summary,
                    "after": event.after_summary, "created_at": event.created_at.isoformat()}
                   for event in events],
        "warnings": _institution_review_warnings(context, claims, facts, list(by_program.values())),
    }


def _source_institution_link(db: Session, university_id, source_id, source_key) -> bool:
    direct = bool(db.scalar(select(InstitutionIdentifier.id).where(
        InstitutionIdentifier.university_id == university_id,
        InstitutionIdentifier.source_id == source_id,
        InstitutionIdentifier.source_key == source_key,
        InstitutionIdentifier.claim_status == "accepted").limit(1)) or db.scalar(
        select(InstitutionIdentityReview.id).where(
            InstitutionIdentityReview.source_id == source_id,
            InstitutionIdentityReview.resolved_university_id == university_id,
            InstitutionIdentityReview.status == "approved").limit(1)))
    if direct:
        return True
    rows = db.execute(select(FactVersion.value_json, FactEvidence, SourceDocument, Source).select_from(FactRecord)
        .join(FactVersion, FactVersion.id == FactRecord.current_version_id)
        .join(FactEvidence, FactEvidence.fact_version_id == FactVersion.id)
        .join(SourceDocument, SourceDocument.id == FactEvidence.source_document_id)
        .join(Source, Source.id == SourceDocument.source_id)
        .where(FactRecord.entity_type == "university", FactRecord.entity_id == university_id,
               FactRecord.fact_key == "source_identity_claim",
               FactRecord.current_status.in_(("candidate", "verified", "unverified")),
               FactVersion.status.in_(("candidate", "verified", "unverified")),
               FactEvidence.supports_or_conflicts == "supports", SourceDocument.source_id == source_id,
               SourceDocument.fetch_status == "fetched"))
    for value, evidence, document, source in rows:
        if (not isinstance(value, dict) or value.get("namespace") not in IDENTITY_NAMESPACES
                or not supporting_evidence({"allowed_use_policy": source.allowed_use_policy,
                    "fetch_status": document.fetch_status, "http_status": document.http_status,
                    "supports_or_conflicts": evidence.supports_or_conflicts,
                    "excerpt": evidence.evidence_excerpt, "locator": evidence.evidence_locator})):
            continue
        if db.scalar(select(InstitutionIdentifier.id).where(
            InstitutionIdentifier.university_id == university_id,
            InstitutionIdentifier.namespace == value["namespace"],
            InstitutionIdentifier.normalized_value == value.get("identifier", "").strip().casefold(),
            InstitutionIdentifier.scope == value.get("scope"),
            InstitutionIdentifier.claim_status == "accepted").limit(1)):
            return True
    return False


def _catalogue_sources(programs: list[dict]) -> list[dict]:
    documents = {}
    for program in programs:
        for identity in program["source_identities"]:
            document = identity["source_document"]
            if document:
                documents.setdefault(document["id"], {
                    **document, "source_key": identity["source_key"],
                    "source_name": identity["source_name"],
                    "allowed_use_policy": identity["allowed_use_policy"],
                    "institution_linked": identity["institution_linked"],
                })
    return list(documents.values())


def _source_discovery(db: Session, university: University, claims: list) -> list[dict]:
    from app.ingestion.registry import all_specs
    identity_keys = {"fr_monmaster": "uai", "duo_rio_masters": "rio_provider_id"}
    results = []
    for key, spec in all_specs().items():
        if spec.country_scope != university.country_code or not any(
                "master" in item or "program" in item for item in spec.supported_data):
            continue
        namespace = identity_keys.get(key)
        claim = next((c for c in claims if c["namespace"] == namespace and c["claim_status"] == "accepted"), None)
        # Source-scoped publisher links can be explicitly reconciled without
        # being authoritative institution IDs. Use the same link check as the
        # imported programmes; institution approval still requires its own ID.
        linked = any(c["source_key"] == key and c["source_id"]
                     and _source_institution_link(db, university.id, c["source_id"], key)
                     for c in claims)
        results.append({"source_key": key, "name": spec.name, "terms_url": spec.terms_url,
                        "allowed_use_policy": spec.allowed_use_policy,
                        "connection_status": spec.integration_status,
                        "requires_identity": namespace, "matching_identifier": claim["value"] if claim else None,
                        "status": "targetable" if claim or linked else "identity_mapping_required",
                        "message": ("Source identity is already linked to this institution; programme evidence and institution approval are reviewed separately."
                                    if linked else "Potential source for this country; programme coverage must be retrieved and matched.")})
    return results


def _program_missing_information(program: Program, facts: list[dict]) -> list[str]:
    missing = []
    keys = {fact["fact_key"] for fact in facts if fact["status"] not in ("rejected", "unavailable", "superseded")}
    for present, label in (
        (program.field_id is not None, "Academic field is not mapped."),
        (program.duration_min_months is not None, "Duration is unknown."),
        (bool(program.delivery_language), "Teaching language is unknown."),
        (bool(keys & {"tuition", "tuition_fee"}), "Tuition is unknown."),
        (bool(keys & {"admission_requirement", "admission_requirements"}), "Admissions requirements are unknown."),
        (bool(keys & {"application_deadline", "deadline"}), "Application deadlines are unknown."),
    ):
        if not present:
            missing.append(label)
    return missing


def _institution_program_coverage(programs: list[dict]) -> dict:
    if not programs:
        return {
            "status": "availability_not_established", "program_count": 0,
            "evidence_backed_program_count": 0,
            "message": "No named Master's programme records are associated with this institution. "
                       "A directory-level graduate offering flag does not establish course availability.",
        }
    evidence_backed = sum(bool(program["evidence_backed"]) for program in programs)
    if evidence_backed == len(programs):
        status = "catalogue_available_and_imported"
        message = "Associated Master's candidates have source identifiers and programme-row evidence."
    else:
        status = "catalogue_imported_needs_evidence"
        message = "Some associated program records lack sufficient source identity or row evidence."
    return {"status": status, "program_count": len(programs),
            "evidence_backed_program_count": evidence_backed, "message": message,
            "historical_program_count": sum(p["review_readiness"]["applicability"] == "historical" for p in programs),
            "verified_program_page_count": sum(p["program_page_evidence"]["status"] == "verified" for p in programs)}


def _institution_approval_eligibility(university: University, context: dict,
                                      claims: list, facts: list,
                                      program_coverage: dict) -> dict:
    blockers = []
    if not any(claim["claim_status"] == "accepted" and claim["namespace"] in IDENTITY_NAMESPACES
               for claim in claims):
        blockers.append("An accepted authoritative institution identifier is required.")
    if not any(fact["fact_key"] == "official_name"
               and fact["status"] in ("candidate", "verified", "unverified")
               and any(supporting_evidence(evidence) for evidence in fact["evidence"])
               for fact in facts):
        blockers.append("Source evidence for the official institution name is required.")
    if not university.official_website_url:
        blockers.append("An official university website URL has not been established.")
    elif context["website_evidence_status"] != "verified":
        blockers.append("The official university website and its evidence must be verified first.")
    if program_coverage["status"] != "catalogue_available_and_imported":
        blockers.append(program_coverage["message"])
    return {"eligible": not blockers, "blockers": blockers}


def _campus_context(db: Session, university_id: uuid.UUID) -> list[dict]:
    from app.models import Campus
    rows = db.scalars(select(Campus).where(Campus.university_id == university_id)
                      .order_by(Campus.name, Campus.id)).all()
    return [{"id": row.id, "name": row.name, "city_id": row.city_id,
             "address_public": row.address_public} for row in rows]


def _institution_review_warnings(context: dict, claims: list, facts: list, programs: list) -> list[str]:
    warnings = []
    if not any(c["claim_status"] == "accepted" for c in claims):
        warnings.append("No accepted authoritative institution identifier is recorded.")
    if not context["official_website_url"]:
        warnings.append("Official university website is unresolved.")
    elif context["website_evidence_status"] != "verified":
        warnings.append("Stored university website has not been fact-verified.")
    if not any(f["fact_key"] == "official_name" and f["evidence"] for f in facts):
        warnings.append("No source evidence is attached to an official-name fact.")
    for program in programs:
        if program["possible_same_title_program_ids"]:
            warnings.append(f"Similar-title programs need identity comparison: {program['title']}.")
        if not program["source_identities"]:
            warnings.append(f"Program has no source identity: {program['title']}.")
        if program["program_page_evidence"]["status"] != "verified":
            warnings.append(f"Program page is unresolved: {program['title']}.")
    return sorted(set(warnings))


def decide_institution_review(db: Session, user: User, university_id: uuid.UUID,
                              action: str, reason: str,
                              request_id: str | None = None) -> dict:
    action = _check(action, ("approve", "reject", "defer", "needs_evidence"), "action")
    reason = _require_publication_reason(reason, action)
    review = db.scalar(select(InstitutionReview).where(
        InstitutionReview.university_id == university_id).with_for_update())
    if review is None:
        raise ApiError(404, "NOT_FOUND", "Institution review not found.")
    if review.status in ("approved", "rejected"):
        raise ApiError(409, "CONFLICT", "This institution review is already final.")
    university = db.get(University, university_id)
    if university is None:
        raise ApiError(404, "NOT_FOUND", "Institution not found.")
    if action == "approve":
        payload = _institution_review_out(db, review, detail=True)
        eligibility = payload["approval_eligibility"]
        if not eligibility["eligible"]:
            raise ApiError(409, "INSTITUTION_REVIEW_REQUIRED",
                           "This institution is not yet eligible for approval.",
                           [{"field": "approval", "code": "evidence_required",
                             "message": blocker} for blocker in eligibility["blockers"]])
    before = {"status": review.status, "reviewed_at": review.reviewed_at.isoformat()
              if review.reviewed_at else None}
    status = {"approve": "approved", "reject": "rejected", "defer": "deferred",
              "needs_evidence": "needs_evidence"}[action]
    review.status = status
    review.reviewed_by_user_id = user.id
    review.reviewed_at = _now()
    review.review_reason = reason
    after = {"status": status, "reviewed_by_user_id": str(user.id),
             "reviewed_at": review.reviewed_at.isoformat()}
    db.add(InstitutionReviewEvent(review_id=review.id, actor_user_id=user.id,
                                  action=action, reason=reason,
                                  before_summary=before, after_summary=after))
    db.add(AuditEvent(actor_user_id=user.id, actor_type="user",
                      action=f"institution_{action}", entity_type="university",
                      entity_id=university.id,
                      request_id=uuid.UUID(request_id) if request_id else None,
                      reason=reason, before_summary=before, after_summary=after))
    db.flush()
    return {"university_id": university.id, "status": review.status,
            "reviewed_by_user_id": user.id, "reviewed_at": review.reviewed_at.isoformat()}


def decide_identity_review(db: Session, user: User, review_id: uuid.UUID, action: str,
                           reason: str, request_id: str | None,
                           university_id: uuid.UUID | None = None) -> dict:
    action = _check(action, ("approve_link", "reject", "defer"), "action")
    reason = _require_reason(reason, action)
    review = db.scalar(select(InstitutionIdentityReview).where(
        InstitutionIdentityReview.id == review_id).with_for_update())
    if review is None:
        raise ApiError(404, "NOT_FOUND", "Institution identity review not found.")
    if record_context(db, "institution_identity_reviews", review.id):
        raise ApiError(409, "CONFLICT", "This source identity review belongs to an immutable catalogue archive.")
    if review.status != "pending":
        raise ApiError(409, "CONFLICT", "This identity review has already been decided.")

    target = None
    if action == "approve_link":
        if university_id is None:
            raise ApiError(422, "VALIDATION_ERROR", "A university_id is required to approve a link.")
        target = db.get(University, university_id)
        if target is None:
            raise ApiError(404, "NOT_FOUND", "University not found.")
        if (target.external_identifiers or {}).get("demo_fixture"):
            raise ApiError(409, "IDENTITY_CONFLICT",
                           "Synthetic demo fixtures cannot receive real source identities.")
        candidate = review.candidate_payload.get("candidate", {})
        if candidate.get("country_code") and candidate["country_code"] != target.country_code:
            raise ApiError(409, "IDENTITY_CONFLICT", "Candidate and university country codes differ.")
        source = db.get(Source, review.source_id)
        source_key = (source.metadata_json or {}).get("adapter_key") or source.name
        document = db.get(SourceDocument, review.source_document_id)
        for namespace, raw_value in (candidate.get("identifiers") or {}).items():
            normalized = str(raw_value).strip().casefold()
            if not normalized:
                continue
            namespace = namespace.strip().lower()
            scope = (candidate.get("identifier_scopes") or {}).get(
                namespace, "reporting_unit" if namespace == "ipeds_unitid" else "institution")
            if namespace in IDENTITY_NAMESPACES and scope != "campus":
                conflict = db.scalar(select(InstitutionIdentifier.university_id).where(
                    InstitutionIdentifier.namespace == namespace,
                    InstitutionIdentifier.normalized_value == normalized,
                    InstitutionIdentifier.scope == scope,
                    InstitutionIdentifier.claim_status == "accepted",
                    InstitutionIdentifier.university_id != target.id).limit(1))
                if conflict:
                    raise ApiError(409, "IDENTITY_CONFLICT",
                                   "An authoritative identifier is already claimed by another university.")
            existing = db.scalar(select(InstitutionIdentifier.id).where(
                InstitutionIdentifier.source_key == source_key,
                InstitutionIdentifier.namespace == namespace,
                InstitutionIdentifier.normalized_value == normalized,
                InstitutionIdentifier.scope == scope,
                InstitutionIdentifier.university_id == target.id))
            if existing is None:
                db.add(InstitutionIdentifier(
                    university_id=target.id, source_id=source.id,
                    source_document_id=document.id, source_key=source_key,
                    namespace=namespace, identifier_value=str(raw_value).strip(),
                    normalized_value=normalized, scope=scope,
                    campus_id=(uuid.UUID((candidate.get("identifier_campus_ids") or {})[namespace])
                               if (candidate.get("identifier_campus_ids") or {}).get(namespace) else None),
                    claim_status="accepted" if namespace in IDENTITY_NAMESPACES else "pending_review"))
        review.status = "approved"
        review.resolved_university_id = target.id
    else:
        review.status = "rejected" if action == "reject" else "deferred"
    before = {"status": "pending", "resolved_university_id": None}
    review.reviewed_by_user_id = user.id
    review.reviewed_at = _now()
    review.review_reason = reason
    after = {"status": review.status,
             "resolved_university_id": str(review.resolved_university_id)
             if review.resolved_university_id else None}
    db.add(InstitutionIdentityReviewEvent(
        review_id=review.id, actor_user_id=user.id, action=action, reason=reason,
        before_summary=before, after_summary=after))
    db.add(AuditEvent(actor_user_id=user.id, actor_type="user",
                      action=f"institution_identity_{action}",
                      entity_type="institution_identity_review", entity_id=review.id,
                      request_id=uuid.UUID(request_id) if request_id else None,
                      reason=reason, before_summary=before, after_summary=after))
    db.flush()
    return {"review_id": review.id, "action": action, "status": review.status,
            "resolved_university_id": review.resolved_university_id}


# ---------------------------------------------------------- program publication

def _program_review_facts(db: Session, program: Program, *, context=None) -> list[dict]:
    entries = context['program_facts'].get(program.id, {}) if context is not None else None
    records = (sorted((e['record'] for e in entries.values()), key=lambda r: (r.fact_key,r.applicability_key))
               if entries is not None else db.scalars(select(FactRecord).where(
        FactRecord.entity_type == "program", FactRecord.entity_id == program.id)
        .order_by(FactRecord.fact_key, FactRecord.applicability_key)).all())
    result = []
    for record in records:
        version = (entries[record.id]['version'] if entries is not None else
                   db.get(FactVersion, record.current_version_id) if record.current_version_id else None)
        evidence_rows = (sorted(entries[record.id]['evidence'],key=lambda r:(r[0].created_at,str(r[0].id)))
                         if entries is not None else db.execute(
            select(FactEvidence, SourceDocument, Source)
            .join(SourceDocument, SourceDocument.id == FactEvidence.source_document_id)
            .join(Source, Source.id == SourceDocument.source_id)
            .options(*source_document_options(db))
            .where(FactEvidence.fact_version_id == version.id)
            .order_by(FactEvidence.created_at, FactEvidence.id)
        ).all() if version else [])
        result.append({
            "fact_id": record.id, "fact_key": record.fact_key, "applicability_key": record.applicability_key,
            "status": record.current_status,
            "value": version.value_json if version else None,
            "display_value": _display_fact_value(version.value_json if version else None),
            "applicable_intake_year": version.applicable_intake_year if version else None,
            "applicable_intake_term": version.applicable_intake_term if version else None,
            "effective_from": version.effective_from.isoformat() if version and version.effective_from else None,
            "effective_to": version.effective_to.isoformat() if version and version.effective_to else None,
            "evidence": [{"source_name": source.name,
                          "source_id": source.id,
                          "publisher": source.owner_or_publisher,
                          "allowed_use_policy": source.allowed_use_policy,
                          "source_url": doc.canonical_url,
                          "source_document_id": doc.id,
                          "retrieved_at": doc.retrieved_at.isoformat(),
                          **freshness_values(db, doc),
                          "http_status": doc.http_status, "fetch_status": doc.fetch_status,
                          "excerpt": ev.evidence_excerpt, "locator": ev.evidence_locator,
                          "supports_or_conflicts": ev.supports_or_conflicts}
                         for ev, doc, source in evidence_rows],
        })
    return result


def _institution_review_context(db: Session, university: University | None) -> dict | None:
    if university is None:
        return None
    identifiers = db.scalars(select(InstitutionIdentifier).where(
        InstitutionIdentifier.university_id == university.id).order_by(
            InstitutionIdentifier.namespace, InstitutionIdentifier.normalized_value)).all()
    website_fact = db.scalar(select(FactRecord).where(
        FactRecord.entity_type == "university", FactRecord.entity_id == university.id,
        FactRecord.fact_key == "official_website_url").limit(1))
    website_evidence = []
    if website_fact and website_fact.current_version_id:
        website_evidence = [{"url": doc.canonical_url, "title": doc.title,
                             "source_name": source.name,
                             "publisher": source.owner_or_publisher,
                             "allowed_use_policy": source.allowed_use_policy,
                             "retrieved_at": doc.retrieved_at.isoformat(),
                             **freshness_values(db, doc),
                             "excerpt": ev.evidence_excerpt, "locator": ev.evidence_locator,
                             "status": website_fact.current_status,
                             "fetch_status": doc.fetch_status, "http_status": doc.http_status,
                             "supports_or_conflicts": ev.supports_or_conflicts}
            for ev, doc, source in db.execute(
                select(FactEvidence, SourceDocument, Source)
                .join(SourceDocument, SourceDocument.id == FactEvidence.source_document_id)
                .join(Source, Source.id == SourceDocument.source_id)
                .options(*source_document_options(db))
                .where(FactEvidence.fact_version_id == website_fact.current_version_id)
                .order_by(FactEvidence.created_at, FactEvidence.id)).all()]
    website_version = db.get(FactVersion, website_fact.current_version_id) if website_fact and website_fact.current_version_id else None
    website_verified = bool(website_fact and website_fact.current_status == "verified"
        and website_version and website_version.status == "verified"
        and normalize_url((website_version.value_json or {}).get("url")) == normalize_url(university.official_website_url)
        and university.official_website_url and any(supporting_evidence(e) for e in website_evidence))
    return {"id": university.id, "name": university.canonical_name,
            "country_code": university.country_code,
            "official_website_url": university.official_website_url,
            "institution_type": getattr(university.institution_type, "value", university.institution_type),
            "recognition_status": getattr(university.recognition_status, "value", university.recognition_status),
            "is_demo": bool((university.external_identifiers or {}).get("demo_fixture")),
            "identifiers": university.external_identifiers or {},
            "identifier_claims": [{"namespace": row.namespace, "value": row.identifier_value,
                                   "scope": row.scope, "source_key": row.source_key,
                                   "claim_status": row.claim_status,
                                   "source_document_id": row.source_document_id}
                                  for row in identifiers],
            "website_evidence": website_evidence,
            "website_evidence_status": ("verified" if website_verified else
                                        "candidate" if website_fact else "unavailable")}


def program_publication_queue(db: Session, *, status: str = "candidate",
                              page: int = 1, page_size: int = 20) -> dict:
    _check(status, ("candidate", "published", "hidden"), "status")
    cond = Program.publication_status == status
    total = db.scalar(select(func.count()).select_from(Program).where(cond)) or 0
    rows = db.scalars(select(Program).where(cond).order_by(
        Program.created_at, Program.id).offset((page - 1) * page_size).limit(page_size)).all()
    items = []
    for program in rows:
        university = db.get(University, program.university_id)
        field = db.get(Field, program.field_id) if program.field_id else None
        identifiers = db.scalars(select(ProgramIdentifier).where(
            ProgramIdentifier.program_id == program.id).order_by(ProgramIdentifier.source_key,
                                                                 ProgramIdentifier.external_key)).all()
        provenance = []
        for identifier in identifiers:
            document = db.get(SourceDocument, identifier.source_document_id)
            source = db.get(Source, identifier.source_id)
            provenance.append({
                "source_key": identifier.source_key, "external_key": identifier.external_key,
                "claim_status": identifier.claim_status,
                "source": ({"id": source.id, "name": source.name,
                            "allowed_use_policy": source.allowed_use_policy,
                            "authority_tier": source.authority_tier} if source else None),
                "document": ({"id": document.id, "title": document.title,
                              "url": document.canonical_url,
                              "retrieved_at": document.retrieved_at.isoformat(),
                              "http_status": document.http_status,
                              "fetch_status": document.fetch_status} if document else None),
            })
        can_publish, publication_blocker = _publication_evidence(db, program)
        page_evidence = official_program_page(db, program)
        facts = _program_review_facts(db, program)
        missing = []
        if field is None:
            missing.append("academic field not mapped")
        if program.duration_min_months is None and program.duration_max_months is None:
            missing.append("duration unavailable")
        if not program.delivery_language:
            missing.append("teaching language unavailable")
        fact_keys = {item["fact_key"] for item in facts}
        if not fact_keys.intersection({"admission_requirement", "admission_requirements"}):
            missing.append("admission requirements unavailable")
        if not fact_keys.intersection({"tuition", "tuition_fee"}):
            missing.append("tuition unavailable")
        if not fact_keys.intersection({"application_deadline", "deadline"}):
            missing.append("application deadline unavailable")
        publication_events = db.scalars(select(AuditEvent).where(
            AuditEvent.entity_type == "program", AuditEvent.entity_id == program.id,
            AuditEvent.action.in_(("program_published", "program_unpublished")))
            .order_by(AuditEvent.created_at, AuditEvent.id)).all()
        items.append({
            "id": program.id, "name": program.canonical_name,
            "degree_level": program.degree_level, "country_code": program.country_code,
            "official_program_url": program.official_program_url,
            "official_program_url_classification": classify_program_url(
                program.official_program_url,
                verified=page_evidence["status"] == "verified",
                demo_fixture=bool((university.external_identifiers or {}).get("demo_fixture"))),
            "publication_status": program.publication_status,
            "published_at": program.published_at.isoformat() if program.published_at else None,
            "university": _institution_review_context(db, university),
            "academic_field": ({"id": field.id, "key": field.key,
                                "display_name": field.display_name} if field else None),
            "source_identities": provenance,
            "program_page_evidence": page_evidence,
            "registry_page_evidence": official_registry_page(db, program),
            "program_facts": facts,
            "missing_information": missing,
            "fact_count": db.scalar(select(func.count()).select_from(FactRecord).where(
                FactRecord.entity_type == "program", FactRecord.entity_id == program.id)) or 0,
            "can_publish": can_publish, "publication_blocker": publication_blocker or None,
            "publication_events": [{"action": event.action, "actor_user_id": event.actor_user_id,
                                    "reason": event.reason,
                                    "created_at": event.created_at.isoformat()}
                                   for event in publication_events],
        })
    return {"items": items, "page": page, "page_size": page_size,
            "total_items": total, "total_pages": (total + page_size - 1) // page_size}


def _publication_evidence(db: Session, program: Program) -> tuple[bool, str]:
    if program.degree_level != "masters":
        return False, "Only Master's programs can be published through this review queue."
    page = official_program_page(db, program)
    registry = official_registry_page(db, program)
    if page["status"] != "verified" and registry["status"] != "verified_government_program_record":
        return False, page["reason"] or "The official program page has not been verified."
    university = db.get(University, program.university_id)
    if university is None or (university.external_identifiers or {}).get("demo_fixture"):
        return False, "The program must link to a non-demo canonical institution."
    institution_review = db.scalar(select(InstitutionReview).where(
        InstitutionReview.university_id == university.id))
    if institution_review is None or institution_review.status != "approved":
        return False, "The canonical institution requires an explicit approved institution review."
    claims = db.scalars(select(ProgramIdentifier).where(
        ProgramIdentifier.program_id == program.id,
        ProgramIdentifier.claim_status == "accepted")).all()
    if not claims:
        return False, "An accepted source-specific program identity is required."
    has_eligible_evidence = False
    for claim in claims:
        source = db.get(Source, claim.source_id)
        document = db.get(SourceDocument, claim.source_document_id)
        if (source is None or document is None
                or source.allowed_use_policy not in REFRESHABLE_POLICIES
                or document.fetch_status != "fetched"
                or (document.http_status is not None and not 200 <= document.http_status < 300)):
            continue
        # A source URL alone does not establish which institution owns its records.
        # Require either an accepted source-scoped institutional claim or an explicit
        # reviewer-approved identity decision for that source and canonical institution.
        source_key = claim.source_key
        registered_source_key = (source.metadata_json or {}).get("adapter_key") or source.name
        if claim.source_id != source.id or document.source_id != source.id or source_key != registered_source_key:
            continue
        accepted_institution = db.scalar(select(InstitutionIdentifier.id).where(
            InstitutionIdentifier.university_id == university.id,
            InstitutionIdentifier.source_key == source_key,
            InstitutionIdentifier.claim_status == "accepted"))
        reviewed_link = db.scalar(select(InstitutionIdentityReview.id).where(
            InstitutionIdentityReview.source_id == source.id,
            InstitutionIdentityReview.resolved_university_id == university.id,
            InstitutionIdentityReview.status == "approved"))
        if accepted_institution or reviewed_link:
            has_eligible_evidence = True
            break
    if not has_eligible_evidence:
        return False, "A successful permitted source document and reviewed institution link are required."
    identities = []
    for claim in claims:
        source = db.get(Source, claim.source_id)
        document = db.get(SourceDocument, claim.source_document_id)
        identities.append({"claim_status": claim.claim_status, "source_id": claim.source_id,
            "allowed_use_policy": source.allowed_use_policy if source else None,
            "institution_linked": _source_institution_link(db, program.university_id, claim.source_id, claim.source_key),
            "source_binding_valid": bool(source and document and document.source_id == source.id
                and claim.source_key == ((source.metadata_json or {}).get("adapter_key") or source.name)),
            "source_document": {"id": document.id, "fetch_status": document.fetch_status,
                "http_status": document.http_status, **freshness_values(db, document)} if document else None})
    readiness = program_package({"title": program.canonical_name, "degree_level": program.degree_level,
        "is_active": program.is_active, "source_identities": identities,
        "program_facts": _program_review_facts(db, program)})
    if not readiness["eligible"]:
        return False, readiness["blockers"][0]
    return True, ""


def set_program_publication(db: Session, user: User, program_id: uuid.UUID, action: str,
                            reason: str, request_id: str | None = None) -> dict:
    if action not in ("publish", "unpublish"):
        raise ApiError(422, "VALIDATION_ERROR", "Unsupported program publication action.")
    reason = _require_publication_reason(reason, action)
    program = db.scalar(select(Program).where(Program.id == program_id).with_for_update())
    if program is None:
        raise ApiError(404, "NOT_FOUND", "Program not found.")
    before_status = program.publication_status
    if action == "publish":
        if before_status == "published":
            raise ApiError(409, "CONFLICT", "Program is already published.")
        eligible, message = _publication_evidence(db, program)
        if not eligible:
            raise ApiError(409, "PROGRAM_REVIEW_REQUIRED", message)
        program.publication_status = "published"
        program.published_at = _now()
    else:
        if before_status != "published":
            raise ApiError(409, "CONFLICT", "Only a published program can be unpublished.")
        program.publication_status = "hidden"
        program.published_at = None
    before = {"publication_status": before_status}
    after = {"publication_status": program.publication_status,
             "published_at": program.published_at.isoformat() if program.published_at else None}
    db.add(AuditEvent(actor_user_id=user.id, actor_type="user",
                      action="program_published" if action == "publish" else "program_unpublished",
                      entity_type="program", entity_id=program.id,
                      request_id=uuid.UUID(request_id) if request_id else None,
                      reason=reason, before_summary=before, after_summary=after))
    db.flush()
    return {"program_id": program.id, "publication_status": program.publication_status,
            "published_at": program.published_at.isoformat() if program.published_at else None}


# -------------------------------------------------------------------- sources

def _source_out(source: Source) -> dict:
    from app.core.config import settings
    schedule = (source.metadata_json or {}).get("refresh_schedule") or {}
    approved = bool(schedule.get("approved") and schedule.get("approval_reference"))
    scheduled = bool(approved and settings.enable_scheduler and source.enabled)
    health = dict((source.metadata_json or {}).get("health") or {})
    last_success = _parse_datetime(health.get("last_success_at"))
    interval = source.refresh_interval_hours
    next_refresh = last_success + timedelta(hours=interval) if last_success and interval else None
    stale = bool(next_refresh and next_refresh < _now())
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
        "last_checked_at": health.get("last_checked_at"),
        "last_success_at": health.get("last_success_at"),
        "last_content_changed_at": health.get("last_content_changed_at"),
        "next_refresh_at": next_refresh.isoformat() if next_refresh and scheduled else None,
        "scheduling": {"enabled": scheduled, "approved": approved,
                       "state": "enabled" if scheduled else "scheduler_disabled" if approved else "awaiting_operational_approval",
                       "max_records": schedule.get("max_records")},
        "freshness_status": ("stale" if stale else "current" if last_success else "unknown") if interval else "manual",
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
    freshness_available = freshness_columns_available(db)
    for source in rows:
        documents = db.scalar(select(func.count()).select_from(SourceDocument)
                              .where(SourceDocument.source_id == source.id)) or 0
        jobs = db.scalar(select(func.count()).select_from(IngestionJob)
                         .where(IngestionJob.source_id == source.id)) or 0
        latest = db.scalar(
            select(SourceDocument).where(SourceDocument.source_id == source.id)
            .options(*source_document_options(db))
            .order_by((SourceDocument.last_checked_at if freshness_available
                       else SourceDocument.retrieved_at).desc(), SourceDocument.id)
            .limit(1))
        latest_freshness = freshness_values(db, latest) if latest else {}
        items.append({**_source_out(source), "document_count": documents, "job_count": jobs,
                      "latest_academic_period": latest_freshness.get("academic_period"),
                      "latest_source_published_at": latest_freshness.get("source_published_at"),
                      "freshness_metadata_available": freshness_available})
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
    freshness_available = freshness_columns_available(db)
    documents = db.scalars(
        select(SourceDocument).where(SourceDocument.source_id == source.id)
        .options(*source_document_options(db))
        .order_by((SourceDocument.last_checked_at if freshness_available
                   else SourceDocument.retrieved_at).desc()).limit(20)).all()
    retrievals = (db.scalars(select(SourceDocumentRetrieval).where(
        SourceDocumentRetrieval.source_id == source.id)
        .order_by(SourceDocumentRetrieval.attempted_at.desc()).limit(30)).all()
        if retrieval_history_available(db) else [])
    jobs = db.scalars(select(IngestionJob).where(IngestionJob.source_id == source.id)
                      .order_by(IngestionJob.created_at.desc()).limit(10)).all()
    return {
        **_source_out(source),
        "freshness_metadata_available": freshness_available,
        "retrieval_history_available": retrieval_history_available(db),
        "documents": [{"id": d.id, "canonical_url": d.canonical_url, "title": d.title,
                       "document_type": d.document_type, "fetch_status": d.fetch_status,
                       "http_status": d.http_status, **freshness_values(db, d),
                       "retrieved_at": d.retrieved_at.isoformat(),
                       "content_hash": d.content_hash} for d in documents],
        "retrieval_attempts": [{"canonical_url": r.canonical_url,
                                "attempted_at": r.attempted_at.isoformat(),
                                "outcome": r.outcome, "http_status": r.http_status,
                                "attempt_count": r.attempt_count,
                                "error_summary": r.error_summary}
                               for r in retrievals],
        "recent_jobs": [_job_out(j) for j in jobs],
    }


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


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
    if (source.metadata_json or {}).get("requires_explicit_limit"):
        raise ApiError(409, "BOUNDED_RUN_REQUIRED",
                       "This source requires an explicit record limit. Use the bounded ingestion CLI.")
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

def _job_metrics(job: IngestionJob) -> dict:
    """Expose versioned counters and explain what can be recovered from old jobs.

    Historical IngestionJob columns are immutable aggregate counters: their
    ``records_*`` values combine institutions and programs, while the old
    ``review`` count mixed identity/program/fact review cases. Do not fabricate
    a breakdown that was never recorded.
    """
    checkpoint = job.checkpoint if isinstance(job.checkpoint, dict) else {}
    if (job.worker_version or '').startswith('ror-directory-'):
        empty = {'seen': 0, 'created': 0, 'updated': 0, 'unchanged': 0}
        return {'version': 2, 'institutions': empty, 'programs': dict(empty),
                'facts': dict(empty), 'rejected': 0, 'conflicted': 0,
                'needs_review': job.records_review_required, 'skipped': 0,
                'directory_records': {'seen': job.records_seen, 'created': job.records_created,
                    'unchanged': job.records_unchanged, 'country_counts': checkpoint.get('country_counts', {}),
                    'match_counts': checkpoint.get('match_counts', {})},
                'semantics': {'records': 'unreviewed ROR directory references only; no canonical institutions, programs or facts created'}}
    current = checkpoint.get("metrics")
    if isinstance(current, dict) and current.get("version") == 2:
        return current
    entities = checkpoint.get("entities")
    facts = checkpoint.get("facts")
    if isinstance(entities, dict) or isinstance(facts, dict):
        return {
            "version": 1,
            "quality": "legacy_partial",
            "institutions": None,
            "entities": entities if isinstance(entities, dict) else None,
            "facts": facts if isinstance(facts, dict) else None,
            "rejected": job.records_rejected,
            "conflicted": None,
            "needs_review": job.records_review_required,
            "skipped": checkpoint.get("skipped"),
            "semantics": {
                "legacy_records": "institutions_and_programs_combined",
                "legacy_review": "aggregate; conflicts and review reasons cannot be separated",
                "conflicted": "not separately recorded",
            },
        }
    return {
        "version": 0,
        "quality": "legacy_aggregate",
        "institutions": None,
        "programs": None,
        "facts": None,
        "rejected": job.records_rejected,
        "conflicted": None,
        "needs_review": job.records_review_required,
        "skipped": None,
        "semantics": {
            "legacy_records": "institutions_and_programs_combined",
            "legacy_review": "aggregate; conflicts and review reasons cannot be separated",
            "conflicted": "not separately recorded",
        },
    }


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
        "metrics": _job_metrics(job),
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
    if (job.worker_version or '').startswith('ror-directory-'):
        raise ApiError(409, 'DIRECTORY_RESUME_REQUIRED',
                       'Directory jobs require the approved bulk CLI plan and --resume-job; generic source retry is not permitted.')
    if job.status not in ("failed", "cancelled"):
        raise ApiError(409, "CONFLICT",
                       "Only failed or cancelled jobs can be retried.")
    before = {"status": job.status}
    checkpoint = dict(job.checkpoint or {})
    checkpoint["attempt_history"] = [*(checkpoint.get("attempt_history") or []), {
        "status": job.status, "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "metrics": _job_metrics(job), "error_summary": job.error_summary,
    }]
    checkpoint.pop("metrics", None)
    job.checkpoint = checkpoint
    job.records_unchanged = job.records_review_required = 0
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
        "archive_context": record_context(db, {"program": "programs", "university": "universities",
            "institution_identity_review": "institution_identity_reviews", "fact_record": "fact_records"}.get(e.entity_type, e.entity_type), e.entity_id),
        "created_at": e.created_at.isoformat()} for e in rows],
        "page": page, "page_size": page_size, "total_items": total,
        "total_pages": (total + page_size - 1) // page_size}
