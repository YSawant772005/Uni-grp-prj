"""API core + auth tests: error envelope, health, registration/login/session,
no account enumeration, cookie auth, bearer auth and rate limiting."""
from __future__ import annotations

import uuid

import pytest

from app.core.config import settings
from app.routers.v1.auth import limiter


@pytest.fixture(autouse=True)
def generous_rate_limit():
    previous = settings.rate_limit_auth
    settings.rate_limit_auth = "1000/minute"
    yield
    settings.rate_limit_auth = previous


def _register(client, email=None, password="Sup3rSecret!"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email or f"user-{uuid.uuid4().hex[:10]}@example.com",
              "password": password, "display_name": "Test"},
    )


class TestHealthAndMeta:
    def test_live(self, client):
        r = client.get("/api/v1/health/live")
        assert r.status_code == 200 and r.json() == {"status": "ok"}

    def test_ready(self, client):
        r = client.get("/api/v1/health/ready")
        assert r.status_code == 200 and r.json()["database"] == "ok"

    def test_meta(self, client):
        r = client.get("/api/v1/meta")
        body = r.json()
        assert r.status_code == 200 and body["base_path"] == "/api/v1"

    def test_unknown_route_uses_error_envelope(self, client):
        r = client.get("/api/v1/definitely-not-a-route")
        body = r.json()["error"]
        assert r.status_code == 404
        assert body["code"] == "NOT_FOUND"
        assert body["request_id"] == r.headers.get("X-Request-Id")

    def test_every_error_carries_request_id(self, client):
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401
        assert r.json()["error"]["request_id"]


class TestRegistration:
    def test_register_returns_student_and_sets_cookies(self, client):
        r = _register(client)
        assert r.status_code == 201
        body = r.json()
        assert body["roles"] == ["student"]
        assert "access_token" in r.cookies
        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200 and me.json()["email"] == body["email"]

    def test_duplicate_email_conflicts(self, client):
        email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
        assert _register(client, email=email).status_code == 201
        r = _register(client, email=email)
        assert r.status_code == 409 and r.json()["error"]["code"] == "EMAIL_TAKEN"

    def test_invalid_email_is_validation_error(self, client):
        r = client.post("/api/v1/auth/register", json={"email": "not-an-email", "password": "Sup3rSecret!"})
        assert r.status_code == 422
        err = r.json()["error"]
        assert err["code"] == "VALIDATION_ERROR" and any(d["field"] == "email" for d in err["details"])

    def test_short_password_rejected(self, client):
        r = _register(client, password="short")
        assert r.status_code == 422


class TestLoginSession:
    def test_no_account_enumeration(self, client):
        unknown = client.post("/api/v1/auth/login",
                              json={"email": "nobody-here@example.com", "password": "whatever12"})
        email = f"user-{uuid.uuid4().hex[:8]}@example.com"
        _register(client, email=email)
        wrong = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
        assert unknown.status_code == wrong.status_code == 401
        unknown_err, wrong_err = unknown.json()["error"], wrong.json()["error"]
        # identical error shape and wording: no way to tell registered from unregistered
        assert (unknown_err["code"], unknown_err["message"]) == (wrong_err["code"], wrong_err["message"])

    def test_suspended_user_cannot_login(self, client, db):
        from app.models import User, UserStatus
        from app.services import accounts

        email = f"sus-{uuid.uuid4().hex[:8]}@example.com"
        accounts.create_account(db, email=email, password="Sup3rSecret!", display_name=None)
        db.query(User).filter(User.email == email).update({"status": UserStatus.suspended})
        db.commit()
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "Sup3rSecret!"})
        assert r.status_code == 401

    def test_login_logout_flow(self, client):
        email = f"user-{uuid.uuid4().hex[:8]}@example.com"
        _register(client, email=email)
        client.post("/api/v1/auth/logout")
        assert client.get("/api/v1/auth/me").status_code == 401
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "Sup3rSecret!"})
        assert r.status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 200
        out = client.post("/api/v1/auth/logout")
        assert out.status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_refresh_rotates_session(self, client):
        email = f"user-{uuid.uuid4().hex[:8]}@example.com"
        _register(client, email=email)
        client.cookies.clear()
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "Sup3rSecret!"})
        assert r.status_code == 200
        assert "refresh_token" in client.cookies
        client.cookies.clear()
        refresh_only = {"refresh_token": r.cookies["refresh_token"]}
        client.cookies.update(refresh_only)
        refreshed = client.post("/api/v1/auth/refresh")
        assert refreshed.status_code == 200 and "access_token" in refreshed.cookies

    def test_me_rejects_missing_and_bogus_tokens(self, client):
        client.cookies.clear()
        assert client.get("/api/v1/auth/me").status_code == 401
        client.cookies.set("access_token", "garbage.token.value")
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_bearer_header_accepted(self, client):
        email = f"user-{uuid.uuid4().hex[:8]}@example.com"
        r = _register(client, email=email)
        token = r.cookies["access_token"]
        client.cookies.clear()
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200 and me.json()["email"] == email


class TestRateLimiting:
    def test_auth_endpoints_rate_limited(self, client):
        settings.rate_limit_auth = "3/minute"
        limiter.reset()
        try:
            payload = {"email": "limited@example.com", "password": "wrong-password"}
            codes = [client.post("/api/v1/auth/login", json=payload).status_code for _ in range(4)]
            assert codes[:3] == [401, 401, 401]
            assert codes[3] == 429
            assert client.post("/api/v1/auth/login", json=payload).json()["error"]["code"] == "RATE_LIMITED"
        finally:
            limiter.reset()
            settings.rate_limit_auth = "1000/minute"
