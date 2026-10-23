"""Reviewer/admin endpoints: review queue, fact review actions, source registry,
ingestion jobs and audit history (§5.10). Role gates are enforced server-side."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field as PydField
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models import User
from app.services import admin

router = APIRouter(tags=["admin"])

REVIEWER = Depends(require_roles("reviewer", "admin"))
ADMIN = Depends(require_roles("admin"))


class FactActionIn(BaseModel):
    version_id: uuid.UUID | None = None
    reason: str | None = PydField(default=None, max_length=2000)
    description_summary: str | None = PydField(default=None, max_length=600)


class IdentityActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = PydField(min_length=1, max_length=2000)
    university_id: uuid.UUID | None = None


class InstitutionReviewActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = PydField(pattern="^(approve|reject|defer|needs_evidence)$")
    reason: str = PydField(min_length=1, max_length=2000)


class ProgramPublicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = PydField(min_length=1, max_length=2000)


class SourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = PydField(min_length=1, max_length=250)
    base_url: str = PydField(min_length=8, max_length=500)
    source_type: str = "other"
    authority_tier: int = PydField(default=3, ge=1, le=5)
    owner_or_publisher: str | None = PydField(default=None, max_length=200)
    allowed_use_policy: str = "review_required"
    terms_url: str | None = PydField(default=None, max_length=500)
    rate_limit_notes: str | None = PydField(default=None, max_length=1000)
    license_notes: str | None = PydField(default=None, max_length=1000)
    refresh_interval_hours: int | None = PydField(default=None, ge=1, le=8760)
    enabled: bool = True


class SourcePatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = PydField(default=None, min_length=1, max_length=250)
    authority_tier: int | None = PydField(default=None, ge=1, le=5)
    owner_or_publisher: str | None = PydField(default=None, max_length=200)
    terms_url: str | None = PydField(default=None, max_length=500)
    rate_limit_notes: str | None = PydField(default=None, max_length=1000)
    license_notes: str | None = PydField(default=None, max_length=1000)
    refresh_interval_hours: int | None = PydField(default=None, ge=1, le=8760)
    enabled: bool | None = None
    metadata: dict | None = None


@router.get("/admin/review-queue")
async def review_queue(status: str | None = Query(None),
                       entity_type: str | None = Query(None, max_length=40),
                       fact_key: str | None = Query(None, max_length=80),
                       page: int = Query(1, ge=1),
                       page_size: int = Query(20, ge=1, le=100),
                       db: Session = Depends(get_db), user: User = REVIEWER):
    return admin.review_queue(db, status=status, entity_type=entity_type,
                              fact_key=fact_key, page=page, page_size=page_size)


@router.get("/admin/identity-reviews")
async def identity_review_queue(status: str = Query("pending"),
                                page: int = Query(1, ge=1),
                                page_size: int = Query(20, ge=1, le=100),
                                db: Session = Depends(get_db), user: User = REVIEWER):
    return admin.identity_review_queue(db, status=status, page=page, page_size=page_size)


@router.get("/admin/identity-reviews/{review_id}")
async def identity_review_detail(review_id: uuid.UUID, db: Session = Depends(get_db),
                                 user: User = REVIEWER):
    return admin.identity_review_detail(db, review_id)


@router.get("/admin/institution-reviews")
async def institution_review_queue(status: str = Query("pending"),
                                   stage: str = Query("all"),
                                   page: int = Query(1, ge=1),
                                   page_size: int = Query(20, ge=1, le=100),
                                   db: Session = Depends(get_db), user: User = REVIEWER):
    return admin.institution_review_queue(db, status=status, stage=stage, page=page, page_size=page_size)


@router.get("/admin/institution-reviews/{university_id}")
async def institution_review_detail(university_id: uuid.UUID, db: Session = Depends(get_db),
                                    user: User = REVIEWER):
    return admin.institution_review_detail(db, university_id)


@router.post("/admin/institutions/{university_id}/review")
async def decide_institution_review(university_id: uuid.UUID, request: Request,
                                    payload: InstitutionReviewActionIn,
                                    db: Session = Depends(get_db), user: User = REVIEWER):
    return admin.decide_institution_review(
        db, user, university_id, payload.action, payload.reason,
        getattr(request.state, "request_id", None))


@router.get("/admin/program-publication-reviews")
async def program_publication_queue(status: str = Query("candidate"),
                                   page: int = Query(1, ge=1),
                                   page_size: int = Query(20, ge=1, le=100),
                                   db: Session = Depends(get_db), user: User = REVIEWER):
    return admin.program_publication_queue(db, status=status, page=page, page_size=page_size)


@router.post("/admin/programs/{program_id}/publish")
async def publish_program(program_id: uuid.UUID, request: Request,
                          payload: ProgramPublicationIn,
                          db: Session = Depends(get_db), user: User = REVIEWER):
    return admin.set_program_publication(
        db, user, program_id, "publish", payload.reason,
        getattr(request.state, "request_id", None))


@router.post("/admin/programs/{program_id}/unpublish")
async def unpublish_program(program_id: uuid.UUID, request: Request,
                            payload: ProgramPublicationIn,
                            db: Session = Depends(get_db), user: User = REVIEWER):
    return admin.set_program_publication(
        db, user, program_id, "unpublish", payload.reason,
        getattr(request.state, "request_id", None))


@router.post("/admin/identity-reviews/{review_id}/approve")
async def approve_identity_link(review_id: uuid.UUID, request: Request,
                                payload: IdentityActionIn,
                                db: Session = Depends(get_db), user: User = REVIEWER):
    return admin.decide_identity_review(db, user, review_id, "approve_link", payload.reason,
                                        getattr(request.state, "request_id", None),
                                        payload.university_id)


@router.post("/admin/identity-reviews/{review_id}/reject")
async def reject_identity_link(review_id: uuid.UUID, request: Request,
                               payload: IdentityActionIn,
                               db: Session = Depends(get_db), user: User = REVIEWER):
    return admin.decide_identity_review(db, user, review_id, "reject", payload.reason,
                                        getattr(request.state, "request_id", None))


@router.post("/admin/identity-reviews/{review_id}/defer")
async def defer_identity_link(review_id: uuid.UUID, request: Request,
                              payload: IdentityActionIn,
                              db: Session = Depends(get_db), user: User = REVIEWER):
    return admin.decide_identity_review(db, user, review_id, "defer", payload.reason,
                                        getattr(request.state, "request_id", None))


@router.get("/admin/facts/{fact_id}")
async def fact_detail(fact_id: uuid.UUID, db: Session = Depends(get_db),
                      user: User = REVIEWER):
    return admin.fact_detail(db, fact_id)


@router.post("/admin/facts/{fact_id}/approve")
async def approve_fact(fact_id: uuid.UUID, request: Request,
                       payload: FactActionIn | None = None,
                       db: Session = Depends(get_db), user: User = REVIEWER):
    payload = payload or FactActionIn()
    return admin.approve_fact(db, user, fact_id, payload.version_id, payload.reason,
                              getattr(request.state, "request_id", None),
                              description_summary=payload.description_summary)


@router.post("/admin/facts/{fact_id}/reject")
async def reject_fact(fact_id: uuid.UUID, request: Request, payload: FactActionIn,
                      db: Session = Depends(get_db), user: User = REVIEWER):
    return admin.reject_fact(db, user, fact_id, payload.version_id, payload.reason,
                             getattr(request.state, "request_id", None))


@router.post("/admin/facts/{fact_id}/request-evidence")
async def request_evidence(fact_id: uuid.UUID, request: Request, payload: FactActionIn,
                           db: Session = Depends(get_db), user: User = REVIEWER):
    return admin.request_evidence(db, user, fact_id, payload.reason,
                                  getattr(request.state, "request_id", None))


@router.get("/admin/sources")
async def list_sources(enabled: bool | None = Query(None),
                       page: int = Query(1, ge=1),
                       page_size: int = Query(20, ge=1, le=100),
                       db: Session = Depends(get_db), user: User = REVIEWER):
    return admin.list_sources(db, enabled=enabled, page=page, page_size=page_size)


@router.post("/admin/sources", status_code=201)
async def create_source(payload: SourceIn, request: Request,
                        db: Session = Depends(get_db), user: User = ADMIN):
    return admin.create_source(db, user, payload.model_dump(),
                               getattr(request.state, "request_id", None))


@router.get("/admin/sources/{source_id}")
async def get_source(source_id: uuid.UUID, db: Session = Depends(get_db),
                     user: User = REVIEWER):
    return admin.get_source(db, source_id)


@router.patch("/admin/sources/{source_id}")
async def update_source(source_id: uuid.UUID, request: Request, payload: SourcePatchIn,
                        db: Session = Depends(get_db), user: User = ADMIN):
    return admin.update_source(db, user, source_id, payload.model_dump(exclude_unset=True),
                               getattr(request.state, "request_id", None))


@router.post("/admin/sources/{source_id}/refresh")
async def enqueue_refresh(source_id: uuid.UUID, request: Request,
                          db: Session = Depends(get_db), user: User = ADMIN):
    return admin.enqueue_refresh(db, user, source_id,
                                 getattr(request.state, "request_id", None))


@router.post("/admin/ingestion/run")
async def trigger_ingestion(request: Request,
                            source_key: str = Query(..., min_length=1, max_length=120),
                            db: Session = Depends(get_db), user: User = ADMIN):
    """Queue a refresh for a registered connector by its stable source key."""
    return admin.enqueue_refresh_by_key(db, user, source_key,
                                        getattr(request.state, "request_id", None))


@router.get("/admin/jobs")
async def list_jobs(status: str | None = Query(None),
                    job_type: str | None = Query(None),
                    source_id: uuid.UUID | None = Query(None),
                    page: int = Query(1, ge=1),
                    page_size: int = Query(20, ge=1, le=100),
                    db: Session = Depends(get_db), user: User = ADMIN):
    return admin.list_jobs(db, status=status, job_type=job_type, source_id=source_id,
                           page=page, page_size=page_size)


@router.get("/admin/jobs/{job_id}")
async def get_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = ADMIN):
    return admin.get_job(db, job_id)


@router.post("/admin/jobs/{job_id}/retry")
async def retry_job(job_id: uuid.UUID, request: Request,
                    db: Session = Depends(get_db), user: User = ADMIN):
    return admin.retry_job(db, user, job_id, getattr(request.state, "request_id", None))


@router.get("/admin/audit-events")
async def list_audit_events(action: str | None = Query(None, max_length=120),
                            actor_user_id: uuid.UUID | None = Query(None),
                            entity_type: str | None = Query(None, max_length=60),
                            since: datetime | None = Query(None),
                            page: int = Query(1, ge=1),
                            page_size: int = Query(20, ge=1, le=100),
                            db: Session = Depends(get_db), user: User = ADMIN):
    return admin.list_audit_events(db, action=action, actor_user_id=actor_user_id,
                                   entity_type=entity_type, since=since,
                                   page=page, page_size=page_size)


@router.get("/admin/catalogue-archives")
async def catalogue_archives(db: Session = Depends(get_db), user: User = ADMIN):
    from app.services.archive import operations
    return operations(db)


@router.get("/admin/catalogue-archives/{operation_id}")
async def catalogue_archive_records(operation_id: uuid.UUID,
                                    table_name: str | None = Query(None, max_length=80),
                                    page: int = Query(1, ge=1),
                                    page_size: int = Query(20, ge=1, le=100),
                                    db: Session = Depends(get_db), user: User = ADMIN):
    from app.services.archive import records
    return records(db, operation_id, table_name=table_name, page=page, page_size=page_size)
