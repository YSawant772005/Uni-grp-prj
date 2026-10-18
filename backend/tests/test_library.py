"""Phase 6a: saved programs, normalized compare and saved comparisons (§5.6)."""
import uuid

import pytest

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.seed import run_seed
from app.models import Program
from conftest import _truncate_all

ONBOARDING = {
    "intended_degree_level": "masters", "field": "computer_science",
    "country_preferences": [{"country_code": "DE", "is_mandatory": True}],
    "academic_degree": "B.Tech", "institution_name": "Test University",
    "grade_value": 8.5, "grade_scale_min": 0, "grade_scale_max": 10, "grade_system": "cgpa",
    "graduation_status": "completed", "graduation_year": 2024,
    "english_test_status": "completed", "english_test_type": "ielts", "english_test_overall": 7.5,
    "budget_amount": 60000, "budget_currency": "EUR", "budget_basis": "full_degree_all_in",
    "target_intake_year": 2027, "target_intake_term": "fall",
}


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


def _register(client):
    email = f"lib-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "Sup3rSecret!"})
    assert r.status_code == 201
    return email


def _program_ids(db, limit=8):
    return [str(p.id) for p in db.query(Program).order_by(Program.id).limit(limit).all()]


class TestSavedPrograms:
    def test_requires_auth(self, client):
        client.cookies.clear()
        r = client.post("/api/v1/saved-programs", json={"program_id": str(uuid.uuid4())})
        assert r.status_code == 401
        assert client.get("/api/v1/saved-programs").status_code == 401

    def test_save_list_note_delete(self, db, client):
        _register(client)
        pid = _program_ids(db, 1)[0]
        r = client.post("/api/v1/saved-programs", json={"program_id": pid, "note": "top pick"})
        assert r.status_code == 201 and r.json()["note"] == "top pick"
        assert r.json()["program"]["name"]

        listing = client.get("/api/v1/saved-programs").json()["items"]
        assert len(listing) == 1 and listing[0]["program_id"] == pid

        # resaving is idempotent (no duplicate rows)
        client.post("/api/v1/saved-programs", json={"program_id": pid, "note": "updated"})
        listing = client.get("/api/v1/saved-programs").json()["items"]
        assert len(listing) == 1 and listing[0]["note"] == "updated"

        assert client.request("DELETE", f"/api/v1/saved-programs/{pid}").status_code == 204
        assert client.get("/api/v1/saved-programs").json()["items"] == []
        assert client.request("DELETE", f"/api/v1/saved-programs/{pid}").status_code == 404

    def test_save_unknown_program_404(self, db, client):
        _register(client)
        r = client.post("/api/v1/saved-programs", json={"program_id": str(uuid.uuid4())})
        assert r.status_code == 404


class TestCompare:
    def test_public_without_auth(self, db, client):
        client.cookies.clear()
        p0, p1 = _program_ids(db, 2)
        r = client.post("/api/v1/programs/compare", json={"program_ids": [p0, p1]})
        assert r.status_code == 200 and r.json()["count"] == 2

    def test_duplicates_normalized(self, db, client):
        p0, p1 = _program_ids(db, 2)
        r = client.post("/api/v1/programs/compare", json={"program_ids": [p0, p1, p0]})
        assert r.status_code == 200 and r.json()["count"] == 2

    def test_max_programs_validated(self, db, client):
        ids = _program_ids(db, 8)
        r = client.post("/api/v1/programs/compare", json={"program_ids": ids})
        assert r.status_code == 422
        assert r.json()["error"]["details"][0]["field"] == "program_ids"

    def test_unknown_program_404(self, db, client):
        r = client.post("/api/v1/programs/compare", json={"program_ids": [str(uuid.uuid4())]})
        assert r.status_code == 404

    def test_money_cells_keep_status_source_and_missing_stays_null(self, db, client):
        ids = _program_ids(db, 6)
        items = client.post("/api/v1/programs/compare",
                            json={"program_ids": ids}).json()["items"]
        for item in items:
            cell = item["tuition"]
            assert cell["status"] in ("candidate", "unverified", "estimated",
                                      "unavailable", "verified", "stale", "conflicted")
            if cell["value"] is None:
                # missing must be null + flagged, never zero
                assert cell["status"] == "unavailable"
                assert item["data_quality"]["status"] in ("partial", "unreliable", "missing")
            else:
                assert cell["unit"] in ("EUR", "GBP", "USD", "AUD", "CAD", "INR")
                assert cell["period"] and cell["source"]["url"].startswith("http")
            assert item["data_quality"]["status"] in ("good", "partial", "unreliable", "missing")
            assert isinstance(item["data_quality"]["warnings"], list)

    def test_eligibility_column_only_with_logged_in_profile(self, db, client):
        p0 = _program_ids(db, 1)[0]
        anon = client.post("/api/v1/programs/compare",
                           json={"program_ids": [p0]}).json()["items"][0]
        assert anon["eligibility_status"] is None

        _register(client)
        assert client.post("/api/v1/profile/onboarding/complete",
                           json=ONBOARDING).status_code == 200
        authed = client.post("/api/v1/programs/compare",
                             json={"program_ids": [p0]}).json()["items"][0]
        assert authed["eligibility_status"] in ("eligible", "conditionally_eligible",
                                                "ineligible", "unknown_needs_review")


class TestSavedComparisons:
    def test_crud_flow(self, db, client):
        _register(client)
        p0, p1, p2 = _program_ids(db, 3)
        r = client.post("/api/v1/comparisons",
                        json={"title": "My three", "program_ids": [p0, p1]})
        assert r.status_code == 201
        cid = r.json()["id"]
        assert r.json()["program_ids"] == [p0, p1]
        assert r.json()["positions"] == {p0: 1, p1: 2}

        listing = client.get("/api/v1/comparisons").json()["items"]
        assert [c["id"] for c in listing] == [cid]

        patched = client.patch(f"/api/v1/comparisons/{cid}",
                               json={"title": "Renamed", "program_ids": [p1, p2]})
        assert patched.json()["title"] == "Renamed"
        assert patched.json()["program_ids"] == [p1, p2]

        assert client.request("DELETE", f"/api/v1/comparisons/{cid}").status_code == 204
        assert client.get(f"/api/v1/comparisons/{cid}").status_code == 404

    def test_owner_only(self, db, client):
        _register(client)
        p0, p1 = _program_ids(db, 2)
        cid = client.post("/api/v1/comparisons",
                          json={"title": "mine", "program_ids": [p0, p1]}).json()["id"]
        client.cookies.clear()
        _register(client)
        assert client.get(f"/api/v1/comparisons/{cid}").status_code == 404
        assert client.patch(f"/api/v1/comparisons/{cid}",
                            json={"title": "stolen"}).status_code == 404
        assert client.request("DELETE", f"/api/v1/comparisons/{cid}").status_code == 404

    def test_rejects_empty_and_unknown_programs(self, db, client):
        _register(client)
        assert client.post("/api/v1/comparisons",
                           json={"title": "x", "program_ids": []}).status_code == 422
        r = client.post("/api/v1/comparisons",
                        json={"title": "x", "program_ids": [str(uuid.uuid4())]})
        assert r.status_code == 404
