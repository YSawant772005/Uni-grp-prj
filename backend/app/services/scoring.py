"""Explainable fit scoring and shortlist tiering (plan §4.4/§4.5).

A fit score answers "how well does this suit the student's goals and constraints" —
never "chance of admission". Dimensions whose evidence is missing are returned as
``None``; weights are renormalised over the dimensions that DO have evidence and the
omitted ones are surfaced as data warnings. No number is invented for missing data.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LivingCostFact, Program, ProgramFee
from app.services.fx import convert

DIMENSIONS = ("academic_fit", "career_fit", "affordability", "quality", "outcomes", "destination")

_RECOGNITION_SCORE = {"recognized": 1.0, "under_review": 0.6, "unknown": 0.4, "not_recognized": 0.1}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def estimate_program_cost(db: Session, program: Program) -> dict:
    """Rough total-cost estimate (tuition + living) in one currency.

    Returns amounts as ``estimated``; ``None`` where a component is unknown. Never
    substitutes zero for a missing figure.
    """
    tuition = db.scalar(
        select(ProgramFee).where(ProgramFee.program_id == program.id,
                                 ProgramFee.fee_type == "tuition",
                                 ProgramFee.amount.is_not(None))
        .order_by(ProgramFee.academic_year.desc().nulls_last(), ProgramFee.id).limit(1))
    # living cost via the program's campus city
    city_id = None
    if program.campus_id:
        from app.models import Campus
        campus = db.get(Campus, program.campus_id)
        city_id = campus.city_id if campus else None
    months = program.duration_max_months or 0
    years = Decimal(months) / Decimal(12) if months else None

    tuition_total = None
    tuition_currency = tuition.currency if tuition else None
    if tuition and years:
        tuition_total = (Decimal(tuition.amount) * years).quantize(Decimal("0.01"))

    living_total = None
    living_currency = None
    if city_id and months:
        rows = db.scalars(select(LivingCostFact).where(LivingCostFact.city_id == city_id)
                          .order_by(LivingCostFact.id)).all()
        if rows and all(r.amount_typical is not None for r in rows):
            currencies = {r.currency for r in rows}
            if len(currencies) == 1:
                living_currency = currencies.pop()
                monthly = sum(Decimal(r.amount_typical) for r in rows)
                living_total = (monthly * months).quantize(Decimal("0.01"))

    return {
        "tuition_total": tuition_total, "tuition_currency": tuition_currency,
        "tuition_period_years": float(years) if years else None,
        "living_total": living_total, "living_currency": living_currency,
        "months": months,
        "tuition_status": tuition.status if tuition else "unavailable",
    }


def total_in_currency(db: Session, cost: dict, target_currency: str | None):
    """Total tuition + living in ``target_currency``; returns (amount|None, notes).

    Strict: if ANY component is unknown or unconvertible, the total is ``None`` —
    a partial sum would silently treat missing tuition as zero.
    """
    if target_currency is None:
        return None, ["no_budget_currency"]
    notes, parts = [], []
    for key, ckey in (("tuition_total", "tuition_currency"), ("living_total", "living_currency")):
        amount, cur = cost.get(key), cost.get(ckey)
        if amount is None:
            notes.append(f"{key.split('_')[0]}_unknown")
            continue
        conv = convert(db, amount, cur, target_currency)
        if conv is None:
            notes.append(f"no_fx_rate_{cur}")
            continue
        parts.append(conv.amount)
    if notes or not parts:
        return None, notes + (["no_cost_components"] if not parts else [])
    return sum(parts), []


def _academic(profile, program) -> tuple[float | None, str]:
    if profile.grade_value is None or not profile.grade_scale_max:
        return None, "No grade recorded; academic fit not scored."
    ratio = _clamp(float(Decimal(profile.grade_value) / Decimal(profile.grade_scale_max)))
    return ratio, f"Grade ratio {ratio:.2f} against program '{program.canonical_name}'."


def _career(profile, program) -> tuple[float | None, str]:
    if profile.field_id is None:
        return None, "No field of study recorded; career fit not scored."
    if profile.field_id == program.field_id:
        return 1.0, "Program field matches your chosen field exactly."
    return 0.5, "Program field differs from your chosen field."


def _affordability(budget_amount, budget_currency, total) -> tuple[float | None, str]:
    if budget_amount is None or budget_currency is None:
        return None, "Budget not recorded; affordability not scored."
    if total is None:
        return None, "Total cost could not be estimated in your budget currency."
    ratio = _clamp(float(Decimal(str(budget_amount)) / Decimal(str(total))))
    return ratio, f"Budget covers about {ratio:.0%} of the estimated total cost."


def _quality(recognition_status: str | None) -> tuple[float | None, str]:
    score = _RECOGNITION_SCORE.get(recognition_status, 0.4)
    return score, f"Institution recognition status '{recognition_status or 'unknown'}'."


def _outcomes(outcome_rate) -> tuple[float | None, str]:
    if outcome_rate is None:
        return None, "No scoped outcome evidence available for this program/field."
    return _clamp(float(outcome_rate) / 100.0), f"Outcome evidence rate {outcome_rate}%."


def _destination(profile, country_code) -> tuple[float | None, str]:
    prefs = profile.country_preferences or []
    if not prefs:
        return None, "No country preferences recorded; destination fit not scored."
    codes = [p.country_code for p in sorted(prefs, key=lambda p: p.preference_rank)]
    if country_code in codes:
        rank = codes.index(country_code) + 1
        return _clamp(1.2 - 0.2 * rank), f"Country is preference #{rank} in your profile."
    return 0.1, "Country is not among your preferred countries."


def score_dimensions(profile, program, *, recognition_status, outcome_rate, total_cost) -> dict:
    dims = {}
    dims["academic_fit"] = _academic(profile, program)
    dims["career_fit"] = _career(profile, program)
    dims["affordability"] = _affordability(profile.budget_amount, profile.budget_currency, total_cost)
    dims["quality"] = _quality(recognition_status)
    dims["outcomes"] = _outcomes(outcome_rate)
    dims["destination"] = _destination(profile, program.country_code)
    return dims


def combine(dimensions: dict, weights: dict) -> tuple[float | None, list[dict], list[str]]:
    """Weighted average over dimensions that have evidence; renormalise the rest."""
    breakdown, warnings = [], []
    num = den = 0.0
    for dim in DIMENSIONS:
        result, note = dimensions.get(dim, (None, "not evaluated"))
        weight = float(weights.get(dim, 0) or 0)
        if result is None:
            warnings.append(f"{dim}_unavailable")
            breakdown.append({"dimension": dim, "weight": weight, "score": None, "note": note})
            continue
        num += weight * result
        den += weight
        breakdown.append({"dimension": dim, "weight": weight, "score": round(result, 4), "note": note})
    overall = round(num / den, 4) if den > 0 else None
    return overall, breakdown, warnings


def competitiveness_tier(profile, requirement_thresholds: dict) -> str:
    """Deterministic tier from how far the student clears published thresholds.

    NOT an admission prediction. Uses only evidence: the gap between the student's
    recorded grade/english and the program's published minimums, relative to the rest
    of this run's list. A higher barrier (barely meets) -> ambitious; comfortably above
    -> safer_fit; in between -> target. Falls back to 'target' without thresholds.
    """
    gaps = []
    grade = requirement_thresholds.get("min_grade_ratio")
    if grade is not None and profile.grade_value is not None and profile.grade_scale_max:
        student = float(Decimal(profile.grade_value) / Decimal(profile.grade_scale_max))
        gaps.append(student - grade)
    english = requirement_thresholds.get("min_english")
    if english is not None and profile.english_test_overall is not None:
        gaps.append(float(Decimal(profile.english_test_overall) - Decimal(str(english))) / 3.0)
    if not gaps:
        return "target"
    margin = sum(gaps) / len(gaps)
    if margin < 0.05:
        return "ambitious"
    if margin >= 0.20:
        return "safer_fit"
    return "target"
