"""Saved programs, comparisons and side-by-side compare endpoints (§5.6)."""
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field as PydField
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user, get_optional_user
from app.db.session import get_db
from app.models import User
from app.services import library

router = APIRouter(tags=["library"])


class SaveIn(BaseModel):
    program_id: uuid.UUID
    note: str | None = PydField(default=None, max_length=1000)


class CompareIn(BaseModel):
    program_ids: list[uuid.UUID] = PydField(min_length=1, max_length=library.MAX_COMPARE_PROGRAMS)


class ComparisonIn(BaseModel):
    title: str | None = PydField(default=None, max_length=160)
    program_ids: list[uuid.UUID] = PydField(min_length=1, max_length=library.MAX_COMPARE_PROGRAMS)


class ComparisonPatchIn(BaseModel):
    title: str | None = PydField(default=None, max_length=160)
    program_ids: list[uuid.UUID] | None = PydField(default=None, min_length=1,
                                                    max_length=library.MAX_COMPARE_PROGRAMS)


@router.get("/saved-programs")
async def list_saved(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"items": library.list_saved(db, user)}


@router.post("/saved-programs", status_code=201)
async def save_program(payload: SaveIn, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    return library.save_program(db, user, payload.program_id, payload.note)


@router.delete("/saved-programs/{program_id}", status_code=204)
async def unsave_program(program_id: uuid.UUID, user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    library.unsave_program(db, user, program_id)


@router.post("/programs/compare")
async def compare(payload: CompareIn, db: Session = Depends(get_db),
                  user: User | None = Depends(get_optional_user)):
    profile = None
    if user is not None:
        from app.services import profiles as profile_service
        profile = profile_service.current_profile(db, user)
    return library.compare_programs(db, payload.program_ids, profile)


@router.get("/comparisons")
async def list_comparisons(user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    return {"items": library.list_comparisons(db, user)}


@router.post("/comparisons", status_code=201)
async def create_comparison(payload: ComparisonIn, user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    return library.create_comparison(db, user, payload.title, payload.program_ids)


@router.get("/comparisons/{comparison_id}")
async def get_comparison(comparison_id: uuid.UUID, user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    return library.get_comparison(db, user, comparison_id)


@router.patch("/comparisons/{comparison_id}")
async def update_comparison(comparison_id: uuid.UUID, payload: ComparisonPatchIn,
                            user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    return library.update_comparison(db, user, comparison_id, payload.title,
                                     payload.program_ids)


@router.delete("/comparisons/{comparison_id}", status_code=204)
async def delete_comparison(comparison_id: uuid.UUID, user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    library.delete_comparison(db, user, comparison_id)
