"""Human fact review updates structured data without publishing programmes."""
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import select

from app.ingestion.persist import Counters, record_fact
from app.ingestion.types import CandidateFact
from app.models import AdmissionRequirement, FactRecord, FactVersion, Program, ProgramFee, StudentProfile
from app.services import admin, costs, eligibility
from test_admin import TestInstitutionReview as InstitutionFixture


def test_reviewed_site_title_and_structured_fee_are_projected_only_after_review(db, make_user):
    university, _ = InstitutionFixture()._make_institution(db, with_program=True)
    program = db.scalar(select(Program).where(Program.university_id == university.id))
    reviewer = make_user("reviewer")
    from app.models import Source, SourceDocument
    doc = db.scalar(select(SourceDocument).where(SourceDocument.title == "Official Master's programme record"))
    source = db.get(Source, doc.source_id)
    record_fact(db, entity_type="program", entity_id=program.id, source=source, document=doc,
                fact=CandidateFact("tuition", {"amount": "12345", "currency": "EUR", "period": "academic_year", "academic_year": "2027-2028"},
                                   excerpt="Official programme tuition: EUR 12,345 for 2027-2028.", locator="record/tuition"), counters=Counters())
    fact = db.scalar(select(FactRecord).where(FactRecord.entity_id == program.id, FactRecord.fact_key == "tuition"))
    assert db.scalar(select(ProgramFee.id).where(ProgramFee.program_id == program.id)) is None
    result = admin.approve_fact(db, reviewer, fact.id, None, "The official source confirms this tuition amount and academic year.", None)
    assert result["projection_status"] == "applied"
    fee = db.scalar(select(ProgramFee).where(ProgramFee.fact_id == fact.id))
    assert fee.amount == Decimal("12345") and fee.status == "verified"
    assert program.publication_status == "candidate"
    record_fact(db, entity_type="program", entity_id=program.id, source=source, document=doc,
                fact=CandidateFact("tuition", {"amount": "20000", "currency": "EUR", "period": "academic_year", "academic_year": "2027-2028"}), counters=Counters())
    db.flush()
    assert fee.amount == Decimal("12345")
    assert fact.current_status == "conflicted"
    assert costs._tuition_items(db, program)["tuition"]["value"] is None
    from app.services import catalog
    summary = catalog._summary(program, university, None, catalog._page_context(db, [program.id]))
    assert summary["tuition_summary"]["status"] == "conflicted"
    assert "tuition_not_verified" in summary["data_quality"]["warnings"]


def test_recurring_fee_with_unknown_duration_is_not_a_full_program_cost(db):
    program = db.scalar(select(Program))
    program.duration_min_months = program.duration_max_months = None
    assert costs._tuition_items(db, program)["tuition"]["value"] is None


def test_optional_failed_requirement_does_not_make_a_program_ineligible():
    profile = StudentProfile(user_id=uuid.uuid4(), work_experience_months=0)
    required = AdmissionRequirement(id=uuid.uuid4(), requirement_type="work_experience", requirement_key="required_experience", operator="gte", expected_value={"months": 0}, is_mandatory=True, group_key="required", group_operator="AND")
    optional = AdmissionRequirement(id=uuid.uuid4(), requirement_type="work_experience", requirement_key="preferred_experience", operator="gte", expected_value={"months": 24}, is_mandatory=False, group_key="optional", group_operator="AND")
    assert eligibility.evaluate_program(profile, [required, optional])["status"] == "eligible"


def test_stored_or_group_accepts_one_matching_alternative():
    profile = StudentProfile(user_id=uuid.uuid4(), work_experience_months=12)
    requirements = [AdmissionRequirement(id=uuid.uuid4(), requirement_type="work_experience", requirement_key=f"experience_{months}", operator="gte", expected_value={"months": months}, is_mandatory=True, group_key="alternatives", group_operator="OR") for months in (6, 24)]
    assert eligibility.evaluate_program(profile, requirements)["status"] == "eligible"


def test_conflicting_requirement_evidence_stays_unknown():
    profile = StudentProfile(user_id=uuid.uuid4(), work_experience_months=12)
    fact_id = uuid.uuid4()
    rule = AdmissionRequirement(id=uuid.uuid4(), source_fact_id=fact_id, requirement_type="work_experience", requirement_key="experience", operator="gte", expected_value={"months": 6}, is_mandatory=True, group_operator="AND")
    assert eligibility.evaluate_program(profile, [rule], fact_statuses={fact_id: "conflicted"})["status"] == "unknown_needs_review"


@pytest.mark.parametrize("key,value", [
    ("tuition", {"amount": "1000000000000", "currency": "EUR", "period": "academic_year", "academic_year": "2027"}),
    ("tuition", {"amount": "500", "currency": "EUR", "period": "academic_year", "academic_year": "2027", "student_category": "x" * 41}),
    ("admission_requirement", {"requirement_type": "work_experience", "requirement_key": "experience", "operator": "gte", "expected_value": {"months": 6}, "is_mandatory": True, "group_operator": "MAYBE"}),
    ("intake_dates", {"intake_year": 2027, "intake_term": "fall", "is_open_for_applications": "yes"}),
])
def test_invalid_structured_values_are_rejected_before_database_projection(db, key, value):
    from types import SimpleNamespace
    from app.core.errors import ApiError
    from app.services.fact_projection import apply_reviewed_fact
    program = db.scalar(select(Program))
    fact = SimpleNamespace(id=uuid.uuid4(), entity_type="program", entity_id=program.id, fact_key=key)
    version = SimpleNamespace(value_json=value, applicable_intake_year=None)
    with pytest.raises(ApiError) as error:
        apply_reviewed_fact(db, fact, version)
    assert error.value.status_code == 422


def test_unstructured_value_remains_evidence_only(db):
    from types import SimpleNamespace
    from app.services.fact_projection import apply_reviewed_fact
    fact = SimpleNamespace(entity_type="program", fact_key="tuition")
    assert apply_reviewed_fact(db, fact, SimpleNamespace(value_json=["raw prose"])) == "evidence_only"
