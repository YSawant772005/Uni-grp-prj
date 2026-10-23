"""Eligibility evaluation and recommendation-run endpoints (own profile only)."""
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field as PydField
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.permissions import get_current_user
from app.db.session import get_db
from app.models import Program, User
from app.services import eligibility as eligibility_engine
from app.services import profiles as profile_service
from app.services import recommendations as rec_service
from app.services import catalog as catalog_service

router = APIRouter(tags=["eligibility"])


class EvaluationIn(BaseModel):
    program_ids: list[uuid.UUID] = PydField(default_factory=list, max_length=50)


@router.post("/eligibility/evaluations")
async def evaluate(payload: EvaluationIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    if not payload.program_ids:
        raise ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       [{"field": "program_ids", "code": "required",
                         "message": "Provide at least one program_id."}])
    profile = profile_service.current_profile(db, user)
    items = []
    for pid in payload.program_ids:
        program = db.get(Program, pid)
        if program is None or not catalog_service.student_visible_program(db, program):
            raise ApiError(404, "NOT_FOUND", f"Program {pid} not found.")
        ev = eligibility_engine.evaluate_for_program(db, profile, pid)
        items.append({"program_id": pid, "program_name": program.canonical_name, **ev})
    return {"items": items}


class RecommendationIn(BaseModel):
    filters: dict = PydField(default_factory=dict)
    limit_per_tier: int | None = PydField(default=None, ge=1, le=100)


@router.post("/recommendations")
async def create_run(payload: RecommendationIn | None = None,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payload = payload or RecommendationIn()
    profile = profile_service.current_profile(db, user)
    run, _tiers, _excluded = rec_service.create_run(
        db, user, profile, payload.filters, payload.limit_per_tier)
    return rec_service.get_run(db, user, run.id)


@router.get("/recommendations")
async def list_runs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"items": rec_service.list_runs(db, user)}


@router.get("/recommendations/{run_id}")
async def get_run(run_id: uuid.UUID, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    return rec_service.get_run(db, user, run_id)


@router.get("/recommendations/{run_id}/explanations")
async def get_explanations(run_id: uuid.UUID, user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    return rec_service.explanations(db, user, run_id)


@router.post("/recommendations/{run_id}/refresh")
async def refresh_run(run_id: uuid.UUID, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    profile = profile_service.current_profile(db, user)
    run, _tiers, _excluded = rec_service.refresh_run(db, user, profile, run_id)
    return rec_service.get_run(db, user, run.id)
