"""Loan and ROI scenario calculations (§5.7/§5.8).

Both are explicit user-driven scenarios with disclosed assumptions, not advice.
Loan math uses a documented equal-EMI model with moratorium handling; ROI returns
payback only when the surplus is positive, otherwise it reports why rather than a
meaningless number. Neither ever implies approval or a guaranteed outcome.
"""
from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import InterestDuringMoratorium, LoanScenario, RepaymentMethod, RoiScenario, User

CALC_VERSION = "loan-v1"
ROI_VERSION = "roi-v1"
DISCLAIMER = ("Scenario estimate for planning only. Not a loan offer, approval, or "
              "personalised regulated financial advice; actual terms depend on the lender.")
ROI_DISCLAIMER = ("Scenario based on your stated assumptions and scoped evidence, not a "
                  "promise of income or payback. Outcomes vary by cohort and market.")


def _q(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def compute_emi(principal: Decimal, annual_rate_pct: Decimal, tenure_months: int,
                moratorium_months: int, moratorium_mode: str) -> dict:
    """Equal-EMI amortisation with an optional moratorium.

    - ``capitalize``: moratorium interest is added to principal before amortising.
    - ``simple_interest``: interest accrued during moratorium is charged as a lump
      on top of the amortised total (principal itself unchanged).
    - ``none``: no interest accrues during moratorium; tenure just starts later.
    """
    monthly_rate = annual_rate_pct / Decimal(100) / Decimal(12)
    repay_months = tenure_months - moratorium_months
    if repay_months <= 0:
        raise ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       [{"field": "tenure_months", "code": "invalid_range",
                         "message": "Repayment period must be longer than the moratorium."}])

    original_principal = principal
    moratorium_interest = Decimal(0)
    if moratorium_months and moratorium_mode == InterestDuringMoratorium.capitalize.value:
        moratorium_interest = principal * monthly_rate * moratorium_months
        principal += moratorium_interest
    elif moratorium_months and moratorium_mode == InterestDuringMoratorium.simple_interest.value:
        moratorium_interest = principal * monthly_rate * moratorium_months

    if monthly_rate == 0:
        emi = principal / repay_months
    else:
        factor = (Decimal(1) + monthly_rate) ** (-repay_months)
        emi = principal * monthly_rate / (1 - factor)

    emi = _q(emi)

    # monthly amortisation schedule (contract §5.7: EMI/payment schedule);
    # the final payment clears rounding drift on the balance
    schedule = []
    balance = principal
    for m in range(1, repay_months + 1):
        interest = _q(balance * monthly_rate)
        princ = balance if m == repay_months else _q(emi - interest)
        if princ > balance:
            princ = balance
        balance -= princ
        schedule.append({"month": m, "emi": _q(emi if m < repay_months else princ + interest),
                         "interest": interest, "principal": princ,
                         "closing_balance": _q(max(balance, Decimal(0)))})

    # capitalize adds MI to the balance (the schedule pays it back), so only
    # simple-interest MI is an extra lump on top of the schedule
    extra = (moratorium_interest
             if moratorium_mode == InterestDuringMoratorium.simple_interest.value
             else Decimal(0))
    total_paid = sum((row["emi"] for row in schedule), Decimal(0)) + extra
    return {
        "emi": emi,
        "repayment_months": repay_months,
        "principal_after_moratorium": _q(principal),
        "moratorium_interest": _q(moratorium_interest),
        "total_interest": _q(total_paid - original_principal),
        "total_payable": _q(total_paid),
        "schedule": schedule,
    }


def create_loan(db: Session, user: User, payload) -> dict:
    if payload.tenure_months <= 0:
        raise ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       [{"field": "tenure_months", "code": "out_of_range",
                         "message": "tenure_months must be positive."}])
    if payload.repayment_method != RepaymentMethod.equal_emi.value:
        raise ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                       [{"field": "repayment_method", "code": "invalid_choice",
                         "message": "Only equal_emi is modelled."}])
    result = compute_emi(payload.principal_amount, payload.annual_interest_rate,
                         payload.tenure_months, payload.moratorium_months,
                         payload.interest_during_moratorium)
    row = LoanScenario(
        user_id=user.id, name=payload.name,
        principal_amount=payload.principal_amount, currency=payload.currency,
        annual_interest_rate=payload.annual_interest_rate,
        tenure_months=payload.tenure_months, moratorium_months=payload.moratorium_months,
        interest_during_moratorium=payload.interest_during_moratorium,
        repayment_method=payload.repayment_method,
        estimated_emi=result["emi"], total_interest=result["total_interest"],
        calculation_version=CALC_VERSION,
    )
    db.add(row)
    db.flush()
    return _loan_out(row, result)


def _loan_out(row: LoanScenario, computed: dict | None = None) -> dict:
    if computed is None:
        # stored scenarios recompute the full schedule from their own inputs
        computed = compute_emi(row.principal_amount, row.annual_interest_rate,
                               row.tenure_months, row.moratorium_months,
                               row.interest_during_moratorium)
    return {
        "id": row.id, "name": row.name,
        "inputs": {"principal_amount": row.principal_amount, "currency": row.currency,
                   "annual_interest_rate": row.annual_interest_rate,
                   "tenure_months": row.tenure_months,
                   "moratorium_months": row.moratorium_months,
                   "interest_during_moratorium": row.interest_during_moratorium,
                   "repayment_method": row.repayment_method},
        "results": computed,
        "interest_method": "monthly reducing balance, equal EMI",
        "assumptions": ["fixed interest rate for the full tenure",
                        "moratorium handled as disclosed in inputs",
                        "fees and prepayment charges excluded"],
        "calculation_version": row.calculation_version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "disclaimer": DISCLAIMER,
    }


