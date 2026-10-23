"""Institution evidence and review boundaries, with deterministic ROR/UAL HTTP."""
import uuid

import httpx
import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.ingestion import persist
from app.ingestion.adapters.ror import RorAdapter
from app.ingestion.http import Fetcher
from app.ingestion.pipeline import RunOptions, run_source
from app.models import (
    CatalogueResetOperation, FactEvidence, FactRecord, FactVersion,
    InstitutionIdentifier, InstitutionIdentityReview, InstitutionReview, Program, SourceDocument, University,
)
from app.services import admin
from test_ual_program_pages import make_fetcher, patch_pipeline, setup_ual  # noqa: F401


# Frozen subset of the official ROR response; these tests never use live HTTP.
ROR_RECORD = {
    "id": "https://ror.org/003d3xx08", "status": "active", "types": ["education"],
    "names": [
        {"value": "Universidad de Almería", "lang": "es", "types": ["label"]},
        {"value": "University of Almería", "lang": "en", "types": ["ror_display", "label"]},
    ],
    "links": [{"type": "website", "value": "https://www.ual.es"}],
    "locations": [{"geonames_details": {"country_code": "ES", "country_name": "Spain"}}],
}


def _ual(db, monkeypatch, make_fetcher):
    university, source, review = setup_ual(db)
    patch_pipeline(monkeypatch, make_fetcher)
    result = run_source("ual_masters", RunOptions(max_records=5), db=db)
    assert result.status == "succeeded", result.error
    db.commit()
    return university, source, review


def _ror_http(monkeypatch):
    def make(**kwargs):
        fetcher = Fetcher(**kwargs)
        fetcher._client.close()

        def respond(request):
            assert request.url.host == "api.ror.org"
            assert request.url.params["query"] == "Universidad de Almería"
            return httpx.Response(200, json={"items": [ROR_RECORD]})

        fetcher._client = httpx.Client(transport=httpx.MockTransport(respond))
        return fetcher
    monkeypatch.setattr("app.ingestion.pipeline.Fetcher", make)


def _university_facts(db, university):
    return db.scalars(select(FactRecord).where(
        FactRecord.entity_type == "university", FactRecord.entity_id == university.id)).all()


def test_publisher_link_is_targetable_but_does_not_satisfy_institution_approval(db, monkeypatch, make_fetcher):
    university, _, _ = _ual(db, monkeypatch, make_fetcher)
    detail = admin.institution_review_detail(db, university.id)
    assert detail["program_coverage"]["evidence_backed_program_count"] == 5
    assert detail["facts"] == []
    assert len(detail["approval_eligibility"]["blockers"]) == 3
    assert detail["identifier_claims"][0]["namespace"] == "ual_dataset_publisher"
    assert detail["identifier_claims"][0]["claim_status"] == "pending_review"
    discovery = next(s for s in detail["source_discovery"] if s["source_key"] == "ual_masters")
    assert discovery["status"] == "targetable"
    # A reviewed publisher link never becomes an authoritative identifier.
    assert discovery["matching_identifier"] is None


