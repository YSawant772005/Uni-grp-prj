"""Student profile and onboarding schemas."""
from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CountryPreferenceIn(BaseModel):
    country_code: str = Field(min_length=2, max_length=2)
    preference_rank: int | None = Field(default=None, ge=1, le=50)
    is_mandatory: bool = False


class PriorityIn(BaseModel):
    priority_key: str
    weight: int = Field(ge=1, le=5)


class ProfileIn(BaseModel):
    """PUT body: every omitted optional field is reset (documented PUT semantics)."""

    intended_degree_level: str = "masters"
    field: str | None = None
    country_mode: str | None = None
    risk_tolerance: str | None = None
    academic_degree: str | None = None
    academic_major: str | None = None
    institution_name: str | None = None
    grade_value: Decimal | None = None
    grade_scale_min: Decimal | None = None
    grade_scale_max: Decimal | None = None
    grade_system: str | None = None
    graduation_status: str | None = None
    graduation_year: int | None = Field(default=None, ge=1950, le=2100)
    backlog_count: int | None = Field(default=None, ge=0)
    english_test_status: str | None = None
    english_test_type: str | None = None
    english_test_overall: Decimal | None = None
    english_test_component_scores: dict | None = None
    other_test_scores: dict | None = None
    work_experience_months: int | None = Field(default=None, ge=0)
    projects_summary: str | None = Field(default=None, max_length=4000)
    career_goal: str | None = Field(default=None, max_length=2000)
    budget_amount: Decimal | None = Field(default=None, gt=0)
    budget_currency: str | None = Field(default=None, min_length=3, max_length=3)
    budget_basis: str | None = None
    target_intake_year: int | None = Field(default=None, ge=2000, le=2100)
    target_intake_term: str | None = None
    country_preferences: list[CountryPreferenceIn] = []
    priorities: list[PriorityIn] = []


class ProfilePatchIn(ProfileIn):
    """PATCH body: only fields explicitly present are updated."""

    intended_degree_level: str | None = None
    country_preferences: list[CountryPreferenceIn] | None = None
    priorities: list[PriorityIn] | None = None


class OnboardingCompleteIn(BaseModel):
    """The 8 documented quick-profile questions (API_Contract §5.3)."""

    intended_degree_level: str
    field: str
    country_preferences: list[CountryPreferenceIn] = Field(min_length=1)
    academic_degree: str
    institution_name: str
    grade_value: Decimal
    grade_scale_min: Decimal
    grade_scale_max: Decimal
    grade_system: str
    graduation_status: str
    graduation_year: int = Field(ge=1950, le=2100)
    english_test_status: str
    english_test_type: str | None = None
    english_test_overall: Decimal | None = None
    budget_amount: Decimal = Field(gt=0)
    budget_currency: str = Field(min_length=3, max_length=3)
    budget_basis: str
    target_intake_year: int = Field(ge=2000, le=2100)
    target_intake_term: str
    risk_tolerance: str | None = None


class CompletenessItem(BaseModel):
    key: str
    label: str
    required: bool
    complete: bool


class CompletenessOut(BaseModel):
    required_complete: bool
    optional_complete: bool
    percentage: int
    items: list[CompletenessItem]


class CountryPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    country_code: str
    preference_rank: int
    is_mandatory: bool


class PriorityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    priority_key: str
    weight: int


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    intended_degree_level: str
    field_key: str | None = None
    country_mode: str | None = None
    risk_tolerance: str | None = None
    academic_degree: str | None = None
    academic_major: str | None = None
    institution_name: str | None = None
    grade_value: Decimal | None = None
    grade_scale_min: Decimal | None = None
    grade_scale_max: Decimal | None = None
    grade_system: str | None = None
    graduation_status: str | None = None
    graduation_year: int | None = None
    backlog_count: int | None = None
    english_test_status: str | None = None
    english_test_type: str | None = None
    english_test_overall: Decimal | None = None
    english_test_component_scores: dict | None = None
    other_test_scores: dict | None = None
    work_experience_months: int | None = None
    projects_summary: str | None = None
    career_goal: str | None = None
    budget_amount: Decimal | None = None
    budget_currency: str | None = None
    budget_basis: str | None = None
    target_intake_year: int | None = None
    target_intake_term: str | None = None
    profile_completed_at: str | None = None
    country_preferences: list[CountryPreferenceOut] = []
    priorities: list[PriorityOut] = []
