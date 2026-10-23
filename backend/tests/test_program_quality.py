"""Reviewed source pages do not fill missing academic facts."""
from datetime import date

import pytest
from sqlalchemy import event, select

from app.models import FactEvidence, FactRecord, FactVersion, Program, ProgramFee, ProgramIntake, SourceDocument
from app.services import catalog
from test_admin import TestProgramPublicationReview as PublicationFixture


@pytest.mark.parametrize("page_state", ["verified", "candidate", "unavailable"])
def test_page_review_and_academic_completeness_are_independent(db, client, page_state):
    program, _ = PublicationFixture()._candidate(db, verified_program_page=page_state == "verified")
    program.publication_status = "published"
    if page_state == "unavailable":
        program.official_program_url = None
    db.commit()
    result = client.get(f"/api/v1/programs/{program.id}")
    assert result.status_code == 200
    body = result.json()
    assert body["source_verification"]["official_program_page_status"] == page_state
    assert body["source_verification"]["program_identity_status"] == "accepted"
    assert body["academic_completeness"]["status"] == "limited"
    assert body["academic_completeness"]["verified_count"] == 0
    assert set(body["academic_completeness"]["fields"].values()) == {"unavailable"}
    assert body["data_quality"]["status"] == "unavailable"  # compatible legacy calculation
    assert body["tuition_summary"]["value"] is None
    assert body["duration_months"] is body["language"] is None
    assert body["requirements"] == body["intakes"] == []
    summary = next(p for p in client.get("/api/v1/programs?page_size=100").json()["items"]
                   if p["id"] == str(program.id))
    assert summary["source_verification"] == body["source_verification"]
    assert summary["academic_completeness"] == body["academic_completeness"]


def test_populated_unreviewed_fields_and_intake_without_deadline_are_not_verified(db, client):
    program, _ = PublicationFixture()._candidate(db)
    program.publication_status = "published"
    program.duration_min_months = program.duration_max_months = 24
    program.delivery_language = "es"
    db.add(ProgramIntake(program_id=program.id, intake_year=2027, intake_term="fall",
                         start_date=date(2027, 9, 1), status="unknown"))
    db.commit()
    body = client.get(f"/api/v1/programs/{program.id}").json()
    fields = body["academic_completeness"]["fields"]
    assert fields["duration"] == fields["teaching_language"] == fields["intake_dates"] == "unverified"
    assert fields["application_deadline"] == "unavailable"
    assert "application_deadline_not_available" in body["academic_completeness"]["warnings"]


def test_current_verified_status_without_qualifying_evidence_is_not_source_verification(db, client):
    program, _ = PublicationFixture()._candidate(db)
    program.publication_status = "published"
    fact = db.scalar(select(FactRecord).where(FactRecord.entity_id == program.id,
                                             FactRecord.fact_key == "official_program_page_url"))
    db.get(FactVersion, fact.current_version_id).status = "rejected"
    db.commit()
    body = client.get(f"/api/v1/programs/{program.id}").json()
    assert body["source_verification"]["official_program_page_status"] == "candidate"
    assert body["official_program_url"] is None


def test_listing_source_indicators_are_loaded_in_batches(db):
    program, _ = PublicationFixture()._candidate(db)
    program.publication_status = "published"
    db.commit()
    queries = []
    def record(*args):
        queries.append(args[2])
    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        catalog.search_programs(db, page_size=100)
        first = len(queries)
        other = Program(university_id=program.university_id, country_code=program.country_code,
            canonical_name="Another published fixture", slug="another", degree_level="masters",
            publication_status="published")
        db.add(other)
        db.commit()
        queries.clear()
        catalog.search_programs(db, page_size=100)
        assert len(queries) == first
    finally:
        event.remove(engine, "before_cursor_execute", record)


def _reviewed_fact(db, program, key, value):
    document = db.scalar(select(SourceDocument).join(FactEvidence,
        FactEvidence.source_document_id == SourceDocument.id).join(FactVersion,
        FactVersion.id == FactEvidence.fact_version_id).join(FactRecord,
        FactRecord.id == FactVersion.fact_record_id).where(FactRecord.entity_id == program.id))
    fact = FactRecord(entity_type='program', entity_id=program.id, fact_key=key, current_status='verified')
    db.add(fact)
    db.flush()
    version = FactVersion(fact_record_id=fact.id, version_number=1, value_json=value, status='verified')
    db.add(version)
    db.flush()
    fact.current_version_id = version.id
    db.add(FactEvidence(fact_version_id=version.id, source_document_id=document.id,
        evidence_excerpt=f'{program.canonical_name}: {value}', evidence_locator='fixture/academic-field'))
    return fact, version


def test_available_fields_require_current_matching_reviewed_values(db, client):
    program, _ = PublicationFixture()._candidate(db)
    program.publication_status = 'published'
    program.duration_min_months = program.duration_max_months = 24
    program.delivery_language = 'es'
    _, duration = _reviewed_fact(db, program, 'duration', {'min_months': 24, 'max_months': 24})
    _reviewed_fact(db, program, 'teaching_language', {'language': 'es'})
    db.commit()
    coverage = client.get(f'/api/v1/programs/{program.id}').json()['academic_completeness']
    assert coverage['fields']['duration'] == coverage['fields']['teaching_language'] == 'verified'
    assert coverage['verified_count'] == 2 and coverage['status'] == 'partial'
    duration.value_json = {'min_months': 12, 'max_months': 12}
    db.commit()
    coverage = client.get(f'/api/v1/programs/{program.id}').json()['academic_completeness']
    assert coverage['fields']['duration'] == 'unverified' and coverage['verified_count'] == 1


def test_a_verified_unrelated_fact_does_not_verify_tuition(db, client):
    program, _ = PublicationFixture()._candidate(db)
    program.publication_status = 'published'
    fact = db.scalar(select(FactRecord).where(FactRecord.entity_id == program.id,
                                             FactRecord.fact_key == 'program_title_as_reported'))
    fact.current_status = db.get(FactVersion, fact.current_version_id).status = 'verified'
    db.add(ProgramFee(program_id=program.id, fee_type='tuition', amount=12000,
                      currency='EUR', period='year', fact_id=fact.id, status='verified'))
    db.commit()
    assert client.get(f'/api/v1/programs/{program.id}').json()['academic_completeness']['fields']['tuition'] == 'unverified'


def test_tuition_verification_checks_decimal_amount_and_current_evidence(db, client):
    program, _ = PublicationFixture()._candidate(db)
    program.publication_status = 'published'
    fact, version = _reviewed_fact(db, program, 'tuition', {'amount': '12000', 'currency': 'EUR', 'period': 'year'})
    db.add(ProgramFee(program_id=program.id, fee_type='tuition', amount=12000,
                      currency='EUR', period='year', fact_id=fact.id, status='verified'))
    db.commit()
    assert client.get(f'/api/v1/programs/{program.id}').json()['academic_completeness']['fields']['tuition'] == 'verified'
    version.value_json = {**version.value_json, 'amount': 'not an amount'}
    db.commit()
    assert client.get(f'/api/v1/programs/{program.id}').json()['academic_completeness']['fields']['tuition'] == 'unverified'
