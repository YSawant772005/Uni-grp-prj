"""Scholarships, funding opportunities and profile matching (§5.7).

Money keeps currency + amount range; an unknown amount stays None. Matching is
deterministic rule checking against the profile — it never claims eligibility or
approval, and uncheckable rules are surfaced as unverified rather than assumed.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import (
    FundingOpportunity,
    Scholarship,
    ScholarshipEligibilityRule,
    ScholarshipProgramLink,
    StudentProfile,
)
from app.services import eligibility as eligibility_engine

MAX_MATCH_ROWS = 50


def _scholarship_out(db: Session, s: Scholarship) -> dict:
    rules = db.scalars(select(ScholarshipEligibilityRule)
                       .where(ScholarshipEligibilityRule.scholarship_id == s.id)
                       .order_by(ScholarshipEligibilityRule.id)).all()
    return {
        "id": s.id, "name": s.name, "provider_name": s.provider_name,
        "official_url": s.official_url, "country_code": s.country_code,
        "award_type": s.award_type,
        "amount": {"min": s.amount_min, "max": s.amount_max, "currency": s.currency,
                   "status": "estimated" if s.amount_min is not None else "unavailable"},
        "coverage_type": s.coverage_type, "renewable": s.renewable,
        "deadline": s.deadline.isoformat() if s.deadline else None,
        "status": s.status,
        "eligibility_rules": [
            {"rule_key": r.rule_key, "operator": r.operator, "expected_value": r.expected_value,
             "is_mandatory": r.is_mandatory, "group_key": r.group_key} for r in rules],
    }


def search_scholarships(db: Session, *, country: str | None = None,
                        q: str | None = None, page: int = 1, page_size: int = 20) -> dict:
    conds = []
    if country:
        conds.append(Scholarship.country_code == country.upper())
    if q:
        conds.append(Scholarship.name.ilike(f"%{q.strip()}%"))
    total = db.scalar(select(func.count()).select_from(Scholarship).where(*conds)) or 0
    rows = db.scalars(select(Scholarship).where(*conds)
                      .order_by(Scholarship.deadline.nulls_last(), Scholarship.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_scholarship_out(db, s) for s in rows], "page": page,
            "page_size": page_size, "total_items": total,
            "total_pages": (total + page_size - 1) // page_size}


def get_scholarship(db: Session, scholarship_id: uuid.UUID) -> dict:
    s = db.get(Scholarship, scholarship_id)
    if s is None:
        raise ApiError(404, "NOT_FOUND", "Scholarship not found.")
    links = db.scalars(select(ScholarshipProgramLink)
                       .where(ScholarshipProgramLink.scholarship_id == s.id)).all()
    out = _scholarship_out(db, s)
    out["linked_program_ids"] = [l.program_id for l in links]
    return out


def match_scholarships(db: Session, profile: StudentProfile,
                       program_id: uuid.UUID | None = None) -> dict:
    """Deterministic match: checkable rules vs profile; others marked unverified."""
    scholarships = db.scalars(select(Scholarship)
                              .order_by(Scholarship.deadline.nulls_last()).limit(MAX_MATCH_ROWS)).all()
    preferred = {p.country_code for p in (profile.country_preferences or [])}
    today = date.today()
    matches = []
    for s in scholarships:
        outcomes, concerns, unverified = [], [], []
        if s.deadline and s.deadline < today:
            outcomes.append({"rule": "deadline", "status": "fail",
                             "explanation": f"Deadline {s.deadline} has passed."})
        elif s.deadline:
            outcomes.append({"rule": "deadline", "status": "pass",
                             "explanation": f"Deadline {s.deadline} is upcoming."})
        if s.country_code:
            if preferred and s.country_code in preferred:
                outcomes.append({"rule": "country", "status": "pass",
                                 "explanation": "Award country is among your preferences."})
            elif preferred:
                outcomes.append({"rule": "country", "status": "conditional",
                                 "explanation": "Award country is outside your preferences."})
            else:
                unverified.append("country_preferences_missing")
        rules = db.scalars(select(ScholarshipEligibilityRule)
                           .where(ScholarshipEligibilityRule.scholarship_id == s.id)).all()
        for r in rules:
            ev = eligibility_engine.evaluate_requirement(
                _rule_as_requirement(r), profile)
            outcomes.append({"rule": r.rule_key, "status": ev["status"],
                             "explanation": ev["explanation"]})
            if ev["status"] == "fail":
                concerns.append(r.rule_key)
            elif ev["status"] == "unknown":
                unverified.append(r.rule_key)
        status = ("not_matching" if any(o["status"] == "fail" for o in outcomes)
                  else "needs_review" if unverified
                  else "matching")
        matches.append({
            "scholarship_id": s.id, "name": s.name, "provider_name": s.provider_name,
            "match_status": status, "outcomes": outcomes, "concerns": concerns,
            "unverified": sorted(set(unverified)),
            "amount": {"min": s.amount_min, "max": s.amount_max, "currency": s.currency},
            "deadline": s.deadline.isoformat() if s.deadline else None,
            "official_url": s.official_url,
            "program_id": program_id,
        })
    return {"items": matches, "note": "Matching checks published rules against your profile; "
                                      "it is not an eligibility guarantee or award decision."}


def _rule_as_requirement(rule: ScholarshipEligibilityRule):
    """Adapt a scholarship rule row to the shared evaluator's interface."""
    from app.models import AdmissionRequirement
    return AdmissionRequirement(
        id=rule.id, program_id=None,
        requirement_type=rule.rule_key if rule.rule_key in (
            "grade", "language_test", "work_experience", "degree", "major",
            "prerequisite_course") else "other",
        requirement_key=rule.rule_key, operator=rule.operator,
        expected_value=rule.expected_value, is_mandatory=rule.is_mandatory,
        group_key=rule.group_key, group_operator="AND",
    )


def search_funding(db: Session, *, opportunity_type: str | None = None,
                   country: str | None = None, q: str | None = None,
                   page: int = 1, page_size: int = 20) -> dict:
    conds = []
    if opportunity_type:
        conds.append(FundingOpportunity.opportunity_type == opportunity_type)
    if country:
        conds.append(FundingOpportunity.eligible_countries.op_contains([country.upper()]))
    if q:
        conds.append(FundingOpportunity.name.ilike(f"%{q.strip()}%"))
    total = db.scalar(select(func.count()).select_from(FundingOpportunity).where(*conds)) or 0
    rows = db.scalars(select(FundingOpportunity).where(*conds)
                      .order_by(FundingOpportunity.deadline.nulls_last(), FundingOpportunity.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_funding_out(o) for o in rows], "page": page, "page_size": page_size,
            "total_items": total, "total_pages": (total + page_size - 1) // page_size}


def _funding_out(o: FundingOpportunity) -> dict:
    return {
        "id": o.id, "name": o.name, "provider_name": o.provider_name,
        "opportunity_type": o.opportunity_type, "official_url": o.official_url,
        "eligible_countries": o.eligible_countries,
        "eligible_nationalities": o.eligible_nationalities,
        "study_levels": o.study_levels, "field_eligibility": o.field_eligibility,
        "award_summary": o.award_summary,
        "opening_date": o.opening_date.isoformat() if o.opening_date else None,
        "deadline": o.deadline.isoformat() if o.deadline else None,
        "status": o.status,
    }


def get_funding(db: Session, opportunity_id: uuid.UUID) -> dict:
    o = db.get(FundingOpportunity, opportunity_id)
    if o is None:
        raise ApiError(404, "NOT_FOUND", "Funding opportunity not found.")
    return _funding_out(o)
