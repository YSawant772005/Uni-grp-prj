"""Controlled enumerations shared across models, engines and API responses.

One convention for the whole schema: VARCHAR columns with generated CHECK
constraints (SQLAlchemy ``Enum`` with ``native_enum=False``).
"""
from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import mapped_column


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


# --- identity / profile ---
class UserStatus(StrEnum):
    active = "active"
    pending_verification = "pending_verification"
    suspended = "suspended"
    deletion_pending = "deletion_pending"
    deleted = "deleted"


class RoleKey(StrEnum):
    student = "student"
    reviewer = "reviewer"
    admin = "admin"


class DegreeLevel(StrEnum):
    bachelors = "bachelors"
    masters = "masters"
    phd = "phd"
    diploma = "diploma"
    certificate = "certificate"
    other = "other"


class GradeSystem(StrEnum):
    cgpa = "cgpa"
    percentage = "percentage"
    gpa = "gpa"
    other = "other"


class GraduationStatus(StrEnum):
    completed = "completed"
    in_progress = "in_progress"
    other = "other"


class TestStatus(StrEnum):
    not_taken = "not_taken"
    booked = "booked"
    completed = "completed"
    waived = "waived"
    unknown = "unknown"


class EnglishTestType(StrEnum):
    ielts = "ielts"
    toefl = "toefl"
    pte = "pte"
    duolingo = "duolingo"
    cambridge = "cambridge"
    other = "other"


class BudgetBasis(StrEnum):
    annual_tuition = "annual_tuition"
    annual_all_in = "annual_all_in"
    full_degree_tuition = "full_degree_tuition"
    full_degree_all_in = "full_degree_all_in"


class IntakeTerm(StrEnum):
    fall = "fall"
    spring = "spring"
    winter = "winter"
    summer = "summer"
    other = "other"


class CountryMode(StrEnum):
    specific = "specific"          # scenario A: country is a hard constraint
    considering = "considering"    # scenario B: preferred countries, open to more
    open = "open"                  # scenario C: open to recommendations


class RiskTolerance(StrEnum):
    conservative = "conservative"
    balanced = "balanced"
    ambitious = "ambitious"


class PriorityKey(StrEnum):
    cost = "cost"
    academic_fit = "academic_fit"
    career = "career"
    quality = "quality"
    destination = "destination"
    scholarship = "scholarship"


# --- reference / catalogue ---
class InstitutionType(StrEnum):
    public = "public"
    private = "private"
    non_profit = "non_profit"
    for_profit = "for_profit"
    unknown = "unknown"


class RecognitionStatus(StrEnum):
    recognized = "recognized"
    not_recognized = "not_recognized"
    under_review = "under_review"
    unknown = "unknown"


class StudyMode(StrEnum):
    full_time = "full_time"
    part_time = "part_time"
    online = "online"
    blended = "blended"
    unknown = "unknown"


class PublicationStatus(StrEnum):
    candidate = "candidate"
    published = "published"
    hidden = "hidden"
    retired = "retired"


class RecordStatus(StrEnum):
    """Lifecycle/freshness of a stored record or fact value."""
    candidate = "candidate"
    in_review = "in_review"
    verified = "verified"
    estimated = "estimated"
    unverified = "unverified"
    stale = "stale"
    conflicted = "conflicted"
    unavailable = "unavailable"
    superseded = "superseded"
    rejected = "rejected"


class IntakeStatus(StrEnum):
    candidate = "candidate"
    verified = "verified"
    closed = "closed"
    unknown = "unknown"


class RequirementType(StrEnum):
    degree = "degree"
    major = "major"
    grade = "grade"
    language_test = "language_test"
    standardized_test = "standardized_test"
    prerequisite_course = "prerequisite_course"
    work_experience = "work_experience"
    document = "document"
    other = "other"


class Operator(StrEnum):
    gte = "gte"
    gt = "gt"
    lte = "lte"
    lt = "lt"
    eq = "eq"
    in_ = "in"
    contains = "contains"
    completed_course = "completed_course"
    any_of = "any_of"
    all_of = "all_of"
    manual_review = "manual_review"


class GroupOperator(StrEnum):
    AND = "AND"
    OR = "OR"


class FeeType(StrEnum):
    tuition = "tuition"
    mandatory_fee = "mandatory_fee"
    application_fee = "application_fee"
    deposit = "deposit"
    insurance = "insurance"
    other = "other"


class MoneyPeriod(StrEnum):
    one_time = "one_time"
    semester = "semester"
    academic_year = "academic_year"
    full_program = "full_program"
    month = "month"
    year = "year"
    other = "other"


# --- provenance ---
class SourceType(StrEnum):
    official_university = "official_university"
    government = "government"
    regulator = "regulator"
    statistical = "statistical"
    licensed_aggregator = "licensed_aggregator"
    other = "other"


