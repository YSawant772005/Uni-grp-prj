"""Cost estimate calculation (§5.7).

Line items keep amount + currency + period + status + source. Scenarios
(low/base/high) use the published ranges where they exist; a component without
data stays out of the total and is listed explicitly as ``unavailable`` — never 0.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.services import catalog
from app.models import (
    Campus,
    City,
    CostScenario,
    CostScenarioItem,
    FactRecord,
    LivingCostFact,
    Program,
    ProgramFee,
    User,
)
from app.services.fx import convert

CALC_VERSION = "cost-v1"
SCENARIOS = ("low", "base", "high")

# components the product promises to model; absence is shown, not hidden
EXPECTED_COMPONENTS = {
    "tuition": "Tuition", "mandatory_fee": "Mandatory academic fees", "living": "Living costs",
    "insurance": "Health insurance", "travel_visa": "Travel and visa",
    "setup": "Setup and deposit",
}


def _money(value, currency, period, status, source=None, note=None) -> dict:
    return {"value": value, "currency": currency, "period": period, "status": status,
            "source": source, "note": note}


def _tuition_items(db: Session, program: Program) -> dict:
    fees = db.scalars(select(ProgramFee).where(
        ProgramFee.program_id == program.id,
        ProgramFee.fee_type.in_(("tuition", "mandatory_fee"))).order_by(ProgramFee.id)).all()
    items: dict[str, dict] = {}
    months = program.duration_max_months
    # Academic years and student categories are alternatives, not additive fees.
    for kind in ("tuition", "mandatory_fee"):
        rows = [fee for fee in fees if fee.fee_type == kind]
        if not rows:
            continue
        latest_year = max((fee.academic_year or "" for fee in rows), default="")
        rows = [fee for fee in rows if (fee.academic_year or "") == latest_year]
        if len({fee.student_category for fee in rows if fee.amount is not None}) > 1:
            items[kind] = _money(None, None, None, "unavailable",
                note="Different student-category fees are published; an applicable category is required.")
            continue
        if len({fee.currency for fee in rows if fee.amount is not None}) > 1:
            items[kind] = _money(None, None, None, "unavailable", note="Fee components use different currencies.")
            continue
        total, status, unknown, notes = Decimal(0), "verified", False, []
        currency = next((fee.currency for fee in rows if fee.currency), None)
        for fee in rows:
            fact = db.get(FactRecord, fee.fact_id) if fee.fact_id else None
            evidence_status = fact.current_status if fact else fee.status
            if fee.amount is None or evidence_status in ("candidate", "in_review", "conflicted", "stale", "rejected", "unavailable", "superseded"):
                unknown = True
                status = evidence_status if evidence_status in ("conflicted", "stale") else "unavailable"
                notes.append("A fee is missing or its source evidence needs review; excluded from totals.")
                continue
            if fee.period in ("semester", "academic_year", "month", "year") and not months:
                unknown = True
                notes.append("Program duration is unknown; a recurring fee cannot establish the full-degree cost.")
                continue
            if fee.period in ("other", None):
                unknown = True
                notes.append("The fee time basis is insufficient for a full-degree calculation.")
                continue
            multiplier = {"semester": Decimal((months + 5) // 6) if months else 1,
                          "academic_year": Decimal(months) / 12 if months else 1,
                          "year": Decimal(months) / 12 if months else 1,
                          "month": months or 1}.get(fee.period, 1)
            total += fee.amount * multiplier
            if fee.period in ("semester", "academic_year", "year", "month"):
                notes.append(f"Assumes the published {fee.period} fee repeats over {months} months.")
            if evidence_status != "verified" and status == "verified":
                status = evidence_status
        items[kind] = _money(None if unknown else total.quantize(Decimal("0.01")), currency,
                             "full_program", status if not unknown or status in ("conflicted", "stale") else "unavailable",
                             note=" ".join(dict.fromkeys(notes)) or None)

    return items


def _living_items(db: Session, program: Program, scenario: str) -> dict:
    if not program.campus_id:
        return {"living": _money(None, None, "month", "unavailable",
                                note="Program city unknown; living costs cannot be attached.")}
    campus = db.get(Campus, program.campus_id)
    city = db.get(City, campus.city_id) if campus else None
    if city is None:
        return {"living": _money(None, None, "month", "unavailable",
                                note="Program city unknown; living costs cannot be attached.")}
    rows = db.scalars(select(LivingCostFact).where(LivingCostFact.city_id == city.id)
                      .order_by(LivingCostFact.cost_category)).all()
    if not rows:
        return {"living": _money(None, None, "month", "unavailable",
                                note=f"No living-cost data for {city.name}.")}
    column = {"low": "amount_min", "base": "amount_typical", "high": "amount_max"}[scenario]
    if any(getattr(r, column) is None for r in rows):
        return {"living": _money(None, None, "month", "unavailable",
                                note=f"Incomplete living-cost range for {city.name}.")}
    currencies = {r.currency for r in rows}
    months = program.duration_max_months or 0
    if len(currencies) != 1:
        return {"living": _money(None, None, "month", "unavailable",
                                note="Living-cost categories use mixed currencies.")}
    monthly = sum(Decimal(getattr(r, column)) for r in rows)
    total = (monthly * months).quantize(Decimal("0.01")) if months else None
    return {"living": _money(total, currencies.pop(), "full_program", "estimated",
                             note=f"{scenario} scenario: sum of {len(rows)} categories "
                                  f"for {city.name}, {months} months.")}


def _unavailable_components(have: set[str]) -> list[dict]:
    missing = []
    for key, label in EXPECTED_COMPONENTS.items():
        if key in have:
            continue
        missing.append({"cost_type": key, "label": label, "amount": None,
                        "currency": None, "period": None, "status": "unavailable",
                        "note": f"No {label.lower()} data for this program; excluded from "
                                f"totals rather than counted as zero."})
    return missing


def _convert(items: list[dict], target: str, db: Session, warnings: list[str]) -> None:
    for item in items:
        if item["amount"] is None or target is None or item["currency"] is None:
            continue
        if item["currency"] == target:
            continue
        conv = convert(db, item["amount"], item["currency"], target)
        if conv is None:
            warnings.append(f"no_fx_rate_{item['currency']}_to_{target}")
            item["note"] = (item["note"] or "") + f" Not converted: no {target} rate on file."
            continue
        item["amount"] = conv.amount
        item["converted_from"] = item["currency"]
        item["currency"] = target
        item["rate"] = {"value": conv.rate, "date": conv.rate_date.isoformat()
                        if conv.rate_date else None, "source": conv.rate_source}
        item["status"] = "estimated"


def calculate(db: Session, *, program_id: uuid.UUID, scenario: str = "base",
              currency: str | None = None, funding_amount: Decimal | None = None,
              funding_currency: str | None = None) -> dict:
    if scenario not in SCENARIOS:
        raise ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       [{"field": "scenario", "code": "invalid_choice",
                         "message": f"scenario must be one of {', '.join(SCENARIOS)}."}])
    program = db.get(Program, program_id)
    if program is None or not catalog.student_visible_program(db, program):
        raise ApiError(404, "NOT_FOUND", "Program not found.")

    warnings: list[str] = []
    components = _tuition_items(db, program)
    components.update(_living_items(db, program, scenario))

    items = []
    for key, label in EXPECTED_COMPONENTS.items():
        if key in components:
            c = components[key]
            items.append({"cost_type": key, "label": label, "amount": c["value"],
                          "currency": c["currency"], "period": c["period"],
                          "status": c["status"], "note": c.get("note")})
    items.extend(_unavailable_components(set(components)))

    target = currency or next((i["currency"] for i in items if i["currency"]), None)
    _convert(items, target, db, warnings)

    known = [i for i in items if i["amount"] is not None and i["currency"] == target]
    unknown = [i for i in items if i["amount"] is None]
    for item in unknown:
        if "zero" not in (item.get("note") or ""):
            item["note"] = ((item.get("note") or "")
                            + " Unknown costs are excluded from totals and never counted as zero.").strip()
    total = sum(i["amount"] for i in known) if known else None
    if unknown:
        warnings.append("components_unavailable:" + ",".join(i["cost_type"] for i in unknown))

    funding_gap = None
    if funding_amount is not None and total is not None and target:
        converted = funding_amount
        if funding_currency and funding_currency != target:
            conv = convert(db, funding_amount, funding_currency, target)
            if conv is None:
                warnings.append(f"no_fx_rate_{funding_currency}_to_{target}")
                converted = None
            else:
                converted = conv.amount
        if converted is not None:
            funding_gap = total - converted

    return {
        "program_id": program.id,
        "scenario": scenario,
        "currency": target,
        "items": items,
        "total": total,
        "total_status": "estimated" if total is not None else "unavailable",
        "funding_amount": funding_amount,
        "funding_currency": funding_currency,
        "funding_gap": funding_gap,
        "assumptions": {
            "scenario": scenario,
            "tuition_period": "full_program" if program.duration_max_months else None,
            "duration_months": program.duration_max_months,
            "currency_conversion": "fixed dated seed reference rates" if currency else None,
        },
        "calculation_version": CALC_VERSION,
        "data_warnings": sorted(set(warnings)),
    }


def save_scenario(db: Session, user: User, payload: dict) -> dict:
    program_id = payload.get("program_id")
    scenario = calculate(db, program_id=uuid.UUID(str(program_id)),
                         scenario=payload.get("scenario", "base"),
                         currency=payload.get("currency"))
    row = CostScenario(
        user_id=user.id, program_id=scenario["program_id"],
        name=payload.get("name") or f"{scenario['scenario']} estimate",
        currency=scenario["currency"] or "EUR",
        scenario_type=scenario["scenario"],
        assumptions=scenario["assumptions"],
        total_amount=scenario["total"],
        funding_amount=payload.get("funding_amount"),
        funding_gap=scenario["funding_gap"],
        calculation_version=CALC_VERSION,
    )
    db.add(row)
    db.flush()
    for item in scenario["items"]:
        db.add(CostScenarioItem(
            scenario_id=row.id, cost_type=item["cost_type"], amount=item["amount"],
            currency=item["currency"] or row.currency,
            period=item["period"] or "other",  # column is NOT NULL; unavailable items keep status/note
            status=item["status"], assumption_note=item.get("note")))
    db.flush()
    return {"scenario_id": row.id, **scenario}


def program_cost_facts(db: Session, program_id: uuid.UUID) -> dict:
    """GET /programs/{id}/cost-estimates — facts for all three scenarios, no saving."""
    program = db.get(Program, program_id)
    if program is None or not catalog.student_visible_program(db, program):
        raise ApiError(404, "NOT_FOUND", "Program not found.")
    return {"program_id": program.id,
            "scenarios": {s: calculate(db, program_id=program_id, scenario=s)
                          for s in SCENARIOS}}