def list_loans(db: Session, user: User) -> list[dict]:
    rows = db.scalars(select(LoanScenario).where(LoanScenario.user_id == user.id)
                      .order_by(LoanScenario.created_at.desc())).all()
    return [_loan_out(r) for r in rows]


def get_loan(db: Session, user: User, scenario_id: uuid.UUID) -> dict:
    row = _owned(db, user, LoanScenario, scenario_id)
    return _loan_out(row)


def delete_loan(db: Session, user: User, scenario_id: uuid.UUID) -> None:
    _remove(db, user, LoanScenario, scenario_id)


# ------------------------------------------------------------------------- ROI

def compute_roi(payload) -> dict:
    """Payback from education cost vs net annual surplus after an employment delay.

    Returns ``payback_months = None`` with ``payback_status`` explaining why when
    the surplus is non-positive or inputs are missing — never a fake number.
    """
    cost = payload.education_cost
    income = payload.expected_annual_income
    expenses = payload.annual_expenses or Decimal(0)
    delay = payload.employment_delay_months or 0

    warnings = []
    if cost is None or income is None:
        return {"payback_months": None, "payback_status": "unknown",
                "warnings": ["education_cost_or_income_missing"]}

    surplus_monthly = (Decimal(income) - Decimal(expenses)) / Decimal(12)
    if surplus_monthly <= 0:
        return {"payback_months": None, "payback_status": "no_positive_surplus",
                "warnings": ["annual expenses meet or exceed expected income"]}

    payback = _q(Decimal(cost) / surplus_monthly, "1")
    payback_months = int(payback) + delay
    horizon_months = 240
    if payback_months > horizon_months:
        warnings.append(f"payback exceeds {horizon_months // 12} years on these assumptions")

    net_present = None
    if payload.discount_rate is not None:
        r = Decimal(payload.discount_rate) / Decimal(100)
        # simple discounted payback check: discount annual surplus over years
        years = Decimal(payback_months) / Decimal(12)
        discounted = Decimal(0)
        for y in range(1, int(years) + 2):
            discounted += (Decimal(income) - Decimal(expenses)) / ((Decimal(1) + r) ** y)
        net_present = _q(discounted - Decimal(cost))
        if net_present < 0:
            warnings.append("discounted surplus does not recover cost within the payback window")

    return {
        "payback_months": payback_months,
        "payback_status": "estimated",
        "monthly_surplus": _q(surplus_monthly),
        "discounted_net_present_value": net_present,
        "warnings": warnings,
    }


def create_roi(db: Session, user: User, payload) -> dict:
    result = compute_roi(payload)
    row = RoiScenario(
        user_id=user.id, program_id=payload.program_id, name=payload.name,
        currency=payload.currency, education_cost=payload.education_cost,
        expected_annual_income=payload.expected_annual_income,
        employment_delay_months=payload.employment_delay_months,
        annual_expenses=payload.annual_expenses, discount_rate=payload.discount_rate,
        assumptions=payload.assumptions, payback_months=result["payback_months"],
        calculation_version=ROI_VERSION,
    )
    db.add(row)
    db.flush()
    return _roi_out(row, result)


def _roi_out(row: RoiScenario, computed: dict | None = None) -> dict:
    out = {
        "id": row.id, "name": row.name, "program_id": row.program_id,
        "currency": row.currency,
        "scope": "program" if row.program_id else "user_scenario",
        "input_provenance": "user_entered_assumptions",  # not sourced outcome evidence
        "inputs": {"education_cost": row.education_cost,
                   "expected_annual_income": row.expected_annual_income,
                   "employment_delay_months": row.employment_delay_months,
                   "annual_expenses": row.annual_expenses,
                   "discount_rate": row.discount_rate},
        "assumptions": row.assumptions or {},
        "calculation_version": row.calculation_version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "disclaimer": ROI_DISCLAIMER,
    }
    if computed:
        out["results"] = computed
    else:
        # stored scenarios recompute results from their own inputs so warnings survive reads
        computed = compute_roi(_roi_inputs(row))
        out["results"] = computed
    return out


def _roi_inputs(row: RoiScenario):
    from types import SimpleNamespace
    return SimpleNamespace(education_cost=row.education_cost,
                           expected_annual_income=row.expected_annual_income,
                           annual_expenses=row.annual_expenses,
                           employment_delay_months=row.employment_delay_months,
                           discount_rate=row.discount_rate)


def list_roi(db: Session, user: User) -> list[dict]:
    rows = db.scalars(select(RoiScenario).where(RoiScenario.user_id == user.id)
                      .order_by(RoiScenario.created_at.desc())).all()
    return [_roi_out(r) for r in rows]


def get_roi(db: Session, user: User, scenario_id: uuid.UUID) -> dict:
    return _roi_out(_owned(db, user, RoiScenario, scenario_id))


def delete_roi(db: Session, user: User, scenario_id: uuid.UUID) -> None:
    _remove(db, user, RoiScenario, scenario_id)


# -------------------------------------------------------------------- ownership

def _owned(db: Session, user: User, model, scenario_id: uuid.UUID):
    row = db.get(model, scenario_id)
    if row is None or row.user_id != user.id:
        raise ApiError(404, "NOT_FOUND", "Scenario not found.")
    return row


def _remove(db: Session, user: User, model, scenario_id: uuid.UUID) -> None:
    db.delete(_owned(db, user, model, scenario_id))
    db.flush()