class AllowedUsePolicy(StrEnum):
    manual_reference = "manual_reference"
    permitted_fetch = "permitted_fetch"
    licensed_api = "licensed_api"
    public_dataset = "public_dataset"
    prohibited_automated_fetch = "prohibited_automated_fetch"
    review_required = "review_required"


class FetchStatus(StrEnum):
    queued = "queued"
    fetched = "fetched"
    http_failed = "http_failed"
    parse_failed = "parse_failed"
    skipped = "skipped"


class EntityType(StrEnum):
    university = "university"
    program = "program"
    intake = "intake"
    fee = "fee"
    requirement = "requirement"
    scholarship = "scholarship"
    city = "city"
    outcome = "outcome"
    country_rule = "country_rule"
    other = "other"


class ExtractionMethod(StrEnum):
    manual = "manual"
    parser = "parser"
    AI_assisted = "AI_assisted"
    licensed_api = "licensed_api"
    dataset = "dataset"


class EvidenceSupport(StrEnum):
    supports = "supports"
    conflicts = "conflicts"
    context = "context"


class ReviewAction(StrEnum):
    approve = "approve"
    reject = "reject"
    request_evidence = "request_evidence"
    mark_stale = "mark_stale"
    resolve_conflict = "resolve_conflict"
    reopen = "reopen"


# --- recommendations ---
class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    partial = "partial"
    failed = "failed"


class Tier(StrEnum):
    ambitious = "ambitious"
    target = "target"
    safer_fit = "safer_fit"


class EligibilityStatus(StrEnum):
    eligible = "eligible"
    conditionally_eligible = "conditionally_eligible"
    ineligible = "ineligible"
    unknown_needs_review = "unknown_needs_review"


class EvalStatus(StrEnum):
    pass_ = "pass"
    fail = "fail"
    conditional = "conditional"
    unknown = "unknown"


# --- finance ---
class ScenarioType(StrEnum):
    low = "low"
    base = "base"
    high = "high"
    custom = "custom"


class CostType(StrEnum):
    tuition = "tuition"
    mandatory_fee = "mandatory_fee"
    living = "living"
    insurance = "insurance"
    travel_visa = "travel_visa"
    deposit = "deposit"
    setup = "setup"
    contingency = "contingency"
    other = "other"


class FundingStatus(StrEnum):
    candidate = "candidate"
    verified = "verified"
    stale = "stale"
    closed = "closed"
    open = "open"
    unknown = "unknown"


class CoverageType(StrEnum):
    tuition = "tuition"
    living = "living"
    partial = "partial"
    full = "full"
    fixed = "fixed"
    other = "other"


class OpportunityType(StrEnum):
    grant = "grant"
    fellowship = "fellowship"
    exam_scheme = "exam_scheme"
    government_scheme = "government_scheme"
    other = "other"


class InterestDuringMoratorium(StrEnum):
    capitalize = "capitalize"
    simple_interest = "simple_interest"
    none = "none"


class RepaymentMethod(StrEnum):
    equal_emi = "equal_emi"


class MetricKey(StrEnum):
    employment_rate = "employment_rate"
    median_salary = "median_salary"
    further_study_rate = "further_study_rate"
    other = "other"


class PopulationScope(StrEnum):
    program = "program"
    institution = "institution"
    subject = "subject"
    country = "country"
    other = "other"


class CostCategory(StrEnum):
    housing = "housing"
    food = "food"
    transport = "transport"
    insurance = "insurance"
    utilities = "utilities"
    personal = "personal"
    other = "other"


class RuleType(StrEnum):
    student_visa = "student_visa"
    work_during_study = "work_during_study"
    post_study_work = "post_study_work"
    health = "health"
    other = "other"


# --- ops ---
class JobType(StrEnum):
    discover = "discover"
    fetch = "fetch"
    parse = "parse"
    normalize = "normalize"
    validate = "validate"
    refresh = "refresh"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    partial = "partial"
    failed = "failed"
    cancelled = "cancelled"


class JobItemStatus(StrEnum):
    processed = "processed"
    created = "created"
    updated = "updated"
    skipped = "skipped"
    failed = "failed"
    rejected = "rejected"


class ActorType(StrEnum):
    user = "user"
    worker = "worker"
    system = "system"


def enum_col(cls: type[StrEnum], *, nullable: bool = False, default=None, server_default: str | None = None, **kw):
    """Mapped column using the shared checked-VARCHAR enum convention."""
    t = SAEnum(
        cls,
        native_enum=False,
        length=64,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
        name=f"{cls.__name__.lower()}",
    )
    return mapped_column(t, nullable=nullable, default=default, server_default=server_default, **kw)
