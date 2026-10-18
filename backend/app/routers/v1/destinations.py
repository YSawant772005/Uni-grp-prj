"""Country/city context, official rules and scoped outcomes endpoints (§5.8)."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import destinations

router = APIRouter(tags=["destinations"])


@router.get("/destinations/countries")
async def list_countries(db: Session = Depends(get_db)):
    return {"items": destinations.list_countries(db)}


@router.get("/destinations/countries/{country_code}")
async def get_country(country_code: str, db: Session = Depends(get_db)):
    return destinations.get_country(db, country_code)


@router.get("/destinations/countries/{country_code}/cities")
async def country_cities(country_code: str, db: Session = Depends(get_db)):
    return {"items": destinations.country_cities(db, country_code)}


@router.get("/destinations/cities/{city_id}")
async def get_city(city_id: uuid.UUID, db: Session = Depends(get_db)):
    return destinations.get_city(db, city_id)


@router.get("/destinations/rules")
async def list_rules(country: str | None = Query(None, min_length=2, max_length=2),
                     rule_type: str | None = Query(None),
                     page: int = Query(1, ge=1),
                     page_size: int = Query(20, ge=1, le=100),
                     db: Session = Depends(get_db)):
    return destinations.list_rules(db, country=country, rule_type=rule_type,
                                   page=page, page_size=page_size)


@router.get("/outcomes")
async def search_outcomes(program_id: uuid.UUID | None = None,
                          field: str | None = Query(None, max_length=80),
                          country: str | None = Query(None, min_length=2, max_length=2),
                          metric: str | None = Query(None),
                          page: int = Query(1, ge=1),
                          page_size: int = Query(20, ge=1, le=100),
                          db: Session = Depends(get_db)):
    return destinations.search_outcomes(db, program_id=program_id, field=field,
                                        country=country, metric=metric,
                                        page=page, page_size=page_size)
