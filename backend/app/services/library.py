"""Saved programs, saved comparisons and normalized side-by-side comparison (§5.6).

Comparison output preserves currency/period/status/source per fact; a fact the
catalogue does not know is returned as ``value: None, status: "unavailable"`` —
never zero, never omitted silently.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import (
    Campus,
    City,
    Comparison,
    ComparisonItem,
    Program,
    SavedProgram,
    StudentProfile,
    University,
    User,
)
from app.services import catalog, eligibility as eligibility_engine

MAX_COMPARE_PROGRAMS = 6


# ---------------------------------------------------------------- saved programs

def _summary_for(db: Session, program: Program) -> dict:
    university = db.get(University, program.university_id)
    ctx = catalog._page_context(db, [program.id])
    city = None
    if program.campus_id:
        campus = db.get(Campus, program.campus_id)
        if campus:
            city = db.get(City, campus.city_id)
    return catalog._summary(program, university, city, ctx)


def list_saved(db: Session, user: User) -> list[dict]:
    rows = db.execute(
        select(SavedProgram, Program)
        .join(Program, Program.id == SavedProgram.program_id)
        .where(SavedProgram.user_id == user.id)
        .order_by(SavedProgram.created_at.desc())).all()
    return [{"program_id": sp.program_id, "note": sp.note,
             "saved_at": sp.created_at.isoformat() if sp.created_at else None,
             "program": _summary_for(db, program)}
            for sp, program in rows]


def save_program(db: Session, user: User, program_id: uuid.UUID, note: str | None) -> dict:
    program = db.get(Program, program_id)
    if program is None or program.publication_status != "published" or not program.is_active:
        raise ApiError(404, "NOT_FOUND", "Program not found.")
    existing = db.scalar(select(SavedProgram).where(
        SavedProgram.user_id == user.id, SavedProgram.program_id == program_id))
    if existing is None:
        existing = SavedProgram(user_id=user.id, program_id=program_id, note=note)
        db.add(existing)
        db.flush()
    elif note is not None:
        existing.note = note
        db.flush()
    return {"program_id": program_id, "note": existing.note,
            "saved_at": existing.created_at.isoformat() if existing.created_at else None,
            "program": _summary_for(db, program)}


def unsave_program(db: Session, user: User, program_id: uuid.UUID) -> None:
    row = db.scalar(select(SavedProgram).where(
        SavedProgram.user_id == user.id, SavedProgram.program_id == program_id))
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Saved program not found.")
    db.delete(row)
    db.flush()


# ------------------------------------------------------------------- comparisons

def _normalize_ids(program_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    unique = list(dict.fromkeys(program_ids))
    if not unique:
        raise ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       [{"field": "program_ids", "code": "required",
                         "message": "Provide at least one program to compare."}])
    if len(unique) > MAX_COMPARE_PROGRAMS:
        raise ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       [{"field": "program_ids", "code": "too_many",
                         "message": f"At most {MAX_COMPARE_PROGRAMS} programs per comparison."}])
    return unique


def _published_programs(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, Program]:
    rows = db.scalars(select(Program).where(
        Program.id.in_(ids),
        Program.publication_status == "published", Program.is_active.is_(True))).all()
    found = {p.id: p for p in rows}
    missing = [str(i) for i in ids if i not in found]
    if missing:
        raise ApiError(404, "NOT_FOUND", f"Program(s) not found: {', '.join(missing)}.")
    return found


def compare_programs(db: Session, program_ids: list[uuid.UUID],
                     profile: StudentProfile | None = None) -> dict:
    """Normalized fact matrix for the supplied programs."""
    ids = _normalize_ids(program_ids)
    programs = _published_programs(db, ids)

    columns = []
    for pid in ids:
        program = programs[pid]
        ctx = catalog._page_context(db, [program.id])
        fees = ctx["fees"].get(program.id, [])
        tuition = catalog._tuition_fee_for(fees)
        tuition_prov = ctx["facts"].get(tuition.fact_id) if tuition and tuition.fact_id else None
        reqs = ctx["requirements"].get(program.id, [])
        intakes = ctx["intakes"].get(program.id, [])
        deadline = next((i.application_deadline for i in intakes if i.application_deadline), None)
        university = db.get(University, program.university_id)
        ev = (eligibility_engine.evaluate_program(profile, reqs)
              if profile is not None and profile.user_id else None)
        columns.append({
            "program_id": program.id,
            "name": program.canonical_name,
            "university": university.canonical_name if university else None,
            "country_code": program.country_code,
            "degree_level": program.degree_level,
            "duration_months": program.duration_max_months,
            "language": program.delivery_language,
            "tuition": catalog._money_object(tuition, tuition_prov),
            "nearest_deadline": deadline,
            "requirements_total": len(reqs),
            "requirements_unverified": sum(
                1 for r in reqs
                if ctx["facts"].get(r.source_fact_id, {}).get("status") != "verified"),
            "recognition_status": university.recognition_status if university else None,
            "eligibility_status": ev["status"] if ev else None,
            "data_quality": catalog._data_quality(
                tuition.status if tuition else None,
                [ctx["facts"].get(r.source_fact_id, {}).get("status", "unverified") for r in reqs],
                has_intake=bool(intakes), has_program_outcomes=bool(ctx["outcomes"].get(program.id)),
            ),
        })
    return {"items": columns, "count": len(columns)}


def _owned_comparison(db: Session, user: User, comparison_id: uuid.UUID) -> Comparison:
    row = db.get(Comparison, comparison_id)
    if row is None or row.user_id != user.id:
        raise ApiError(404, "NOT_FOUND", "Comparison not found.")
    return row


def _comparison_out(db: Session, comparison: Comparison) -> dict:
    items = db.execute(
        select(ComparisonItem).where(ComparisonItem.comparison_id == comparison.id)
        .order_by(ComparisonItem.position)).scalars().all()
    ids = [i.program_id for i in items]
    return {
        "id": comparison.id,
        "title": comparison.title,
        "created_at": comparison.created_at.isoformat() if comparison.created_at else None,
        "updated_at": comparison.updated_at.isoformat() if comparison.updated_at else None,
        "program_ids": ids,
        "positions": {str(i.program_id): i.position for i in items},
    }


def get_comparison(db: Session, user: User, comparison_id: uuid.UUID) -> dict:
    return _comparison_out(db, _owned_comparison(db, user, comparison_id))


def list_comparisons(db: Session, user: User) -> list[dict]:
    rows = db.scalars(select(Comparison).where(Comparison.user_id == user.id)
                      .order_by(Comparison.updated_at.desc())).all()
    return [_comparison_out(db, c) for c in rows]


def create_comparison(db: Session, user: User, title: str | None,
                      program_ids: list[uuid.UUID]) -> dict:
    ids = _normalize_ids(program_ids)
    _published_programs(db, ids)
    comparison = Comparison(user_id=user.id, title=title)
    db.add(comparison)
    db.flush()
    for position, pid in enumerate(ids, start=1):
        db.add(ComparisonItem(comparison_id=comparison.id, program_id=pid, position=position))
    db.flush()
    return _comparison_out(db, comparison)


def update_comparison(db: Session, user: User, comparison_id: uuid.UUID,
                      title: str | None, program_ids: list[uuid.UUID] | None) -> dict:
    comparison = _owned_comparison(db, user, comparison_id)
    if title is not None:
        comparison.title = title
    if program_ids is not None:
        ids = _normalize_ids(program_ids)
        _published_programs(db, ids)
        for item in list(comparison.items):
            db.delete(item)
        db.flush()
        for position, pid in enumerate(ids, start=1):
            db.add(ComparisonItem(comparison_id=comparison.id, program_id=pid,
                                  position=position))
    db.flush()
    db.refresh(comparison)
    return _comparison_out(db, comparison)


def delete_comparison(db: Session, user: User, comparison_id: uuid.UUID) -> None:
    comparison = _owned_comparison(db, user, comparison_id)
    db.delete(comparison)
    db.flush()
