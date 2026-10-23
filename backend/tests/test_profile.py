"""Profile & onboarding API tests: auth, validation, PUT/PATCH semantics,
completeness and per-user isolation."""
import uuid

import pytest

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.seed import run_seed
from conftest import _truncate_all

VALID_ONBOARDING = {
    "intended_degree_level": "masters", "field": "data_science",
    "country_preferences": [{"country_code": "DE", "is_mandatory": True}, {"country_code": "NL"}],
    "academic_degree": "B.Tech", "institution_name": "Test University",
    "grade_value": 8.2, "grade_scale_min": 0, "grade_scale_max": 10, "grade_system": "cgpa",
    "graduation_status": "completed", "graduation_year": 2024,
    "english_test_status": "completed", "english_test_type": "ielts", "english_test_overall": 7.0,
    "budget_amount": 25000, "budget_currency": "EUR", "budget_basis": "full_degree_all_in",
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
    session = SessionLocal()
    _truncate_all(session)
    run_seed(session)
    yield session
    session.close()


@pytest.fixture()
def db(_seeded):
    yield _seeded
    _seeded.rollback()


def _register(client, email=None):
    email = email or f"u-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "Sup3rSecret!"})
    assert r.status_code == 201
    return r


class TestProfileAccess:
    def test_requires_auth(self, client):
        client.cookies.clear()
        assert client.get("/api/v1/profile").status_code == 401

    def test_fresh_profile_low_completeness(self, db, client):
        _register(client)
        body = client.get("/api/v1/profile").json()
        assert body["intended_degree_level"] == "masters"  # sensible default
        c = client.get("/api/v1/profile/completeness").json()
        assert c["required_complete"] is False and c["percentage"] < 100

    def test_profiles_are_per_user(self, db, client):
        _register(client, "alice-x@example.com")
        client.put("/api/v1/profile", json={"intended_degree_level": "masters",
                                            "career_goal": "Alice goal"})
        client.cookies.clear()
        _register(client, "bob-x@example.com")
        body = client.get("/api/v1/profile").json()
        assert body["career_goal"] is None


class TestPutPatchSemantics:
    def test_put_replaces_and_resets(self, db, client):
        _register(client)
        client.patch("/api/v1/profile", json={"career_goal": "keep? no"})
        body = client.put("/api/v1/profile", json={"intended_degree_level": "masters",
                                                   "academic_degree": "B.Sc"}).json()
        assert body["career_goal"] is None
        assert body["academic_degree"] == "B.Sc"

    def test_patch_only_touches_provided_fields(self, db, client):
        _register(client)
        client.patch("/api/v1/profile", json={"academic_degree": "B.Sc", "institution_name": "X"})
        body = client.patch("/api/v1/profile", json={"career_goal": "ML engineer"}).json()
        assert body["career_goal"] == "ML engineer"
        assert body["academic_degree"] == "B.Sc"  # untouched

    def test_invalid_enum_422(self, db, client):
        _register(client)
        r = client.patch("/api/v1/profile", json={"risk_tolerance": "yolo"})
        assert r.status_code == 422
        assert r.json()["error"]["details"][0]["code"] == "invalid_choice"

    def test_grade_value_must_fit_scale(self, db, client):
        _register(client)
        r = client.patch("/api/v1/profile", json={"grade_value": 99, "grade_scale_min": 0,
                                                  "grade_scale_max": 10, "grade_system": "cgpa"})
        assert r.status_code == 422
        assert r.json()["error"]["details"][0]["code"] == "out_of_range"

    def test_budget_amount_requires_currency_and_basis(self, db, client):
        _register(client)
        r = client.patch("/api/v1/profile", json={"budget_amount": 10000})
        codes = {d["field"] for d in r.json()["error"]["details"]}
        assert r.status_code == 422 and {"budget_currency", "budget_basis"} <= codes

    def test_unknown_field_and_country_422(self, db, client):
        _register(client)
        assert client.patch("/api/v1/profile", json={"field": "astrology"}).status_code == 422
        r = client.patch("/api/v1/profile", json={"country_preferences": [{"country_code": "XX"}]})
        assert r.status_code == 422

    def test_duplicate_preference_ranks_422(self, db, client):
        _register(client)
        r = client.patch("/api/v1/profile", json={
            "country_preferences": [{"country_code": "DE", "preference_rank": 1},
                                    {"country_code": "NL", "preference_rank": 1}]})
        assert r.status_code == 422

    def test_priorities_normalized_to_weight_range(self, db, client):
        _register(client)
        body = client.patch("/api/v1/profile", json={
            "priorities": [{"priority_key": "cost", "weight": 5},
                           {"priority_key": "career", "weight": 3}]}).json()
        by_key = {p["priority_key"]: p["weight"] for p in body["priorities"]}
        assert float(by_key["cost"]) == 1.0 and float(by_key["career"]) == 0.6

    def test_invalid_priority_key_422(self, db, client):
        _register(client)
        r = client.patch("/api/v1/profile", json={
            "priorities": [{"priority_key": "vibes", "weight": 3}]})
        assert r.status_code == 422


class TestOnboarding:
    def test_complete_onboarding(self, db, client):
        _register(client)
        r = client.post("/api/v1/profile/onboarding/complete", json=VALID_ONBOARDING)
        assert r.status_code == 200
        body = r.json()
        assert body["completeness"]["required_complete"] is True
        assert body["completeness"]["percentage"] == 100
        assert body["profile"]["profile_completed_at"]
        assert [p["country_code"] for p in body["profile"]["country_preferences"]] == ["DE", "NL"]
        assert body["profile"]["country_preferences"][0]["is_mandatory"] is True

    def test_completed_english_needs_score(self, db, client):
        _register(client)
        payload = {**VALID_ONBOARDING, "english_test_overall": None}
        r = client.post("/api/v1/profile/onboarding/complete", json=payload)
        assert r.status_code == 422
        assert any(d["field"] == "english_test_overall" for d in r.json()["error"]["details"])

    def test_not_taken_english_needs_no_score(self, db, client):
        _register(client)
        payload = {**VALID_ONBOARDING, "english_test_status": "not_taken",
                   "english_test_type": None, "english_test_overall": None}
        r = client.post("/api/v1/profile/onboarding/complete", json=payload)
        assert r.status_code == 200 and r.json()["completeness"]["required_complete"] is True

    def test_unknown_country_rejected(self, db, client):
        _register(client)
        payload = {**VALID_ONBOARDING, "country_preferences": [{"country_code": "XX"}]}
        assert client.post("/api/v1/profile/onboarding/complete", json=payload).status_code == 422

    def test_unknown_field_rejected(self, db, client):
        _register(client)
        payload = {**VALID_ONBOARDING, "field": "astrology"}
        assert client.post("/api/v1/profile/onboarding/complete", json=payload).status_code == 422

    def test_completeness_reflects_onboarding(self, db, client):
        _register(client)
        client.post("/api/v1/profile/onboarding/complete", json=VALID_ONBOARDING)
        c = client.get("/api/v1/profile/completeness").json()
        required = {i["key"]: i["complete"] for i in c["items"] if i["required"]}
        assert all(required.values()) and c["required_complete"] is True
