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
                              getattr(request.state, "request_id", None))


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
