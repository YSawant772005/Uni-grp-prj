"""A reviewable institution needs a coherent Master's evidence package."""
from datetime import date

import pytest
from sqlalchemy import select

from app.models import FactEvidence, FactRecord, FactVersion, InstitutionIdentifier, Program, ProgramIdentifier, SourceDocument
from app.services import admin
from test_admin import TestInstitutionReview as InstitutionFixture


@pytest.mark.parametrize("damage", ["wrong_title", "rejected_title", "conflicting_passage", "failed_fetch", "historical", "unrelated_document"])
def test_incoherent_program_evidence_blocks_institution_approval(db, damage):
    university, _ = InstitutionFixture()._make_institution(db, with_program=True, verified_website=True)
    program = db.scalar(select(Program).where(Program.university_id == university.id))
    fact = db.scalar(select(FactRecord).where(FactRecord.entity_id == program.id))
    version = db.get(FactVersion, fact.current_version_id)
    evidence = db.scalar(select(FactEvidence).where(FactEvidence.fact_version_id == version.id))
    document = db.get(SourceDocument, evidence.source_document_id)
    if damage == "wrong_title":
        version.value_json = {"title": "A different degree"}
    elif damage == "rejected_title":
        fact.current_status = version.status = "rejected"
    elif damage == "conflicting_passage":
        evidence.supports_or_conflicts = "conflicts"
    elif damage == "failed_fetch":
        document.http_status = 404
    elif damage == "historical":
        document.academic_period = str(date.today().year - 1)
    else:
        other = SourceDocument(source_id=document.source_id, canonical_url="https://registry.example/unrelated", http_status=200, fetch_status="fetched")
        db.add(other)
        db.flush()
        evidence.source_document_id = other.id
    db.commit()
    detail = admin.institution_review_detail(db, university.id)
    assert detail["approval_eligibility"]["eligible"] is False
    assert detail["program_coverage"]["evidence_backed_program_count"] == 0


@pytest.mark.parametrize("namespace", ["uai", "rio_provider_id"])
def test_national_registry_identity_can_make_an_evidenced_institution_reviewable(db, namespace):
    university, _ = InstitutionFixture()._make_institution(db, with_program=True, verified_website=True)
    claim = db.scalar(select(InstitutionIdentifier).where(InstitutionIdentifier.university_id == university.id))
    claim.namespace = namespace
    claim.scope = "reporting_unit"
    db.commit()
    assert admin.institution_review_detail(db, university.id)["approval_eligibility"]["eligible"] is True


def test_verified_website_must_name_the_stored_website(db):
    university, _ = InstitutionFixture()._make_institution(db, with_program=True, verified_website=True)
    university.official_website_url = "https://different.example.edu"
    db.commit()
    assert admin.institution_review_detail(db, university.id)["approval_eligibility"]["eligible"] is False


def test_discovery_queue_filters_before_pagination(db):
    empty, _ = InstitutionFixture()._make_institution(db)
    ready, _ = InstitutionFixture()._make_institution(db, with_program=True, verified_website=True)
    result = admin.institution_review_queue(db, stage="ready_for_review", page_size=1)
    assert result["total_items"] == 1
    assert result["items"][0]["university_id"] == ready.id
    discovery = admin.institution_review_queue(db, stage="discovery")
    assert [row["university_id"] for row in discovery["items"]] == [empty.id]


def test_reviewed_course_url_needs_the_observed_page_or_an_explicit_source_link(db):
    from test_admin import TestProgramPublicationReview
    from app.services.program_evidence import official_program_page
    program, _ = TestProgramPublicationReview()._candidate(db)
    claim = db.scalar(select(ProgramIdentifier).where(ProgramIdentifier.program_id == program.id))
    document = db.get(SourceDocument, claim.source_document_id)
    document.canonical_url = "https://example.org/different-evidence-page"
    db.commit()
    assert official_program_page(db, program)["status"] != "verified"
    fact = db.scalar(select(FactRecord).where(FactRecord.entity_id == program.id,
                                            FactRecord.fact_key == "official_program_page_url"))
    evidence = db.scalar(select(FactEvidence).where(FactEvidence.fact_version_id == fact.current_version_id))
    evidence.evidence_excerpt = f"{program.canonical_name}: {program.official_program_url}"
    db.commit()
    assert official_program_page(db, program)["status"] == "verified"
