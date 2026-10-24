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
from app.models import (
    Campus,
    City,
    CostScenario,
    CostScenarioItem,
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
    months = program.duration_max_months or 0
    for fee in fees:
        key = fee.fee_type
        if fee.amount is None:
            items.setdefault(key, _money(None, None, None, "unavailable",
                                         note="No published figure in the catalogue."))
            continue
        # scale recurring periods across the program duration; one-time stays as published
        repeats, note = fee.amount, None
        if fee.period == "semester" and months:
            repeats = fee.amount * ((months + 5) // 6)
            note = f"Assumes the published per-semester fee repeats across {months} months."
        elif fee.period == "academic_year" and months:
            repeats = (fee.amount * Decimal(months) / Decimal(12)).quantize(Decimal("0.01"))
        elif fee.period == "month" and months:
            repeats = fee.amount * months
        if fee.student_category == "fictional_demo_qa":
            note = (note + " " if note else "") + "FICTIONAL DEMO tuition estimate for testing only; NOT a verified university fee."
        total = repeats
        existing = items.get(key)
        if existing and existing["value"] is not None:
            existing["value"] += total
            if fee.status == "unavailable":
                existing["status"] = "unavailable"
        else:
            items[key] = _money(total, fee.currency, "full_program", fee.status, note=note)
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
    demo_living_note = (" FICTIONAL DEMO living-cost estimate for testing only."
                        if city.slug.startswith("fictional-qa-cost-city-") else "")
    return {"living": _money(total, currencies.pop(), "full_program", "estimated",
                             note=f"{scenario} scenario: sum of {len(rows)} categories "
                                  f"for {city.name}, {months} months." + demo_living_note)}


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
    if program is None or program.publication_status != "published" or not program.is_active:
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
    if program is None or program.publication_status != "published" or not program.is_active:
        raise ApiError(404, "NOT_FOUND", "Program not found.")
    return {"program_id": program.id,
            "scenarios": {s: calculate(db, program_id=program_id, scenario=s)
                          for s in SCENARIOS}}
