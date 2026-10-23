"""Phase 7: review queue, fact review actions, sources, jobs and audit (§5.10).

Covers role gates, append-only review history, honest worker outcomes (no fake
success), idempotent enqueue/retry and audit-event filtering.
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.seed import run_seed
from app.models import (
    AuditEvent,
    FactEvidence,
    FactRecord,
    FactReviewEvent,
    FactVersion,
    IngestionJob,
    IngestionJobItem,
    InstitutionIdentityReview,
    InstitutionIdentityReviewEvent,
    InstitutionIdentifier,
    InstitutionReview,
    InstitutionReviewEvent,
    Program,
    ProgramIdentifier,
    Role,
    Source,
    SourceDocument,
    University,
    User,
    UserRole,
)
from conftest import _truncate_all


@pytest.fixture(autouse=True)
def generous_rate_limit():
    from app.routers.v1.auth import limiter

    previous = settings.rate_limit_auth
    settings.rate_limit_auth = "1000/minute"
    limiter.reset()
    yield
    limiter.reset()
    settings.rate_limit_auth = previous


@pytest.fixture(scope="module")
def _seeded():
    session = SessionLocal()
    _truncate_all(session)
    run_seed(session)
    yield session
    session.close()


@pytest.fixture()
def db(_seeded):
    yield _seeded
    _seeded.rollback()


def _register(client, prefix="adm"):
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "Sup3rSecret!"})
    assert r.status_code == 201
    return email


def _grant(db, email, *role_keys):
    """Grant roles DB-side (the app reads roles from its own sessions)."""
    user = db.scalar(select(User).where(User.email == email))
    for key in role_keys:
        role = db.scalar(select(Role).where(Role.key == key))
        db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    return user


def _login(client, email):
    client.cookies.clear()
    assert client.post("/api/v1/auth/login",
                       json={"email": email, "password": "Sup3rSecret!"}).status_code == 200


def _candidate_fact(db, exclude=()):
    fact = db.scalar(
        select(FactRecord).where(
            FactRecord.current_status == "candidate",
            FactRecord.current_version_id.is_not(None),
            FactRecord.id.not_in(exclude),
        ).order_by(FactRecord.id))
    assert fact is not None, "seed must contain candidate facts"
    return fact


def _permitted_source(db):
    from app.services.admin import REFRESHABLE_POLICIES

    source = db.scalar(select(Source).where(
        Source.allowed_use_policy.in_(REFRESHABLE_POLICIES),
        Source.enabled.is_(True)).limit(1))
    if source is None:
        source = Source(name="Fixture Permitted Source", base_url="https://example.com/data",
                        source_type="other", authority_tier=3,
                        allowed_use_policy="permitted_fetch", enabled=True)
        db.add(source)
        db.commit()
    return source


class TestAccessControl:
    def test_requires_auth_then_roles(self, db, client):
        client.cookies.clear()
        assert client.get("/api/v1/admin/review-queue").status_code == 401
        assert client.get("/api/v1/admin/jobs").status_code == 401

        student = _register(client, "stu")
        for path in ("/api/v1/admin/review-queue", "/api/v1/admin/facts/" + str(uuid.uuid4()),
                     "/api/v1/admin/sources", "/api/v1/admin/jobs",
                     "/api/v1/admin/audit-events"):
            assert client.get(path).status_code == 403, path
        assert client.post("/api/v1/admin/sources",
                           json={"name": "x", "base_url": "https://x.example"}).status_code == 403

        # reviewer: read + fact actions yes, admin-only no
        reviewer = _register(client, "rev")
        _grant(db, reviewer, "reviewer")
        _login(client, reviewer)
        assert client.get("/api/v1/admin/review-queue").status_code == 200
        assert client.get("/api/v1/admin/sources").status_code == 200
        assert client.get("/api/v1/admin/jobs").status_code == 403
        assert client.get("/api/v1/admin/audit-events").status_code == 403
        assert client.post("/api/v1/admin/sources",
                           json={"name": "x", "base_url": "https://x.example"}).status_code == 403

        admin = _register(client, "adm")
        _grant(db, admin, "admin", "reviewer")
        _login(client, admin)
        for path in ("/api/v1/admin/review-queue", "/api/v1/admin/sources",
                     "/api/v1/admin/jobs", "/api/v1/admin/audit-events"):
            assert client.get(path).status_code == 200, path


class TestReviewQueue:
    def test_queue_defaults_to_reviewable_and_paginates(self, db, client):
        admin = _register(client)
        _grant(db, admin, "admin", "reviewer")
        _login(client, admin)

        listing = client.get("/api/v1/admin/review-queue?page_size=5").json()
        assert listing["total_items"] >= 1
        assert listing["page"] == 1 and listing["page_size"] == 5
        assert listing["total_pages"] >= 1
        for item in listing["items"]:
            assert item["current_status"] in ("candidate", "in_review", "conflicted", "stale")
            assert item["fact_key"] and item["entity_type"]
            assert item["version_count"] >= 1
            assert isinstance(item["evidence_count"], int)
            assert "last_review" in item
        # program facts resolve their display label
        labelled = [i for i in listing["items"] if i["entity_type"] == "program"]
        if labelled:
            assert labelled[0]["entity_label"]

        second = client.get("/api/v1/admin/review-queue?page=2&page_size=5").json()
        first_ids = {i["fact_id"] for i in listing["items"]}
        second_ids = {i["fact_id"] for i in second["items"]}
        assert not (first_ids & second_ids), "pages must not overlap"

    def test_filters_and_validation(self, db, client):
        admin = _register(client)
        _grant(db, admin, "admin", "reviewer")
        _login(client, admin)

        all_items = client.get("/api/v1/admin/review-queue?page_size=100").json()
        only_candidates = client.get(
            "/api/v1/admin/review-queue?status=candidate&page_size=100").json()
        assert only_candidates["total_items"] <= all_items["total_items"]
        assert all(i["current_status"] == "candidate" for i in only_candidates["items"])

        by_key = client.get(
            "/api/v1/admin/review-queue?fact_key=prereq_calculus&page_size=100").json()
        assert by_key["total_items"] >= 1
        assert all(i["fact_key"] == "prereq_calculus" for i in by_key["items"])

        assert client.get("/api/v1/admin/review-queue?status=bogus").status_code == 422
        empty = client.get("/api/v1/admin/review-queue?fact_key=no_such_key").json()
        assert empty["items"] == [] and empty["total_items"] == 0


class TestInstitutionIdentityReview:
    def _review(self, db):
        source = _permitted_source(db)
        document = SourceDocument(source_id=source.id, canonical_url="https://example.org/identity",
                                  content_hash="identity-review-test", fetch_status="fetched")
        db.add(document)
        db.flush()
        sample = db.scalar(select(University).limit(1))
        target = University(canonical_name=f"Reviewable {uuid.uuid4().hex[:8]}",
                            slug=f"reviewable-{uuid.uuid4().hex[:8]}",
                            country_code=sample.country_code, external_identifiers={})
        db.add(target)
        db.flush()
        review = InstitutionIdentityReview(
            source_id=source.id, source_document_id=document.id,
            external_key=f"source:{uuid.uuid4()}", status="pending",
            suggested_university_id=target.id,
            candidate_payload={"identity_review": [{"code": "weak_match"}],
                "candidate": {"external_key": "source:candidate", "name": target.canonical_name,
                              "country_code": target.country_code,
                              "identifiers": {"ror": f"review-{uuid.uuid4().hex}"},
                              "identifier_scopes": {}}})
        db.add(review)
        db.commit()
        return review, target

    def test_reviewer_can_approve_link_without_merging_and_audit_is_appended(self, db, client):
        reviewer_email = _register(client, "identity-reviewer")
        reviewer = _grant(db, reviewer_email, "reviewer")
        _login(client, reviewer_email)
        review, target = self._review(db)

        queue_item = next(item for item in client.get(
            "/api/v1/admin/identity-reviews?status=pending&page_size=100").json()["items"]
            if item["id"] == str(review.id))
        assert queue_item["status"] == "pending"
        assert queue_item["source"]["allowed_use_policy"]
        assert queue_item["source_document"]["url"].startswith("https://")
        assert queue_item["events"] == []

        response = client.post(f"/api/v1/admin/identity-reviews/{review.id}/approve",
                               json={"university_id": str(target.id),
                                     "reason": "Same authoritative source identity verified."})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "approved"
        db.expire_all()
        assert db.get(InstitutionIdentityReview, review.id).resolved_university_id == target.id
        assert db.scalar(select(InstitutionIdentifier.id).where(
            InstitutionIdentifier.university_id == target.id,
            InstitutionIdentifier.namespace == "ror")) is not None
        event = db.scalar(select(InstitutionIdentityReviewEvent).where(
            InstitutionIdentityReviewEvent.review_id == review.id))
        assert event.actor_user_id == reviewer.id and event.action == "approve_link"
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text("UPDATE institution_identity_review_events SET reason='changed' WHERE id=:id"),
                       {"id": event.id})
        assert client.post(f"/api/v1/admin/identity-reviews/{review.id}/approve",
                           json={"university_id": str(target.id), "reason": "repeat"}).status_code == 409

    def test_student_cannot_read_or_decide_identity_reviews(self, db, client):
        student_email = _register(client, "identity-student")
        _login(client, student_email)
        review, target = self._review(db)
        assert client.get("/api/v1/admin/identity-reviews").status_code == 403
        assert client.post(f"/api/v1/admin/identity-reviews/{review.id}/approve",
                           json={"university_id": str(target.id), "reason": "No."}).status_code == 403

    def test_rejected_identity_action_requires_reason_and_records_event(self, db, client):
        reviewer_email = _register(client, "identity-reject")
        _grant(db, reviewer_email, "reviewer")
        _login(client, reviewer_email)
        review, _ = self._review(db)
        assert client.post(f"/api/v1/admin/identity-reviews/{review.id}/reject",
                           json={"reason": "   "}).status_code == 422
        assert client.post(f"/api/v1/admin/identity-reviews/{review.id}/reject",
                           json={"reason": "Evidence shows a different reporting unit."}).status_code == 200
        event = db.scalar(select(InstitutionIdentityReviewEvent).where(
            InstitutionIdentityReviewEvent.review_id == review.id))
        assert event is not None and event.action == "reject"


class TestInstitutionReview:
    def _make_institution(self, db, *, with_program=False, verified_website=False):
        from app.models import Country

        country = db.scalar(select(Country).where(Country.code == "DE"))
        ror_id = f"01{uuid.uuid4().hex[:8]}"
        university = University(
            canonical_name="Evidence Test University", slug=f"evidence-test-{uuid.uuid4().hex[:8]}",
            country_code=country.code, official_website_url="https://university.example.edu",
            external_identifiers={"ror": ror_id})
        db.add(university)
        db.flush()
        source = Source(name="Official institution catalogue fixture", base_url="https://university.example.edu",
                        source_type="official_university", authority_tier=1,
                        allowed_use_policy="permitted_fetch", enabled=True,
                        metadata_json={"adapter_key": "test_source"})
        db.add(source)
        db.flush()
        document = SourceDocument(source_id=source.id, canonical_url="https://registry.example/data",
                                  title="Institution record", http_status=200,
                                  fetch_status="fetched", content_hash=uuid.uuid4().hex)
        db.add(document)
        db.flush()
        db.add(InstitutionIdentifier(
            university_id=university.id, source_id=source.id, source_document_id=document.id,
            source_key="test_source", namespace="ror", identifier_value=ror_id,
            normalized_value=ror_id, scope="institution", claim_status="accepted"))
        fact = FactRecord(entity_type="university", entity_id=university.id,
                          fact_key="official_name", current_status="candidate")
        db.add(fact)
        db.flush()
        version = FactVersion(fact_record_id=fact.id, version_number=1,
                              value_json={"name": university.canonical_name}, status="candidate")
        db.add(version)
        db.flush()
        fact.current_version_id = version.id
        db.add(FactEvidence(fact_version_id=version.id, source_document_id=document.id,
                            evidence_excerpt=university.canonical_name,
                            evidence_locator="record/name"))
        if verified_website:
            website_fact = FactRecord(entity_type="university", entity_id=university.id,
                                      fact_key="official_website_url", current_status="verified")
            db.add(website_fact)
            db.flush()
            website_version = FactVersion(
                fact_record_id=website_fact.id, version_number=1,
                value_json={"url": university.official_website_url}, status="verified")
            db.add(website_version)
            db.flush()
            website_fact.current_version_id = website_version.id
            db.add(FactEvidence(fact_version_id=website_version.id,
                                source_document_id=document.id,
                                evidence_excerpt=university.official_website_url,
                                evidence_locator="record/website"))
        if with_program:
            program_document = SourceDocument(
                source_id=source.id, canonical_url="https://university.example.edu/graduate/master-test",
                title="Official Master's programme record", http_status=200,
                fetch_status="fetched", content_hash=uuid.uuid4().hex)
            db.add(program_document)
            db.flush()
            program = Program(university_id=university.id, country_code=university.country_code,
                canonical_name="Master of Source Evidence", slug=f"master-source-{uuid.uuid4().hex[:8]}",
                degree_level="masters", official_program_url=program_document.canonical_url)
            db.add(program)
            db.flush()
            program_source_key = f"master-source-{uuid.uuid4().hex[:8]}"
            db.add(ProgramIdentifier(
                program_id=program.id, source_id=source.id,
                source_document_id=program_document.id, source_key="test_source",
                external_key=program_source_key, normalized_external_key=program_source_key,
                claim_status="accepted"))
            program_fact = FactRecord(entity_type="program", entity_id=program.id,
                fact_key="program_title_as_reported", current_status="candidate")
            db.add(program_fact)
            db.flush()
            program_version = FactVersion(fact_record_id=program_fact.id, version_number=1,
                value_json={"title": program.canonical_name}, status="candidate")
            db.add(program_version)
            db.flush()
            program_fact.current_version_id = program_version.id
            db.add(FactEvidence(fact_version_id=program_version.id,
                source_document_id=program_document.id, evidence_excerpt=program.canonical_name,
                evidence_locator=f"programs[{program_source_key}]"))
        review = InstitutionReview(university_id=university.id, status="pending")
        db.add(review)
        db.commit()
        return university, review

    def test_queue_groups_institution_evidence_and_decisions_are_audited(self, db, client):
        university, _ = self._make_institution(db, with_program=True, verified_website=True)
        assert client.get("/api/v1/admin/institution-reviews").status_code == 401
        student = _register(client, "institution-student")
        _login(client, student)
        assert client.get("/api/v1/admin/institution-reviews").status_code == 403

        reviewer = _register(client, "institution-reviewer")
        _grant(db, reviewer, "reviewer")
        _login(client, reviewer)
        listing = client.get("/api/v1/admin/institution-reviews?status=pending").json()
        row = next(item for item in listing["items"] if item["university_id"] == str(university.id))
        assert row["fact_count"] == 2 and row["identifier_count"] == 1
        detail = client.get(f"/api/v1/admin/institution-reviews/{university.id}").json()
        assert detail["facts"][0]["evidence"][0]["locator"] == "record/name"
        assert detail["identifier_claims"][0]["namespace"] == "ror"
        assert detail["status"] == "pending"
        assert detail["program_coverage"]["status"] == "catalogue_available_and_imported"
        assert detail["approval_eligibility"]["eligible"] is True
        assert detail["programs"][0]["program_facts"][0]["evidence"][0]["locator"] == \
            f"programs[{detail['programs'][0]['source_identities'][0]['external_key']}]"
        assert detail["facts"][0]["evidence"][0]["allowed_use_policy"] == "permitted_fetch"
        assert detail["programs"][0]["program_facts"][0]["evidence"][0]["allowed_use_policy"] == "permitted_fetch"

        response = client.post(f"/api/v1/admin/institutions/{university.id}/review", json={
            "action": "approve",
            "reason": "The source evidence confirms the official name and authoritative ROR identity.",
        })
        assert response.status_code == 200, response.text
        db.expire_all()
        review = db.scalar(select(InstitutionReview).where(
            InstitutionReview.university_id == university.id))
        event = db.scalar(select(InstitutionReviewEvent).where(
            InstitutionReviewEvent.review_id == review.id))
        assert review.status == "approved" and review.reviewed_by_user_id is not None
        assert event.action == "approve" and event.actor_user_id == review.reviewed_by_user_id
        assert client.post(f"/api/v1/admin/institutions/{university.id}/review", json={
            "action": "approve", "reason": "The source evidence confirms this identity again.",
        }).status_code == 409

    def test_approval_is_blocked_until_programme_coverage_and_website_are_reviewable(self, db, client):
        university, _ = self._make_institution(db)
        reviewer = _register(client, "institution-coverage-block")
        _grant(db, reviewer, "reviewer")
        _login(client, reviewer)
        detail = client.get(f"/api/v1/admin/institution-reviews/{university.id}").json()
        assert detail["program_coverage"]["status"] == "availability_not_established"
        assert detail["approval_eligibility"]["eligible"] is False
        response = client.post(f"/api/v1/admin/institutions/{university.id}/review", json={
            "action": "approve",
            "reason": "The official university website and program evidence confirm this institution.",
        })
        assert response.status_code == 409
        assert any("No named Master's programme records" in detail["message"]
                   for detail in response.json()["error"]["details"])
        db.expire_all()
        review = db.scalar(select(InstitutionReview).where(
            InstitutionReview.university_id == university.id))
        assert review.status == "pending"
        assert db.scalar(select(InstitutionReviewEvent.id).where(
            InstitutionReviewEvent.review_id == review.id)) is None

    def test_unaccepted_program_identity_does_not_satisfy_coverage(self, db, client):
        university, _ = self._make_institution(db, with_program=True, verified_website=True)
        identifier = db.scalar(select(ProgramIdentifier).join(
            Program, Program.id == ProgramIdentifier.program_id).where(
                Program.university_id == university.id))
        identifier.claim_status = "pending_review"
        db.commit()

        reviewer = _register(client, "unaccepted-program-identity")
        _grant(db, reviewer, "reviewer")
        _login(client, reviewer)
        detail = client.get(
            f"/api/v1/admin/institution-reviews/{university.id}").json()
        assert detail["program_coverage"]["evidence_backed_program_count"] == 0
        assert detail["approval_eligibility"]["eligible"] is False
        response = client.post(f"/api/v1/admin/institutions/{university.id}/review", json={
            "action": "approve",
            "reason": "The source record and official evidence support this institution.",
        })
        assert response.status_code == 409

    def test_invalid_reason_shows_actionable_field_error_without_state_change(self, db, client):
        university, review = self._make_institution(db)
        reviewer = _register(client, "institution-invalid-reason")
        _grant(db, reviewer, "reviewer")
        _login(client, reviewer)
        response = client.post(f"/api/v1/admin/institutions/{university.id}/review", json={
            "action": "needs_evidence", "reason": "checking",
        })
        assert response.status_code == 422
        error = response.json()["error"]
        assert "describe the evidence" in error["message"]
        assert error["details"][0]["field"] == "reason"
        assert "30 characters and five words" in error["details"][0]["message"]
        db.expire_all()
        assert db.get(InstitutionReview, review.id).status == "pending"
        assert db.scalar(select(InstitutionReviewEvent.id).where(
            InstitutionReviewEvent.review_id == review.id)) is None

    def test_request_stronger_evidence_accepts_clear_reason_and_audits(self, db, client):
        university, review = self._make_institution(db)
        reviewer = _register(client, "institution-needs-evidence")
        _grant(db, reviewer, "reviewer")
        _login(client, reviewer)
        reason = "The official university website could not be verified."
        response = client.post(f"/api/v1/admin/institutions/{university.id}/review", json={
            "action": "needs_evidence", "reason": reason,
        })
        assert response.status_code == 200, response.text
        db.expire_all()
        saved = db.get(InstitutionReview, review.id)
        event = db.scalar(select(InstitutionReviewEvent).where(
            InstitutionReviewEvent.review_id == review.id))
        audit = db.scalar(select(AuditEvent).where(
            AuditEvent.entity_type == "university", AuditEvent.entity_id == university.id,
            AuditEvent.action == "institution_needs_evidence"))
        assert saved.status == "needs_evidence" and saved.review_reason == reason
        assert event.actor_user_id == saved.reviewed_by_user_id and event.reason == reason
        assert audit.actor_user_id == saved.reviewed_by_user_id and audit.reason == reason
        refreshed = client.get(f"/api/v1/admin/institution-reviews/{university.id}").json()
        assert refreshed["status"] == "needs_evidence"
        assert refreshed["events"][0]["reason"] == reason

    def test_reject_action_persists_separately_from_request_evidence(self, db, client):
        university, review = self._make_institution(db)
        reviewer = _register(client, "institution-reject")
        _grant(db, reviewer, "reviewer")
        _login(client, reviewer)
        reason = "The source identifier conflicts with the official university record."
        response = client.post(f"/api/v1/admin/institutions/{university.id}/review", json={
            "action": "reject", "reason": reason,
        })
        assert response.status_code == 200, response.text
        db.expire_all()
        saved = db.get(InstitutionReview, review.id)
        event = db.scalar(select(InstitutionReviewEvent).where(
            InstitutionReviewEvent.review_id == review.id))
        assert saved.status == "rejected" and saved.review_reason == reason
        assert event.action == "reject" and event.reason == reason

    def test_defer_action_records_review_history(self, db, client):
        university, review = self._make_institution(db)
        reviewer = _register(client, "institution-defer")
        _grant(db, reviewer, "reviewer")
        _login(client, reviewer)
        reason = "The official source evidence needs additional campus confirmation."
        response = client.post(f"/api/v1/admin/institutions/{university.id}/review", json={
            "action": "defer", "reason": reason,
        })
        assert response.status_code == 200, response.text
        db.expire_all()
        saved = db.get(InstitutionReview, review.id)
        event = db.scalar(select(InstitutionReviewEvent).where(
            InstitutionReviewEvent.review_id == review.id))
        assert saved.status == "deferred" and saved.review_reason == reason
        assert event.action == "defer" and event.reason == reason


class TestProgramPublicationReview:
    def _candidate(self, db, *, with_institution_link=True, verified_program_page=True):
        source = _permitted_source(db)
        source_key = (source.metadata_json or {}).get("adapter_key") or source.name
        document = SourceDocument(source_id=source.id,
            canonical_url="https://example.org/official-masters",
            title="Official Master's catalogue", content_hash=f"publication-{uuid.uuid4()}",
            http_status=200, fetch_status="fetched")
        db.add(document)
        country_code = db.scalar(select(University.country_code).limit(1))
        university = University(canonical_name=f"Published University {uuid.uuid4().hex[:8]}",
            slug=f"published-university-{uuid.uuid4().hex[:8]}", country_code=country_code,
            official_website_url="https://example.org",
            external_identifiers={"ror": f"https://ror.org/{uuid.uuid4().hex[:9]}"})
        db.add(university)
        db.flush()
        db.add(InstitutionReview(university_id=university.id, status="approved"))
        program = Program(university_id=university.id, country_code=country_code,
            canonical_name=f"Master of Evidence {uuid.uuid4().hex[:6]}",
            slug=f"master-evidence-{uuid.uuid4().hex[:12]}", degree_level="masters",
            official_program_url="https://example.org/official-masters",
            publication_status="candidate")
        db.add(program)
        db.flush()
        external_key = f"example:{uuid.uuid4()}"
        db.add(ProgramIdentifier(program_id=program.id, source_id=source.id,
            source_document_id=document.id, source_key=source_key,
            external_key=external_key, normalized_external_key=external_key.casefold(),
            claim_status="accepted"))
        title_fact = FactRecord(entity_type="program", entity_id=program.id,
            fact_key="program_title_as_reported", current_status="candidate")
        db.add(title_fact)
        db.flush()
        title_version = FactVersion(fact_record_id=title_fact.id, version_number=1,
            value_json={"title": program.canonical_name}, status="candidate")
        db.add(title_version)
        db.flush()
        title_fact.current_version_id = title_version.id
        db.add(FactEvidence(fact_version_id=title_version.id, source_document_id=document.id,
            evidence_excerpt=program.canonical_name, evidence_locator=f"programs[{external_key}]"))
        if verified_program_page:
            page_fact = FactRecord(entity_type="program", entity_id=program.id,
                fact_key="official_program_page_url", applicability_key="",
                current_status="verified")
            db.add(page_fact)
            db.flush()
            page_version = FactVersion(fact_record_id=page_fact.id, version_number=1,
                value_json={"url": "https://example.org/official-masters"},
                normalized_value_json={"url": "https://example.org/official-masters"},
                status="verified")
            db.add(page_version)
            db.flush()
            page_fact.current_version_id = page_version.id
            db.add(FactEvidence(fact_version_id=page_version.id,
                source_document_id=document.id,
                evidence_excerpt=f"The page identifies {program.canonical_name}.",
                evidence_locator="programme[example]"))
        if with_institution_link:
            db.add(InstitutionIdentifier(university_id=university.id, source_id=source.id,
                source_document_id=document.id, source_key=source_key, namespace="publisher_unit",
                identifier_value="institution-42", normalized_value="institution-42",
                scope="institution", claim_status="accepted"))
        db.commit()
        return program, university

    def test_reviewer_publishes_only_with_source_and_institution_evidence(self, db, client):
        email = _register(client, "program-pub")
        reviewer = _grant(db, email, "reviewer")
        _login(client, email)
        program, _ = self._candidate(db)

        queue = client.get("/api/v1/admin/program-publication-reviews?status=candidate")
        assert queue.status_code == 200
        item = next(row for row in queue.json()["items"] if row["id"] == str(program.id))
        assert item["can_publish"] is True and item["source_identities"]
        assert client.get(f"/api/v1/programs/{program.id}").status_code == 404
        assert client.post(f"/api/v1/admin/programs/{program.id}/publish", json={}).status_code == 422

        response = client.post(f"/api/v1/admin/programs/{program.id}/publish",
                               json={"reason": "The official source document confirms the institution and program identity."})
        assert response.status_code == 200, response.text
        assert response.json()["publication_status"] == "published"
        assert response.json()["published_at"]
        assert client.get(f"/api/v1/programs/{program.id}").status_code == 200
        detail = client.get(f"/api/v1/programs/{program.id}").json()
        assert detail["official_program_url_status"] == "verified"
        assert detail["official_program_url"] == "https://example.org/official-masters"
        assert client.post(f"/api/v1/admin/programs/{program.id}/publish",
                           json={"reason": "The official source confirms this program identity for publication."}).status_code == 409
        audit = db.scalar(select(AuditEvent).where(
            AuditEvent.action == "program_published", AuditEvent.entity_id == program.id))
        assert audit is not None and audit.actor_user_id == reviewer.id
        assert audit.reason == "The official source document confirms the institution and program identity."

        hidden = client.post(f"/api/v1/admin/programs/{program.id}/unpublish",
                             json={"reason": "The source page changed, so its evidence needs review before publication."})
        assert hidden.status_code == 200 and hidden.json()["publication_status"] == "hidden"
        assert client.get(f"/api/v1/programs/{program.id}").status_code == 404
        assert db.scalar(select(ProgramIdentifier.id).where(
            ProgramIdentifier.program_id == program.id)) is not None
        assert db.scalar(select(AuditEvent.id).where(
            AuditEvent.action == "program_unpublished", AuditEvent.entity_id == program.id))

    def test_publication_requires_reviewed_institution_identity_and_reviewer_role(self, db, client):
        program, _ = self._candidate(db, with_institution_link=False)
        student = _register(client, "program-pub-student")
        _login(client, student)
        assert client.get("/api/v1/admin/program-publication-reviews").status_code == 403
        assert client.post(f"/api/v1/admin/programs/{program.id}/publish",
                           json={"reason": "Not authorized."}).status_code == 403

        reviewer = _register(client, "program-pub-reviewer")
        _grant(db, reviewer, "reviewer")
        _login(client, reviewer)
        response = client.post(f"/api/v1/admin/programs/{program.id}/publish",
                               json={"reason": "The official evidence confirms this identity, but its institution link is missing."})
        assert response.status_code == 409
        assert "institution link" in response.json()["error"]["message"]
        db.expire_all()
        assert db.get(Program, program.id).publication_status == "candidate"

    def test_publication_rejects_generic_reasons_without_changing_state(self, db, client):
        program, _ = self._candidate(db)
        reviewer = _register(client, "program-pub-reason")
        _grant(db, reviewer, "reviewer")
        _login(client, reviewer)

        for reason in ("good", "checking", "This is a good reason to publish this program."):
            response = client.post(f"/api/v1/admin/programs/{program.id}/publish",
                                   json={"reason": reason})
            assert response.status_code == 422
            assert "source or evidence" in response.json()["error"]["details"][0]["message"]
        assert db.get(Program, program.id).publication_status == "candidate"

    def test_publication_rejects_unsuccessful_source_document(self, db, client):
        program, _ = self._candidate(db)
        claim = db.scalar(select(ProgramIdentifier).where(ProgramIdentifier.program_id == program.id))
        db.get(SourceDocument, claim.source_document_id).http_status = 404
        db.commit()
        reviewer = _register(client, "program-pub-bad-document")
        _grant(db, reviewer, "reviewer")
        _login(client, reviewer)
        item = next(row for row in client.get(
            "/api/v1/admin/program-publication-reviews?status=candidate&page_size=100").json()["items"]
            if row["id"] == str(program.id))
        assert item["can_publish"] is False
        assert item["program_page_evidence"]["status"] == "unverified_candidate"
        assert "reviewer-verified fact" in item["publication_blocker"]
        response = client.post(f"/api/v1/admin/programs/{program.id}/publish",
                               json={"reason": "The source retrieval failed, so its official document cannot support publication."})
        assert response.status_code == 409
        assert db.get(Program, program.id).publication_status == "candidate"

    def test_publication_requires_reviewed_program_page_fact(self, db, client):
        program, _ = self._candidate(db, verified_program_page=False)
        reviewer = _register(client, "program-pub-page-review")
        _grant(db, reviewer, "reviewer")
        _login(client, reviewer)
        item = next(row for row in client.get(
            "/api/v1/admin/program-publication-reviews?status=candidate&page_size=100").json()["items"]
            if row["id"] == str(program.id))
        assert item["can_publish"] is False
        assert item["program_page_evidence"]["status"] == "unverified_candidate"
        assert "reviewer-verified fact" in item["publication_blocker"]
        response = client.post(f"/api/v1/admin/programs/{program.id}/publish",
            json={"reason": "The source evidence confirms the course page and its institution identity."})
        assert response.status_code == 409
        assert db.get(Program, program.id).publication_status == "candidate"


class TestFactDetailAndActions:
    def test_fact_detail_shows_versions_evidence_and_events(self, db, client):
        admin = _register(client)
        _grant(db, admin, "admin", "reviewer")
        _login(client, admin)
        fact = _candidate_fact(db)

        detail = client.get(f"/api/v1/admin/facts/{fact.id}").json()
        assert detail["fact_id"] == str(fact.id)
        assert detail["current_version_id"]
        assert detail["versions"], "seeded fact must carry version history"
        version = detail["versions"][0]
        assert version["status"] in ("candidate", "unverified", "estimated")
        assert version["evidence"], "version links to evidence"
        evidence = version["evidence"][0]
        assert evidence["supports_or_conflicts"] in ("supports", "conflicts")
        assert evidence["source"]["name"] and evidence["canonical_url"].startswith("http")
        assert evidence["source"]["allowed_use_policy"]
        assert isinstance(detail["review_events"], list)

        assert client.get(f"/api/v1/admin/facts/{uuid.uuid4()}").status_code == 404

    def test_approve_persists_review_and_audit(self, db, client):
        admin = _register(client)
        user = _grant(db, admin, "admin", "reviewer")
        _login(client, admin)
        fact = _candidate_fact(db)

        r = client.post(f"/api/v1/admin/facts/{fact.id}/approve",
                        json={"reason": "checked against official page"})
        assert r.status_code == 200
        assert r.json()["current_status"] == "verified"
        assert r.json()["version_status"] == "verified"

        # second approve of the same version conflicts
        assert client.post(f"/api/v1/admin/facts/{fact.id}/approve").status_code == 409

        db.expire_all()
        stored = db.get(FactRecord, fact.id)
        assert stored.current_status == "verified"
        version = db.get(FactVersion, stored.current_version_id)
        assert version.status == "verified" and version.reviewed_by_user_id == user.id
        assert version.reviewed_at is not None
        assert version.review_reason == "checked against official page"
        # history preserved: same version count, same value
        versions = db.scalars(select(FactVersion).where(
            FactVersion.fact_record_id == fact.id)).all()
        assert len(versions) == 1

        events = db.scalars(select(FactReviewEvent).where(
            FactReviewEvent.fact_record_id == fact.id)).all()
        assert [e.action for e in events] == ["approve"]
        audit = db.scalar(select(AuditEvent).where(
            AuditEvent.action == "fact_approved",
            AuditEvent.entity_id == fact.id))
        assert audit is not None and audit.request_id is not None
        assert audit.before_summary["current_status"] == "candidate"
        assert audit.after_summary["current_status"] == "verified"

    def test_reject_requires_reason(self, db, client):
        admin = _register(client)
        _grant(db, admin, "admin", "reviewer")
        _login(client, admin)
        fact = _candidate_fact(db, exclude=())

        missing = client.post(f"/api/v1/admin/facts/{fact.id}/reject", json={})
        assert missing.status_code == 422
        assert missing.json()["error"]["details"][0]["field"] == "reason"

        r = client.post(f"/api/v1/admin/facts/{fact.id}/reject",
                        json={"reason": "conflicts with official fee page"})
        assert r.status_code == 200
        assert r.json()["current_status"] == "rejected"
        assert client.post(f"/api/v1/admin/facts/{fact.id}/reject",
                           json={"reason": "again"}).status_code == 409

        db.expire_all()
        version = db.get(FactVersion, fact.current_version_id)
        assert version.status == "rejected"
        assert version.value_json is not None, "rejected values are kept, not erased"

    def test_request_evidence_moves_to_in_review(self, db, client):
        admin = _register(client)
        _grant(db, admin, "admin", "reviewer")
        _login(client, admin)
        fact = _candidate_fact(db)

        assert client.post(f"/api/v1/admin/facts/{fact.id}/request-evidence",
                           json={}).status_code == 422
        r = client.post(f"/api/v1/admin/facts/{fact.id}/request-evidence",
                        json={"reason": "need the 2027 fee page"})
        assert r.status_code == 200 and r.json()["current_status"] == "in_review"

        db.expire_all()
        assert db.get(FactRecord, fact.id).current_status == "in_review"
        events = db.scalars(select(FactReviewEvent).where(
            FactReviewEvent.fact_record_id == fact.id)).all()
        assert events[0].action == "request_evidence"

    def test_approve_specific_version_and_cross_fact_404(self, db, client):
        admin = _register(client)
        _grant(db, admin, "admin", "reviewer")
        _login(client, admin)
        fact = _candidate_fact(db)
        other = _candidate_fact(db, exclude=(fact.id,))
        old_version_id = fact.current_version_id  # captured before any commit/expire

        # a newer version exists but is not current
        v2 = FactVersion(fact_record_id=fact.id, version_number=2,
                         value_json={**db.get(FactVersion, old_version_id).value_json,
                                     "reviewed_fixture_version": 2}, status="candidate")
        db.add(v2)
        db.commit()

        r = client.post(f"/api/v1/admin/facts/{fact.id}/approve",
                        json={"version_id": str(v2.id)})
        assert r.status_code == 200
        assert r.json()["version_id"] == str(v2.id)
        db.expire_all()
        stored = db.get(FactRecord, fact.id)
        assert stored.current_version_id == v2.id
        assert stored.current_status == "verified"
        # the superseded version keeps its own status (append-only history)
        assert db.get(FactVersion, old_version_id).status == "candidate"

        # version from another fact is rejected
        r = client.post(f"/api/v1/admin/facts/{fact.id}/approve",
                        json={"version_id": str(uuid.uuid4())})
        assert r.status_code == 404
        other_v = db.scalar(select(FactVersion).where(
            FactVersion.fact_record_id == other.id).limit(1))
        r = client.post(f"/api/v1/admin/facts/{fact.id}/approve",
                        json={"version_id": str(other_v.id)})
        assert r.status_code == 404

    def test_fact_without_current_version_conflicts(self, db, client):
        admin = _register(client)
        _grant(db, admin, "admin", "reviewer")
        _login(client, admin)
        fact = FactRecord(entity_type="other", entity_id=uuid.uuid4(),
                          fact_key="unit_test_key", applicability_key="",
                          current_status="candidate", current_version_id=None)
        db.add(fact)
        db.commit()
        r = client.post(f"/api/v1/admin/facts/{fact.id}/approve", json={})
        assert r.status_code == 409


class TestSourcesAndJobs:
    def test_legacy_job_metrics_are_labeled_without_rewriting_aggregates(self):
        from app.services.admin import _job_metrics

        legacy = IngestionJob(
            job_type="refresh", status="succeeded", records_seen=9,
            records_created=3, records_review_required=2,
            checkpoint={"entities": {"institutions_seen": 4, "programs_seen": 5},
                        "facts": {"created": 6, "review": 2}})
        metrics = _job_metrics(legacy)
        assert metrics["version"] == 1
        assert metrics["quality"] == "legacy_partial"
        assert metrics["entities"]["institutions_seen"] == 4
        assert metrics["conflicted"] is None
        assert "not separately recorded" in metrics["semantics"]["conflicted"]
        assert legacy.records_seen == 9 and legacy.records_created == 3

    def test_source_crud_and_validation(self, db, client):
        admin = _register(client)
        _grant(db, admin, "admin", "reviewer")
        _login(client, admin)

        listing = client.get("/api/v1/admin/sources").json()
        assert listing["total_items"] >= 1
        demo = listing["items"][0]
        assert demo["document_count"] >= 0 and demo["job_count"] >= 0
        assert demo["metadata"] == {"demo_fixture": True}
        assert client.get(f"/api/v1/admin/sources/{demo['id']}").json()["documents"] is not None
        assert client.get(f"/api/v1/admin/sources/{uuid.uuid4()}").status_code == 404

        r = client.post("/api/v1/admin/sources", json={
            "name": "Registry Test Source", "base_url": "https://example.org/official",
            "source_type": "government", "authority_tier": 2,
            "allowed_use_policy": "permitted_fetch", "refresh_interval_hours": 168})
        assert r.status_code == 201 and r.json()["enabled"] is True
        sid = r.json()["id"]

        # invalid enum choices and unknown fields
        for payload in (
            {"name": "x", "base_url": "https://x.example", "source_type": "banana"},
            {"name": "x", "base_url": "https://x.example", "allowed_use_policy": "banana"},
            {"name": "x", "base_url": "ftp://x.example"},
            {"name": "x", "base_url": "https://x.example", "authority_tier": 9},
            {"name": "x", "base_url": "https://x.example", "surprise": True},
        ):
            assert client.post("/api/v1/admin/sources", json=payload).status_code == 422, payload

        # patch: allowed fields apply and are audited with before/after
        p = client.patch(f"/api/v1/admin/sources/{sid}",
                         json={"license_notes": "public domain", "enabled": False})
        assert p.status_code == 200
        assert p.json()["license_notes"] == "public domain" and p.json()["enabled"] is False
        assert client.patch(f"/api/v1/admin/sources/{sid}", json={}).status_code == 422
        # immutable-after-registration fields
        assert client.patch(f"/api/v1/admin/sources/{sid}",
                            json={"base_url": "https://other.example"}).status_code == 422

        db.expire_all()
        audit = db.scalars(select(AuditEvent).where(
            AuditEvent.action == "source_updated",
            AuditEvent.entity_id == uuid.UUID(sid)).order_by(AuditEvent.created_at.desc())).first()
        assert audit.before_summary["enabled"] is True
        assert audit.after_summary["enabled"] is False

    def test_refresh_respects_use_policy_and_is_idempotent(self, db, client):
        admin = _register(client)
        _grant(db, admin, "admin", "reviewer")
        _login(client, admin)

        listing = client.get("/api/v1/admin/sources?page_size=100").json()["items"]
        demo = next(s for s in listing if s["allowed_use_policy"] == "manual_reference")
        forbidden = client.post(f"/api/v1/admin/sources/{demo['id']}/refresh")
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "REFRESH_NOT_PERMITTED"
        assert client.post(f"/api/v1/admin/sources/{uuid.uuid4()}/refresh").status_code == 404

        source = _permitted_source(db)
        first = client.post(f"/api/v1/admin/sources/{source.id}/refresh").json()
        assert first["status"] == "queued" and first["reused"] is False
        again = client.post(f"/api/v1/admin/sources/{source.id}/refresh").json()
        assert again["id"] == first["id"] and again["reused"] is True

        db.expire_all()
        audit = db.scalar(select(AuditEvent).where(
            AuditEvent.action == "job_enqueued", AuditEvent.entity_id == uuid.UUID(first["id"])))
        assert audit is not None

    def test_worker_drains_honestly_without_fake_success(self, db, client):
        from app.core.scheduler import drain_queued_jobs

        admin = _register(client)
        _grant(db, admin, "admin", "reviewer")
        _login(client, admin)
        drain_queued_jobs()  # clear anything left by earlier tests

        source = _permitted_source(db)
        job = client.post(f"/api/v1/admin/sources/{source.id}/refresh").json()
        assert drain_queued_jobs() == 1

        detail = client.get(f"/api/v1/admin/jobs/{job['id']}").json()
        assert detail["status"] == "partial"  # not "succeeded": this source has no connector
        assert detail["worker_version"] == "ingestion-worker-1"
        assert detail["records_seen"] == 0 and detail["records_created"] == 0
        assert "no candidate facts" in detail["error_summary"]
        assert detail["started_at"] and detail["finished_at"]
        assert isinstance(detail["items"], list)
        assert "candidate_payload" not in str(detail["items"])
        # queue is empty now
        assert drain_queued_jobs() == 0

    def test_worker_fails_for_disabled_source(self, db, client):
        from app.core.scheduler import drain_queued_jobs

        admin = _register(client)
        _grant(db, admin, "admin", "reviewer")
        _login(client, admin)
        drain_queued_jobs()

        source = _permitted_source(db)
        assert client.patch(f"/api/v1/admin/sources/{source.id}",
                            json={"enabled": True}).status_code == 200
        job = client.post(f"/api/v1/admin/sources/{source.id}/refresh").json()
        assert client.patch(f"/api/v1/admin/sources/{source.id}",
                            json={"enabled": False}).status_code == 200
        drain_queued_jobs()

        detail = client.get(f"/api/v1/admin/jobs/{job['id']}").json()
        assert detail["status"] == "failed"
        assert "disabled" in detail["error_summary"]
        # re-enable for later tests
        client.patch(f"/api/v1/admin/sources/{source.id}", json={"enabled": True})

    def test_job_listing_filters_and_detail_hides_payloads(self, db, client):
        admin = _register(client)
        user = _grant(db, admin, "admin", "reviewer")
        _login(client, admin)

        listing = client.get("/api/v1/admin/jobs?page_size=50").json()
        if listing["total_items"] == 0:  # standalone runs: ensure at least one job exists
            source = _permitted_source(db)
            client.post(f"/api/v1/admin/sources/{source.id}/refresh")
            listing = client.get("/api/v1/admin/jobs?page_size=50").json()
        assert listing["total_items"] >= 1
        assert client.get("/api/v1/admin/jobs?status=queued").json()["total_items"] >= 0
        assert client.get("/api/v1/admin/jobs?status=bogus").status_code == 422
        assert client.get("/api/v1/admin/jobs?job_type=bogus").status_code == 422
        source_id = listing["items"][0]["source_id"]
        narrowed = client.get(f"/api/v1/admin/jobs?source_id={source_id}").json()
        assert all(i["source_id"] == source_id for i in narrowed["items"])

        # detail excludes raw candidate payloads even when items exist
        job_id = listing["items"][0]["id"]
        db.add(IngestionJobItem(job_id=uuid.UUID(job_id), entity_type="program",
                                external_key="fixture-key", status="skipped",
                                candidate_payload={"raw": "private"},
                                validation_errors={"amount": "missing"}))
        db.commit()
        detail = client.get(f"/api/v1/admin/jobs/{job_id}").json()
        assert detail["items"][0]["external_key"] == "fixture-key"
        assert "raw" not in str(detail["items"])
        assert detail["items"][0]["validation_errors"] == {"amount": "missing"}
        assert client.get(f"/api/v1/admin/jobs/{uuid.uuid4()}").status_code == 404

    def test_retry_only_for_failed_or_cancelled(self, db, client):
        from app.core.scheduler import drain_queued_jobs

        admin = _register(client)
        _grant(db, admin, "admin", "reviewer")
        _login(client, admin)
        source = _permitted_source(db)

        # queued job cannot be retried
        queued = client.post(f"/api/v1/admin/sources/{source.id}/refresh").json()
        assert client.post(f"/api/v1/admin/jobs/{queued['id']}/retry").status_code == 409

        failed = IngestionJob(source_id=source.id, job_type="refresh", status="failed",
                              records_seen=7, records_created=2, error_summary="boom")
        db.add(failed)
        db.commit()

        r = client.post(f"/api/v1/admin/jobs/{failed.id}/retry")
        assert r.status_code == 200
        assert r.json()["status"] == "queued"
        assert r.json()["records_seen"] == 0 and r.json()["records_created"] == 0
        assert r.json()["error_summary"] is None
        # retried job conflicts until it finishes again
        assert client.post(f"/api/v1/admin/jobs/{failed.id}/retry").status_code == 409
        assert client.post(f"/api/v1/admin/jobs/{uuid.uuid4()}/retry").status_code == 404

        db.expire_all()
        audit = db.scalar(select(AuditEvent).where(
            AuditEvent.action == "job_retried", AuditEvent.entity_id == failed.id))
        assert audit is not None and audit.before_summary["status"] == "failed"
        drain_queued_jobs()  # leave the queue empty for later tests


class TestAuditEvents:
    def test_audit_filtering_and_contents(self, db, client):
        admin = _register(client)
        user = _grant(db, admin, "admin", "reviewer")
        _login(client, admin)

        # produce a fresh, attributable event through the API
        fact = _candidate_fact(db)
        client.post(f"/api/v1/admin/facts/{fact.id}/approve", json={"reason": "audit trail"})

        listing = client.get("/api/v1/admin/audit-events?page_size=50").json()
        assert listing["total_items"] >= 1
        by_action = client.get("/api/v1/admin/audit-events?action=fact_approved").json()
        assert by_action["total_items"] >= 1
        entry = next(e for e in by_action["items"] if e["entity_id"] == str(fact.id))
        assert entry["actor_user_id"] == str(user.id)
        assert entry["actor_type"] == "user"
        assert entry["request_id"]
        assert entry["reason"] == "audit trail"
        assert entry["after_summary"]["current_status"] == "verified"
        assert entry["created_at"]

        by_actor = client.get(f"/api/v1/admin/audit-events?actor_user_id={user.id}").json()
        assert by_actor["total_items"] >= 1
        assert all(i["actor_user_id"] == str(user.id) for i in by_actor["items"])

        by_entity = client.get(
            "/api/v1/admin/audit-events?entity_type=fact_record").json()
        assert by_entity["total_items"] >= 1
        assert all(i["entity_type"] == "fact_record" for i in by_entity["items"])

        future = datetime(2100, 1, 1, tzinfo=timezone.utc).isoformat()
        assert client.get("/api/v1/admin/audit-events",
                          params={"since": future}).json()["total_items"] == 0

        unknown_action = client.get("/api/v1/admin/audit-events?action=no_such_action").json()
        assert unknown_action["total_items"] == 0


class TestSchedulerToggle:
    def test_scheduler_starts_only_when_enabled(self):
        from app.core.scheduler import start_scheduler

        assert settings.enable_scheduler is False  # off by default (tests + local)
        assert start_scheduler() is None

        settings.enable_scheduler = True
        try:
            scheduler = start_scheduler()
            assert scheduler is not None and scheduler.running
            assert any(job.id == "drain_queued_jobs" for job in scheduler.get_jobs())
            scheduler.shutdown(wait=False)
        finally:
            settings.enable_scheduler = False