def test_ror_reconciliation_import_and_website_review_clear_only_evidence_blockers(
        db, monkeypatch, make_fetcher, make_user, client):
    university, _, _ = _ual(db, monkeypatch, make_fetcher)
    program_ids = set(db.scalars(select(Program.id).where(Program.university_id == university.id)))
    university_count = db.scalar(select(func.count()).select_from(University))
    _ror_http(monkeypatch)
    options = RunOptions(query="Universidad de Almería", max_records=1, max_pages=1)
    first = run_source("ror", options, db=db)
    assert first.status == "partial" and first.counters.review == 1
    assert db.scalar(select(func.count()).select_from(University)) == university_count
    review = db.scalar(select(InstitutionIdentityReview).where(
        InstitutionIdentityReview.external_key == "ror:003d3xx08",
        InstitutionIdentityReview.status == "pending"))
    assert review.suggested_university_id == university.id
    assert not _university_facts(db, university)
    reviewer = make_user("reviewer")
    db.commit()
    headers = {"Authorization": "Bearer " + create_access_token(str(reviewer.id), ["reviewer"])}
    response = client.post(f"/api/v1/admin/identity-reviews/{review.id}/approve", headers=headers,
        json={"university_id": str(university.id),
              "reason": "Fresh ROR identity matches the official university name, country and website."})
    assert response.status_code == 200, response.text
    db.expire_all()
    # Link approval records an accepted ID, but does not replay extracted facts.
    assert not _university_facts(db, university)
    claim = db.scalar(select(InstitutionIdentifier).where(
        InstitutionIdentifier.university_id == university.id, InstitutionIdentifier.namespace == "ror"))
    assert claim.claim_status == "accepted" and claim.normalized_value == "003d3xx08"
    assert len(admin.institution_review_detail(db, university.id)["approval_eligibility"]["blockers"]) == 2
    second = run_source("ror", options, db=db)
    assert second.status == "succeeded" and second.counters.institutions_created == 0
    assert second.counters.institutions_updated == 1
    facts = {f.fact_key: f for f in _university_facts(db, university)}
    assert {"official_name", "aliases", "official_website_url"} <= facts.keys()
    for key in ("official_name", "official_website_url"):
        fact = facts[key]
        assert fact.current_status == "candidate"
        evidence = db.scalar(select(FactEvidence).where(FactEvidence.fact_version_id == fact.current_version_id))
        document = db.get(SourceDocument, evidence.source_document_id)
        assert document.source_id == claim.source_id
        assert document.canonical_url.startswith("https://api.ror.org/v2/organizations?")
        assert document.http_status == 200 and document.content_hash
        assert evidence.evidence_excerpt and evidence.evidence_locator == ROR_RECORD["id"]
    detail = admin.institution_review_detail(db, university.id)
    assert detail["website_evidence_status"] == "candidate"
    assert len(detail["approval_eligibility"]["blockers"]) == 1
    # ROR's English display name and official Spanish label remain available;
    # ingestion does not rename the existing canonical institution.
    assert university.canonical_name == "Universidad de Almería"
    name_version = db.get(FactVersion, facts["official_name"].current_version_id)
    assert name_version.value_json["name"] == "University of Almería"
    website = facts["official_website_url"]
    db.commit()
    response = client.post(f"/api/v1/admin/facts/{website.id}/approve", headers=headers,
        json={"version_id": str(website.current_version_id),
              "reason": "The official ROR record explicitly links this university website."})
    assert response.status_code == 200, response.text
    assert response.json()["projection_status"] == "applied"
    db.expire_all()
    detail = admin.institution_review_detail(db, university.id)
    assert detail["official_website_url"] == "https://ual.es"
    assert detail["website_evidence_status"] == "verified"
    assert detail["approval_eligibility"]["eligible"] is True
    assert detail["status"] == "pending"
    assert all(p["publication_status"] == "candidate" for p in detail["programs"])
    before = tuple(db.scalar(select(func.count()).select_from(model))
                   for model in (FactRecord, FactVersion, FactEvidence, SourceDocument))
    third = run_source("ror", options, db=db)
    assert third.status == "succeeded" and third.counters.created == third.counters.review == 0
    assert tuple(db.scalar(select(func.count()).select_from(model))
                 for model in (FactRecord, FactVersion, FactEvidence, SourceDocument)) == before
    assert db.get(FactRecord, website.id).current_status == "verified"
    assert set(db.scalars(select(Program.id).where(Program.university_id == university.id))) == program_ids
    db.commit()
    visible = client.get("/api/v1/programs?page_size=100").json()
    assert not program_ids.intersection(uuid.UUID(p["id"]) for p in visible["items"])
    for program_id in program_ids:
        assert client.get(f"/api/v1/programs/{program_id}").status_code == 404


@pytest.mark.parametrize("active_status", ["pending", "deferred", "rejected"])
def test_archived_publisher_approval_does_not_make_source_targetable(db, active_status):
    university, source, active = setup_ual(db)
    db.add(InstitutionReview(university_id=university.id, status="pending"))
    # Retain a publisher claim, as in development, without an active approved link.
    db.add(InstitutionIdentifier(university_id=university.id, source_id=source.id,
        source_document_id=active.source_document_id, source_key="ual_masters",
        namespace="ual_dataset_publisher", identifier_value="u04800001",
        normalized_value="u04800001", scope="institution", claim_status="pending_review"))
    active.status, active.resolved_university_id = active_status, None
    operation = CatalogueResetOperation(id=uuid.uuid4(), operator="isolated fixture",
        reason="Historical review fixture", original_revision="85b2e4a6c910",
        backup_path="/test-only", backup_sha256="a" * 64, manifest={})
    db.add(operation)
    db.flush()
    db.add(InstitutionIdentityReview(source_id=source.id, source_document_id=active.source_document_id,
        external_key=active.external_key, candidate_payload={}, status="approved",
        archived_operation_id=operation.id))
    db.flush()
    detail = admin.institution_review_detail(db, university.id)
    discovery = next(s for s in detail["source_discovery"] if s["source_key"] == "ual_masters")
    assert discovery["status"] == "identity_mapping_required"
    assert not detail["approval_eligibility"]["eligible"]


def test_ror_names_and_website_remain_candidates_with_record_locators():
    candidate = RorAdapter()._to_institution(ROR_RECORD, 1)
    assert candidate.identifiers["ror"] == "003d3xx08"
    assert "Universidad de Almería" in candidate.aliases
    for fact in candidate.facts:
        assert fact.status == "candidate" and fact.locator == ROR_RECORD["id"]
