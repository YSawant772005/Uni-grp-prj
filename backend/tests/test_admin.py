"""Phase 7: review queue, fact review actions, sources, jobs and audit (§5.10).

Covers role gates, append-only review history, honest worker outcomes (no fake
success), idempotent enqueue/retry and audit-event filtering.
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.seed import run_seed
from app.models import (
    AuditEvent,
    FactRecord,
    FactReviewEvent,
    FactVersion,
    IngestionJob,
    IngestionJobItem,
    Role,
    Source,
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
    assert "_test" in settings.database_url, "tests require a *_test database"
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
                         value_json={"amount": 12345}, status="candidate")
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
        assert detail["status"] == "partial"  # not "succeeded": no fetch pipeline in MVP
        assert detail["worker_version"] == "mvp-worker-1"
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
