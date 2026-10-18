"""Cost estimates, scholarships/funding and loan/ROI scenario endpoints (§5.7/§5.8)."""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field as PydField
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.permissions import get_current_user, get_optional_user
from app.db.session import get_db
from app.models import User
from app.services import costs, finance, funding, profiles as profile_service

router = APIRouter(tags=["finance"])


# ------------------------------------------------------------ cost estimates

class CostEstimateIn(BaseModel):
    program_id: uuid.UUID
    scenario: str = "base"
    currency: str | None = PydField(default=None, min_length=3, max_length=3)
    save: bool = False
    name: str | None = PydField(default=None, max_length=160)
    funding_amount: Decimal | None = PydField(default=None, ge=0)
    funding_currency: str | None = PydField(default=None, min_length=3, max_length=3)


@router.post("/cost-estimates")
async def create_cost_estimate(payload: CostEstimateIn,
                               db: Session = Depends(get_db),
                               user: User | None = Depends(get_optional_user)):
    if payload.save:
        if user is None:
            raise ApiError(401, "UNAUTHENTICATED", "Authentication required to save scenarios.")
        return costs.save_scenario(db, user, payload.model_dump())
    return costs.calculate(db, program_id=payload.program_id, scenario=payload.scenario,
                           currency=payload.currency,
                           funding_amount=payload.funding_amount,
                           funding_currency=payload.funding_currency)


@router.get("/programs/{program_id}/cost-estimates")
async def program_costs(program_id: uuid.UUID, db: Session = Depends(get_db)):
    return costs.program_cost_facts(db, program_id)


# -------------------------------------------------------------- scholarships

@router.get("/scholarships")
async def search_scholarships(country: str | None = Query(None, min_length=2, max_length=2),
                              q: str | None = Query(None, max_length=200),
                              page: int = Query(1, ge=1),
                              page_size: int = Query(20, ge=1, le=100),
                              db: Session = Depends(get_db)):
    return funding.search_scholarships(db, country=country, q=q, page=page, page_size=page_size)


@router.get("/scholarships/{scholarship_id}")
async def get_scholarship(scholarship_id: uuid.UUID, db: Session = Depends(get_db)):
    return funding.get_scholarship(db, scholarship_id)


@router.post("/scholarships/matches")
async def match_scholarships(db: Session = Depends(get_db),
                             user: User = Depends(get_current_user)):
    profile = profile_service.current_profile(db, user)
    return funding.match_scholarships(db, profile)


@router.get("/funding-opportunities")
async def search_funding(opportunity_type: str | None = Query(None),
                         country: str | None = Query(None, min_length=2, max_length=2),
                         q: str | None = Query(None, max_length=200),
                         page: int = Query(1, ge=1),
                         page_size: int = Query(20, ge=1, le=100),
                         db: Session = Depends(get_db)):
    return funding.search_funding(db, opportunity_type=opportunity_type, country=country,
                                  q=q, page=page, page_size=page_size)


@router.get("/funding-opportunities/{opportunity_id}")
async def get_funding(opportunity_id: uuid.UUID, db: Session = Depends(get_db)):
    return funding.get_funding(db, opportunity_id)


# ---------------------------------------------------------------- loans/ROI

class LoanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = PydField(min_length=1, max_length=160)
    principal_amount: Decimal = PydField(gt=0)
    currency: str = PydField(min_length=3, max_length=3)
    annual_interest_rate: Decimal = PydField(ge=0, le=100)
    tenure_months: int = PydField(ge=1, le=480)
    moratorium_months: int = PydField(default=0, ge=0, le=120)
    interest_during_moratorium: str = "none"
    repayment_method: str = "equal_emi"


class RoiIn(BaseModel):
    name: str = PydField(min_length=1, max_length=160)
    program_id: uuid.UUID | None = None
    currency: str = PydField(min_length=3, max_length=3)
    education_cost: Decimal | None = PydField(default=None, ge=0)
    expected_annual_income: Decimal | None = PydField(default=None, ge=0)
    employment_delay_months: int = PydField(default=0, ge=0, le=120)
    annual_expenses: Decimal | None = PydField(default=None, ge=0)
    discount_rate: Decimal | None = PydField(default=None, ge=0, le=100)
    assumptions: dict = PydField(default_factory=dict)


@router.post("/loan-scenarios", status_code=201)
async def create_loan(payload: LoanIn, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    return finance.create_loan(db, user, payload)


@router.get("/loan-scenarios")
async def list_loans(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"items": finance.list_loans(db, user)}


@router.get("/loan-scenarios/{scenario_id}")
async def get_loan(scenario_id: uuid.UUID, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    return finance.get_loan(db, user, scenario_id)


@router.delete("/loan-scenarios/{scenario_id}", status_code=204)
async def delete_loan(scenario_id: uuid.UUID, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    finance.delete_loan(db, user, scenario_id)


@router.post("/roi-scenarios", status_code=201)
async def create_roi(payload: RoiIn, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    return finance.create_roi(db, user, payload)


@router.get("/roi-scenarios")
async def list_roi(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"items": finance.list_roi(db, user)}


@router.get("/roi-scenarios/{scenario_id}")
async def get_roi(scenario_id: uuid.UUID, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    return finance.get_roi(db, user, scenario_id)


@router.delete("/roi-scenarios/{scenario_id}", status_code=204)
async def delete_roi(scenario_id: uuid.UUID, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    finance.delete_roi(db, user, scenario_id)
