"""Country/city context, official rule resources and scoped outcomes (§5.8).

Rule resources always expose their official URL plus checked/effective dates so
the UI can show freshness; outcomes always expose their population scope so
subject/country data is never mistaken for a program's own result.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import (
    City,
    Country,
    Field,
    LivingCostFact,
    OfficialRuleResource,
    ProgramOutcomeEvidence,
    University,
)


def list_countries(db: Session) -> list[dict]:
    rows = db.execute(
        select(Country,
               func.count(City.id).label("city_count"),
               func.count(University.id).label("university_count"))
        .outerjoin(City, City.country_code == Country.code)
        .outerjoin(University, University.country_code == Country.code)
        .group_by(Country.code).order_by(Country.name)).all()
    return [{"code": c.code, "name": c.name, "region": c.region,
             "official_study_url": c.official_study_url,
             "official_immigration_url": c.official_immigration_url,
             "city_count": city_count, "university_count": university_count}
            for c, city_count, university_count in rows]


def get_country(db: Session, country_code: str) -> dict:
    code = country_code.upper()
    country = db.get(Country, code)
    if country is None:
        raise ApiError(404, "NOT_FOUND", "Country not found.")
    rules = db.scalars(select(OfficialRuleResource)
                       .where(OfficialRuleResource.country_code == code)
                       .order_by(OfficialRuleResource.rule_type,
                                 OfficialRuleResource.title)).all()
    cities = db.scalars(select(City).where(City.country_code == code)
                        .order_by(City.name)).all()
    return {
        "code": country.code, "name": country.name, "region": country.region,
        "official_study_url": country.official_study_url,
        "official_immigration_url": country.official_immigration_url,
        "cities": [_city_out(db, c, with_costs=False) for c in cities],
        "official_rules": [_rule_out(r) for r in rules],
    }


def _rule_out(r: OfficialRuleResource) -> dict:
    return {
        "id": r.id, "country_code": r.country_code, "rule_type": r.rule_type,
        "title": r.title,
        "official_url": r.official_url, "summary": r.summary,
        "effective_from": r.effective_from.isoformat() if r.effective_from else None,
        "effective_to": r.effective_to.isoformat() if r.effective_to else None,
        "last_checked_at": r.last_checked_at.isoformat() if r.last_checked_at else None,
        "freshness_note": ("Last checked on the official page; verify current rules there."
                           if r.last_checked_at else
                           "Not yet checked against the official page — verify before relying."),
    }


def _city_out(db: Session, city: City, with_costs: bool) -> dict:
    out = {"id": city.id, "name": city.name, "slug": city.slug,
           "country_code": city.country_code, "admin_region": city.admin_region}
    if with_costs:
        rows = db.scalars(select(LivingCostFact)
                          .where(LivingCostFact.city_id == city.id)
                          .order_by(LivingCostFact.cost_category)).all()
        out["living_costs"] = [
            {"category": r.cost_category, "min": r.amount_min,
             "typical": r.amount_typical, "max": r.amount_max,
             "currency": r.currency, "period": r.period,
             "effective_year": r.effective_year,
             "status": "estimated" if r.amount_typical is not None else "unavailable"}
            for r in rows]
        out["living_cost_year"] = rows[0].effective_year if rows else None
    return out


def country_cities(db: Session, country_code: str) -> list[dict]:
    code = country_code.upper()
    if db.get(Country, code) is None:
        raise ApiError(404, "NOT_FOUND", "Country not found.")
    rows = db.scalars(select(City).where(City.country_code == code)
                      .order_by(City.name)).all()
    return [_city_out(db, c, with_costs=False) for c in rows]


def get_city(db: Session, city_id: uuid.UUID) -> dict:
    city = db.get(City, city_id)
    if city is None:
        raise ApiError(404, "NOT_FOUND", "City not found.")
    return _city_out(db, city, with_costs=True)


def list_rules(db: Session, country: str | None = None, rule_type: str | None = None,
               page: int = 1, page_size: int = 20) -> dict:
    conds = []
    if country:
        conds.append(OfficialRuleResource.country_code == country.upper())
    if rule_type:
        conds.append(OfficialRuleResource.rule_type == rule_type)
    total = db.scalar(select(func.count()).select_from(OfficialRuleResource)
                      .where(*conds)) or 0
    rows = db.scalars(select(OfficialRuleResource).where(*conds)
                      .order_by(OfficialRuleResource.country_code,
                                OfficialRuleResource.rule_type)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_rule_out(r) for r in rows], "page": page, "page_size": page_size,
            "total_items": total, "total_pages": (total + page_size - 1) // page_size}


# ------------------------------------------------------------------ outcomes

def search_outcomes(db: Session, *, program_id: uuid.UUID | None = None,
                    field: str | None = None, country: str | None = None,
                    metric: str | None = None, page: int = 1, page_size: int = 20) -> dict:
    conds = []
    if program_id:
        conds.append(ProgramOutcomeEvidence.program_id == program_id)
    if field:
        conds.append(ProgramOutcomeEvidence.field_id.in_(
            select(Field.id).where(Field.key == field)))
    if country:
        conds.append(ProgramOutcomeEvidence.country_code == country.upper())
    if metric:
        conds.append(ProgramOutcomeEvidence.metric_key == metric)
    total = db.scalar(select(func.count()).select_from(ProgramOutcomeEvidence)
                      .where(*conds)) or 0
    rows = db.scalars(select(ProgramOutcomeEvidence).where(*conds)
                      .order_by(ProgramOutcomeEvidence.population_scope,
                                ProgramOutcomeEvidence.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [_outcome_out(r) for r in rows],
        "page": page, "page_size": page_size, "total_items": total,
        "total_pages": (total + page_size - 1) // page_size,
        "scope_note": "population_scope states whose data each row describes; only "
                      "'program' scope describes that program's own outcome.",
    }


def _outcome_out(r: ProgramOutcomeEvidence) -> dict:
    return {
        "id": r.id, "program_id": r.program_id, "university_id": r.university_id,
        "field_id": r.field_id, "country_code": r.country_code,
        "metric_key": r.metric_key, "metric_value": r.metric_value,
        "metric_unit": r.metric_unit, "currency": r.currency,
        "cohort_label": r.cohort_label, "cohort_year": r.cohort_year,
        "sample_size": r.sample_size, "population_scope": r.population_scope,
        "methodology_note": r.methodology_note,
        "status": "estimated",
    }
