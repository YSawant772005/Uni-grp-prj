"""Affordability, funding, outcomes and destination facts.

Money stays explicit: amount + currency + period. An unknown amount stays NULL and is
reported as unavailable rather than being converted to zero.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPk
from app.models.enums import (
    CostCategory,
    CoverageType,
    FundingStatus,
    InterestDuringMoratorium,
    MetricKey,
    MoneyPeriod,
    OpportunityType,
    Operator,
    PopulationScope,
    RepaymentMethod,
    RecordStatus,
    RuleType,
    ScenarioType,
    enum_col,
)


class CostScenario(Base, UUIDPk, TimestampMixin):
    __tablename__ = "cost_scenarios"
    __table_args__ = (
        CheckConstraint("total_amount IS NULL OR total_amount >= 0", name="ck_cost_scenarios_total_nonnegative"),
        Index("ix_cost_scenarios_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    program_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("programs.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    scenario_type = enum_col(ScenarioType)
    assumptions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    funding_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    funding_gap: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    calculation_version: Mapped[str] = mapped_column(String(40), nullable=False)


class CostScenarioItem(Base, UUIDPk):
    __tablename__ = "cost_scenario_items"
    __table_args__ = (
        CheckConstraint("amount IS NULL OR amount >= 0", name="ck_cost_scenario_items_amount"),
        Index("ix_cost_scenario_items_scenario", "scenario_id"),
    )

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cost_scenarios.id", ondelete="CASCADE"), nullable=False
    )
    cost_type = enum_col(CostCategory)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    period = enum_col(MoneyPeriod)
    status = enum_col(RecordStatus, default=RecordStatus.unverified)
    fact_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fact_versions.id", ondelete="SET NULL")
    )
    assumption_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Scholarship(Base, UUIDPk, TimestampMixin):
    __tablename__ = "scholarships"
    __table_args__ = (Index("ix_scholarships_status", "status"),)

    name: Mapped[str] = mapped_column(String(250), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(200), nullable=False)
    official_url: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str | None] = mapped_column(String(2), ForeignKey("countries.code", ondelete="SET NULL"))
    award_type: Mapped[str | None] = mapped_column(String(60))
    amount_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    amount_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    coverage_type = enum_col(CoverageType, nullable=True)
    renewable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date)
    status = enum_col(FundingStatus, default=FundingStatus.candidate)
    fact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("fact_records.id", ondelete="SET NULL"))


class ScholarshipEligibilityRule(Base, UUIDPk, TimestampMixin):
    __tablename__ = "scholarship_eligibility_rules"

    scholarship_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("scholarships.id", ondelete="CASCADE"), nullable=False
    )
    rule_key: Mapped[str] = mapped_column(String(80), nullable=False)
    operator = enum_col(Operator)
    expected_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", default=True)
    group_key: Mapped[str | None] = mapped_column(String(60))
    source_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fact_records.id", ondelete="SET NULL")
    )


class ScholarshipProgramLink(Base):
    __tablename__ = "scholarship_program_links"

    scholarship_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("scholarships.id", ondelete="CASCADE"), primary_key=True
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("programs.id", ondelete="CASCADE"), primary_key=True
    )
    link_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="program_specific")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FundingOpportunity(Base, UUIDPk, TimestampMixin):
    __tablename__ = "funding_opportunities"
    __table_args__ = (
        CheckConstraint(
            "deadline IS NULL OR opening_date IS NULL OR opening_date <= deadline",
            name="ck_funding_opportunities_date_order",
        ),
        Index("ix_funding_opportunities_status", "status"),
    )

    name: Mapped[str] = mapped_column(String(250), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(200), nullable=False)
    opportunity_type = enum_col(OpportunityType, nullable=True)
    official_url: Mapped[str | None] = mapped_column(Text)
    eligible_countries: Mapped[dict | None] = mapped_column(JSONB)
    eligible_nationalities: Mapped[dict | None] = mapped_column(JSONB)
    study_levels: Mapped[dict | None] = mapped_column(JSONB)
    field_eligibility: Mapped[dict | None] = mapped_column(JSONB)
    award_summary: Mapped[str | None] = mapped_column(Text)
    opening_date: Mapped[date | None] = mapped_column(Date)
    deadline: Mapped[date | None] = mapped_column(Date)
    status = enum_col(FundingStatus, default=FundingStatus.candidate)
    fact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("fact_records.id", ondelete="SET NULL"))


class LoanScenario(Base, UUIDPk, TimestampMixin):
    __tablename__ = "loan_scenarios"
    __table_args__ = (
        CheckConstraint("principal_amount >= 0", name="ck_loan_scenarios_principal"),
        CheckConstraint("annual_interest_rate >= 0", name="ck_loan_scenarios_rate"),
        CheckConstraint("tenure_months > 0", name="ck_loan_scenarios_tenure"),
        CheckConstraint("moratorium_months >= 0", name="ck_loan_scenarios_moratorium"),
        Index("ix_loan_scenarios_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    principal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    annual_interest_rate: Mapped[Decimal] = mapped_column(Numeric(7, 5), nullable=False)
    tenure_months: Mapped[int] = mapped_column(Integer, nullable=False)
    moratorium_months: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    interest_during_moratorium = enum_col(
        InterestDuringMoratorium, default=InterestDuringMoratorium.simple_interest
    )
    repayment_method = enum_col(RepaymentMethod, default=RepaymentMethod.equal_emi)
    estimated_emi: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_interest: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    calculation_version: Mapped[str] = mapped_column(String(40), nullable=False)


class RoiScenario(Base, UUIDPk, TimestampMixin):
    __tablename__ = "roi_scenarios"
    __table_args__ = (
        CheckConstraint(
            "education_cost IS NULL OR education_cost >= 0", name="ck_roi_scenarios_cost_nonnegative"
        ),
        Index("ix_roi_scenarios_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    program_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("programs.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    education_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    expected_annual_income: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    employment_delay_months: Mapped[int | None] = mapped_column(Integer)
    annual_expenses: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    discount_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 5))
    assumptions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    payback_months: Mapped[int | None] = mapped_column(Integer)
    calculation_version: Mapped[str] = mapped_column(String(40), nullable=False)


class ProgramOutcomeEvidence(Base, UUIDPk, TimestampMixin):
    __tablename__ = "program_outcome_evidence"
    __table_args__ = (
        CheckConstraint("sample_size IS NULL OR sample_size >= 0", name="ck_outcome_sample_nonnegative"),
        Index("ix_outcome_evidence_metric", "metric_key"),
    )

    program_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("programs.id", ondelete="CASCADE"))
    university_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("universities.id", ondelete="CASCADE"))
    field_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("fields.id", ondelete="SET NULL"))
    country_code: Mapped[str | None] = mapped_column(String(2), ForeignKey("countries.code", ondelete="SET NULL"))
    metric_key = enum_col(MetricKey)
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    metric_unit: Mapped[str] = mapped_column(String(40), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3))
    cohort_label: Mapped[str | None] = mapped_column(String(120))
    cohort_year: Mapped[int | None] = mapped_column(SmallInteger)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    population_scope = enum_col(PopulationScope)
    methodology_note: Mapped[str | None] = mapped_column(Text)
    fact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("fact_records.id", ondelete="SET NULL"))


class LivingCostFact(Base, UUIDPk, TimestampMixin):
    __tablename__ = "living_cost_facts"
    __table_args__ = (
        CheckConstraint("amount_min IS NULL OR amount_min >= 0", name="ck_living_cost_min"),
        CheckConstraint("amount_max IS NULL OR amount_max >= 0", name="ck_living_cost_max"),
        CheckConstraint(
            "amount_min IS NULL OR amount_max IS NULL OR amount_min <= amount_max",
            name="ck_living_cost_min_max_order",
        ),
        Index("ix_living_cost_facts_city", "city_id"),
    )

    city_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cities.id", ondelete="CASCADE"), nullable=False)
    cost_category = enum_col(CostCategory)
    amount_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    amount_typical: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    amount_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    period = enum_col(MoneyPeriod, default=MoneyPeriod.month)
    student_lifestyle: Mapped[str | None] = mapped_column(String(120))
    effective_year: Mapped[int | None] = mapped_column(SmallInteger)
    fact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("fact_records.id", ondelete="SET NULL"))


class OfficialRuleResource(Base, UUIDPk, TimestampMixin):
    __tablename__ = "official_rule_resources"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_from <= effective_to",
            name="ck_official_rule_resources_effective_order",
        ),
        Index("ix_official_rule_resources_country_type", "country_code", "rule_type"),
    )

    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code"), nullable=False)
    city_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("cities.id", ondelete="SET NULL"))
    rule_type = enum_col(RuleType)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    official_url: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("fact_records.id", ondelete="SET NULL"))
