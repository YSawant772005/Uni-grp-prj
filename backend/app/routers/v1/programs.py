"""Program discovery endpoints (public read-only)."""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.session import get_db
from app.services import catalog

router = APIRouter(prefix="/programs", tags=["programs"])


def _uuid_or_404(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise ApiError(404, "NOT_FOUND", "Program not found.")


@router.get("")
async def list_programs(
    q: str | None = Query(None, max_length=200,
                          description="Case-insensitive substring match on program or university name."),
    country: str | None = Query(None, min_length=2, max_length=2),
    city: str | None = Query(None, max_length=80),
    field: str | None = Query(None, max_length=80, description="Field key, e.g. data_science."),
    degree_level: str | None = Query(None),
    language: str | None = Query(None),
    min_duration_months: int | None = Query(None, ge=1, le=120),
    max_duration_months: int | None = Query(None, ge=1, le=120),
    max_tuition: Decimal | None = Query(None, ge=0, description="Filters TUITION ALONE; requires currency."),
    currency: str | None = Query(None, min_length=3, max_length=3),
    recognition_status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("name", description="One of: name, deadline, tuition, country."),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    return catalog.search_programs(
        db, q=q, country=country, city=city, field=field, degree_level=degree_level,
        language=language, min_duration_months=min_duration_months,
        max_duration_months=max_duration_months, max_tuition=max_tuition, currency=currency,
        recognition_status=recognition_status, page=page, page_size=page_size,
        sort=sort, order=order,
    )


@router.get("/{program_id}")
async def program_detail(program_id: str, db: Session = Depends(get_db)):
    return catalog.get_program(db, _uuid_or_404(program_id))


@router.get("/{program_id}/requirements")
async def program_requirements(program_id: str, db: Session = Depends(get_db)):
    return {"items": catalog.get_requirements(db, _uuid_or_404(program_id))}


@router.get("/{program_id}/fees")
async def program_fees(program_id: str, db: Session = Depends(get_db)):
    return {"items": catalog.get_fees(db, _uuid_or_404(program_id))}


@router.get("/{program_id}/intakes")
async def program_intakes(program_id: str, db: Session = Depends(get_db)):
    return {"items": catalog.get_intakes(db, _uuid_or_404(program_id))}


@router.get("/{program_id}/evidence")
async def program_evidence(
    program_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return catalog.get_evidence(db, _uuid_or_404(program_id), page=page, page_size=page_size)


@router.get("/{program_id}/outcomes")
async def program_outcomes(program_id: str, db: Session = Depends(get_db)):
    return {"items": catalog.get_outcomes(db, _uuid_or_404(program_id))}
