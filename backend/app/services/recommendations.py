"""Recommendation runs: hard constraints -> eligibility -> fit scoring -> tiers.

Hard constraints (mandatory countries, budget ceiling, reliable ineligible) are applied
before scoring. Every run is persisted with a profile snapshot and the ruleset version
for reproducibility; tiers are competitiveness-based, never an admission probability.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import (
    Field,
    Program,
    ProgramOutcomeEvidence,
    RecommendationItem,
    RecommendationRuleset,
    RecommendationRun,
    RequirementEvaluation,
    University,
)
from app.services import eligibility as eligibility_engine
from app.services import scoring as scoring_engine

DEFAULT_LIMIT_PER_TIER = 20


def _active_ruleset(db: Session) -> RecommendationRuleset:
    ruleset = db.scalar(select(RecommendationRuleset)
                        .where(RecommendationRuleset.is_active.is_(True))
                        .order_by(RecommendationRuleset.created_at.desc()).limit(1))
    if ruleset is None:
        raise ApiError(503, "NO_RULESET", "No active recommendation ruleset is configured.")
    return ruleset


def _weights(ruleset: RecommendationRuleset) -> dict:
    return (ruleset.scoring_config or {}).get("weights", {})


def _hard_constraints(db: Session, profile, programs: list[Program], filters: dict):
    """Return (allowed, excluded) where excluded items carry deterministic reason codes."""
    mandatory = [p.country_code for p in (profile.country_preferences or []) if p.is_mandatory]
    budget = (filters or {}).get("max_total_budget") or {}
    budget_amount = budget.get("amount")
    budget_currency = budget.get("currency")
    if budget_amount is not None and not budget_currency:
        raise ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       [{"field": "filters.max_total_budget.currency",
                         "code": "required",
                         "message": "Currency is required with a budget ceiling."}])

    allowed, excluded = [], []
    for program in programs:
        reasons = []
        if mandatory and program.country_code not in mandatory:
            reasons.append("outside_mandatory_countries")
        if budget_amount is not None:
            cost = scoring_engine.estimate_program_cost(db, program)
            total, _notes = scoring_engine.total_in_currency(db, cost, budget_currency)
            if total is not None and total > Decimal(str(budget_amount)):
                reasons.append("exceeds_budget_ceiling")
        if reasons:
            excluded.append((program, reasons))
        else:
            allowed.append(program)
    return allowed, excluded


def _snapshot(profile) -> dict:
    return {
        "intended_degree_level": profile.intended_degree_level,
        "field_id": str(profile.field_id) if profile.field_id else None,
        "grade_value": float(profile.grade_value) if profile.grade_value is not None else None,
        "grade_scale_max": float(profile.grade_scale_max) if profile.grade_scale_max is not None else None,
        "grade_system": profile.grade_system,
        "english_test_status": profile.english_test_status,
        "english_test_type": profile.english_test_type,
        "english_test_overall": float(profile.english_test_overall)
        if profile.english_test_overall is not None else None,
        "budget_amount": float(profile.budget_amount) if profile.budget_amount is not None else None,
        "budget_currency": profile.budget_currency,
        "budget_basis": profile.budget_basis,
        "work_experience_months": profile.work_experience_months,
        "country_preferences": [
            {"country_code": p.country_code, "rank": p.preference_rank, "mandatory": p.is_mandatory}
            for p in (profile.country_preferences or [])],
    }


def _requirement_thresholds(db: Session, program) -> dict:
    out = {}
    for req in eligibility_engine.load_requirements(db, program.id):
        if req.requirement_type == "grade" and req.expected_value:
            val = req.expected_value.get("value")
            scale = req.expected_value.get("scale") or "4.0"
            if val is not None:
                out["min_grade_ratio"] = float(Decimal(str(val)) / Decimal(str(scale)))
        if req.requirement_type == "language_test" and req.expected_value:
            val = req.expected_value.get("value")
            if val is not None:
                out["min_english"] = val
    return out


def _outcome_rate(db: Session, program):
    row = db.scalar(select(ProgramOutcomeEvidence)
                    .where(ProgramOutcomeEvidence.program_id == program.id)
                    .order_by(ProgramOutcomeEvidence.id).limit(1))
    if row is None:
        row = db.scalar(select(ProgramOutcomeEvidence)
                        .where(ProgramOutcomeEvidence.field_id == program.field_id)
                        .order_by(ProgramOutcomeEvidence.id).limit(1))
    return (float(row.metric_value) if row and row.metric_value is not None else None)


def _recognition(db: Session, program) -> str | None:
    university = db.get(University, program.university_id)
    return university.recognition_status if university else None


def create_run(db: Session, user, profile, filters: dict | None, limit_per_tier: int | None):
    filters = filters or {}
    limit_per_tier = limit_per_tier or DEFAULT_LIMIT_PER_TIER
    ruleset = _active_ruleset(db)
    weights = _weights(ruleset)
    tier_limits = (ruleset.scoring_config or {}).get("tiers", {})

    conds = [Program.publication_status == "published", Program.is_active.is_(True)]
    if filters.get("countries"):
        conds.append(Program.country_code.in_([c.upper() for c in filters["countries"]]))
    if filters.get("fields"):
        conds.append(Program.field_id.in_(select(Field.id).where(Field.key.in_(filters["fields"]))))
    if filters.get("degree_level"):
        conds.append(Program.degree_level == filters["degree_level"])
    programs = list(db.scalars(select(Program).where(*conds).order_by(Program.id)).all())

    allowed, excluded = _hard_constraints(db, profile, programs, filters)

    run = RecommendationRun(
        user_id=user.id, profile_id=profile.id,
        profile_snapshot={"profile": _snapshot(profile), "filters": filters},
        ruleset_id=ruleset.id, data_snapshot_at=datetime.now(timezone.utc),
        status="running", started_at=datetime.now(timezone.utc),
        input_hash=hashlib.sha256(
            json.dumps({"filters": filters, "profile": _snapshot(profile)},
                       sort_keys=True, default=str).encode()).hexdigest()[:32],
    )
    db.add(run)
    db.flush()

    tiers: dict[str, list] = {"ambitious": [], "target": [], "safer_fit": []}
    warnings: list[str] = []
    eligible_count = 0

    for program, reasons in excluded:
        ev = eligibility_engine.evaluate_program(profile, eligibility_engine.load_requirements(db, program.id))
        item = RecommendationItem(
            run_id=run.id, program_id=program.id, tier=None,
            eligibility_status=ev["status"], fit_score=None, score_breakdown=None,
            reason_codes=reasons + ["excluded_by_hard_constraint"],
            concerns=ev["unsatisfied"], missing_information=ev["unknowns"],
        )
        db.add(item)
        db.flush()
        _persist_evaluations(db, item, ev)

    for program in allowed:
        ev = eligibility_engine.evaluate_program(profile, eligibility_engine.load_requirements(db, program.id))
        if ev["status"] == "ineligible":
            item = RecommendationItem(
                run_id=run.id, program_id=program.id, tier=None,
                eligibility_status=ev["status"], fit_score=None, score_breakdown=None,
                reason_codes=["ineligible_mandatory_requirement"],
                concerns=ev["unsatisfied"], missing_information=ev["unknowns"],
            )
            db.add(item)
            db.flush()
            _persist_evaluations(db, item, ev)
            continue

        eligible_count += 1
        cost = scoring_engine.estimate_program_cost(db, program)
        total, cost_notes = scoring_engine.total_in_currency(db, cost, profile.budget_currency)
        dims = scoring_engine.score_dimensions(
            profile, program, recognition_status=_recognition(db, program),
            outcome_rate=_outcome_rate(db, program), total_cost=total)
        fit_score, breakdown, dim_warnings = scoring_engine.combine(dims, weights)
        tier = scoring_engine.competitiveness_tier(profile, _requirement_thresholds(db, program))
        reasons = _positive_reasons(breakdown)
        concerns = list(dict.fromkeys(
            ev["unsatisfied"] + ev["conditions"] + [n for n in dim_warnings if "unavailable" in n]))
        warnings.extend(dim_warnings + cost_notes)
        item = RecommendationItem(
            run_id=run.id, program_id=program.id, tier=tier,
            eligibility_status=ev["status"], fit_score=fit_score,
            score_breakdown=breakdown, reason_codes=reasons,
            concerns=concerns, missing_information=ev["unknowns"],
        )
        tiers[tier].append(item)
        db.add(item)
        db.flush()
        _persist_evaluations(db, item, ev)

    # honour per-tier caps from the ruleset; overflow is demoted to the next tier,
    # never dropped (safer_fit is the final tier and stays uncapped)
    order = ["ambitious", "target", "safer_fit"]
    for i, name in enumerate(order):
        cap = int(tier_limits.get(name, DEFAULT_LIMIT_PER_TIER))
        members = sorted(tiers[name], key=lambda it: (it.fit_score or 0), reverse=True)
        tiers[name], overflow = members[:cap], members[cap:]
        if overflow and i + 1 < len(order):  # safer_fit is final and stays uncapped
            nxt = order[i + 1]
            for item in overflow:
                item.tier = nxt
            tiers[nxt] = sorted(tiers[nxt] + overflow,
                                key=lambda it: (it.fit_score or 0), reverse=True)
        elif overflow:
            tiers[name] = members  # never drop from the final tier

    run.status = "succeeded"
    run.completed_at = datetime.now(timezone.utc)
    run.result_summary = {t: len(v) for t, v in tiers.items()}
    run.warning_summary = sorted(set(warnings))
    db.flush()
    return run, tiers, len(excluded)


def _positive_reasons(breakdown: list[dict]) -> list[str]:
    scored = [b for b in breakdown if b.get("score") is not None]
    scored.sort(key=lambda b: b["score"], reverse=True)
    return [f"{b['dimension']}: {b['note']}" for b in scored[:3]]


def _persist_evaluations(db: Session, item: RecommendationItem, ev: dict) -> None:
    for r in ev["requirements"]:
        db.add(RequirementEvaluation(
            recommendation_item_id=item.id,
            admission_requirement_id=r["requirement_id"],
            status=r["status"],
            applicant_value_json={"value": r["evaluated_value"]},
            expected_value_json=r["expected_value"] or {},
            explanation=r["explanation"],
        ))
    db.flush()


# --------------------------------------------------------------------------- output

def _item_out(db: Session, item: RecommendationItem) -> dict:
    program = db.get(Program, item.program_id)
    university = db.get(University, program.university_id) if program else None
    return {
        "id": item.id,
        "program_id": item.program_id,
        "program_name": program.canonical_name if program else None,
        "university": university.canonical_name if university else None,
        "country_code": program.country_code if program else None,
        "tier": item.tier,
        "eligibility_status": item.eligibility_status,
        "fit_score": item.fit_score,
        "reason_codes": item.reason_codes,
        "concerns": item.concerns,
        "missing_information": item.missing_information,
    }


def run_out(db: Session, run: RecommendationRun) -> dict:
    items = list(db.scalars(select(RecommendationItem)
                            .where(RecommendationItem.run_id == run.id)
                            .order_by(RecommendationItem.fit_score.desc().nulls_last())).all())
    by_tier: dict[str, list] = {"ambitious": [], "target": [], "safer_fit": []}
    excluded_count = 0
    for item in items:
        if item.tier is None:
            excluded_count += 1
            continue
        by_tier.setdefault(item.tier, []).append(_item_out(db, item))
    return {
        "run_id": run.id,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "status": run.status,
        "ruleset_version": _ruleset_version(db, run),
        "tiers": by_tier,
        "excluded_count": excluded_count,
        "data_warnings": run.warning_summary or [],
        "result_summary": run.result_summary,
    }


def _ruleset_version(db: Session, run: RecommendationRun) -> str | None:
    ruleset = db.get(RecommendationRuleset, run.ruleset_id)
    return ruleset.version if ruleset else None


def list_runs(db: Session, user) -> list[dict]:
    runs = db.scalars(select(RecommendationRun).where(RecommendationRun.user_id == user.id)
                      .order_by(RecommendationRun.created_at.desc())).all()
    return [{"run_id": r.id, "created_at": r.created_at.isoformat() if r.created_at else None,
             "status": r.status, "result_summary": r.result_summary,
             "ruleset_version": _ruleset_version(db, r)} for r in runs]


def _owned_run(db: Session, user, run_id: uuid.UUID) -> RecommendationRun:
    run = db.get(RecommendationRun, run_id)
    if run is None or run.user_id != user.id:
        raise ApiError(404, "NOT_FOUND", "Recommendation run not found.")
    return run


def get_run(db: Session, user, run_id: uuid.UUID) -> dict:
    return run_out(db, _owned_run(db, user, run_id))


def explanations(db: Session, user, run_id: uuid.UUID) -> dict:
    run = _owned_run(db, user, run_id)
    items = db.scalars(select(RecommendationItem).where(RecommendationItem.run_id == run.id)
                       .order_by(RecommendationItem.fit_score.desc().nulls_last())).all()
    out = []
    for item in items:
        evaluations = db.scalars(select(RequirementEvaluation)
                                 .where(RequirementEvaluation.recommendation_item_id == item.id)).all()
        entry = _item_out(db, item)
        entry["score_breakdown"] = item.score_breakdown
        entry["why"] = {
            "reasons": item.reason_codes,
            "concerns": item.concerns,
            "missing_information": item.missing_information,
            "hard_constraint_status": ("excluded" if item.tier is None else "passed"),
            "requirement_outcomes": [
                {"requirement_id": e.admission_requirement_id, "status": e.status,
                 "applicant_value": e.applicant_value_json, "expected": e.expected_value_json,
                 "explanation": e.explanation} for e in evaluations],
        }
        out.append(entry)
    return {"run_id": run.id, "ruleset_version": _ruleset_version(db, run),
            "items": out, "data_warnings": run.warning_summary or []}


def refresh_run(db: Session, user, profile, run_id: uuid.UUID):
    previous = _owned_run(db, user, run_id)
    previous_filters = (previous.profile_snapshot or {}).get("filters") or {}
    return create_run(db, user, profile, previous_filters, None)
