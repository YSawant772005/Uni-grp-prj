"""Regression checks for strict test database URL identity validation."""
import pytest
from types import SimpleNamespace

from app.db.safety import (
    TEST_DATABASE, TEST_MARKER, TEST_ROLE, verify_connected, validate_test_url,
    verify_recovery_target,
)
from app.core.config import Settings


def _url(user="uni_shortlist_test", password="secret", host="db-test", database="uni_shortlist_test", query=""):
    suffix = f"?{query}" if query else ""
    return f"postgresql+psycopg://{user}:{password}@{host}:5432/{database}{suffix}"


def test_accepts_only_explicit_isolated_test_target():
    validate_test_url(_url(), test_mode="1")


@pytest.mark.parametrize("url", [
    _url(user="user_test", database="uni_shortlist"),
    _url(user="uni_shortlist", password="_test", database="uni_shortlist"),
    _url(host="development_test_alias", database="uni_shortlist"),
    _url(host="postgres.production.example"),
    _url(database="uni_shortlist_test_shadow"),
    _url(query="application_name=uni_shortlist_test"),
    _url(user="wrong_role"),
    _url(host="localhost"),
])
def test_rejects_misleading_or_wrong_database_targets(url):
    with pytest.raises(RuntimeError):
        validate_test_url(url, test_mode="1")


def test_rejects_missing_explicit_test_intent():
    with pytest.raises(RuntimeError):
        validate_test_url(_url(), test_mode="0")


def test_runtime_refuses_to_fall_back_to_administrative_database_url():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://admin:secret@db:5432/uni_shortlist",
        app_database_url=None,
        unishortlist_test_mode=False,
    )
    with pytest.raises(RuntimeError, match="APP_DATABASE_URL is required"):
        _ = settings.runtime_database_url


def test_recovery_migration_guard_rejects_non_recovery_host_before_connecting():
    with pytest.raises(RuntimeError, match="isolated recovery database identity"):
        verify_recovery_target(
            "postgresql+psycopg://uni_shortlist_recovery:secret@db:5432/uni_shortlist_recovery"
        )


@pytest.mark.parametrize("identity", [
    ("uni_shortlist", TEST_ROLE, TEST_MARKER),
    (TEST_DATABASE, "wrong_role", TEST_MARKER),
    (TEST_DATABASE, TEST_ROLE, "development-marker"),
])
def test_rejects_wrong_connected_database_identity(identity):
    class ReadOnlyIdentityConnection:
        def execute(self, _statement):
            row = SimpleNamespace(database_name=identity[0], role_name=identity[1], marker=identity[2])
            return SimpleNamespace(one_or_none=lambda: row)

    with pytest.raises(RuntimeError):
        verify_connected(ReadOnlyIdentityConnection())
