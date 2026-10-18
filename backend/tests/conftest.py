"""Test fixtures.

Safety: tests refuse to run unless DATABASE_URL points at a database whose name
contains ``_test``, so a developer database can never be truncated by mistake.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.seed import run_seed
from app.models import Role, StudentProfile, User, UserRole


def _truncate_all(session: Session) -> None:
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
    assert "_test" in settings.database_url, "tests require a *_test database"
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
