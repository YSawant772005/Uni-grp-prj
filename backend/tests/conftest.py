"""Test fixtures with a fail-closed isolated PostgreSQL identity gate."""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

# This runs while pytest loads conftest, before test modules import application
# settings, engines, TestClient, fixtures, or destructive helpers.
from app.db.safety import verify_connected, verify_test_target, validate_test_url

_test_url = os.environ.get("TEST_DATABASE_URL")
if os.environ.get("UNISHORTLIST_TEST_MODE") != "1" or not _test_url:
    raise RuntimeError(
        "Refusing pytest startup: set UNISHORTLIST_TEST_MODE=1 and TEST_DATABASE_URL "
        "for the isolated db-test service."
    )
validate_test_url(_test_url)
_database_url = os.environ.get("DATABASE_URL")
if not _database_url or make_url(_database_url) != make_url(_test_url):
    raise RuntimeError("Refusing pytest startup: DATABASE_URL must exactly match TEST_DATABASE_URL.")
_app_database_url = os.environ.get("APP_DATABASE_URL")
if _app_database_url and make_url(_app_database_url) != make_url(_test_url):
    raise RuntimeError("Refusing pytest startup: APP_DATABASE_URL must exactly match TEST_DATABASE_URL.")
os.environ["APP_DATABASE_URL"] = _test_url
verify_test_target(_test_url)

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.seed import run_seed
from app.models import Role, StudentProfile, User, UserRole


def _truncate_all(session: Session) -> None:
    validate_test_url(settings.runtime_database_url)
    verify_connected(session.connection())
    rows = session.execute(
        text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            "AND tablename <> 'alembic_version'"
        )
    ).all()
    if rows:
        names = ", ".join(f'"{r[0]}"' for r in rows)
        session.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
        session.commit()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db():
    session = SessionLocal()
    _truncate_all(session)
    run_seed(session)
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def make_user(db):
    def _make(*role_keys: str, email: str | None = None) -> User:
        user = User(
            email=email or f"user-{uuid.uuid4().hex[:12]}@test.local",
            password_hash="x",
            display_name="Test User",
        )
        db.add(user)
        db.flush()
        for key in role_keys:
            role = db.query(Role).filter(Role.key == key).one()
            db.add(UserRole(user_id=user.id, role_id=role.id))
        db.flush()
        return user

    return _make


@pytest.fixture()
def make_profile(db, make_user):
    def _make(**overrides) -> tuple[User, StudentProfile]:
        user = make_user()
        profile = StudentProfile(user_id=user.id, **overrides)
        db.add(profile)
        db.flush()
        return user, profile

    return _make
