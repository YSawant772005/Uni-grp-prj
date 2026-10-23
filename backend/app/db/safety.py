"""Fail-closed identity checks for database-writing test entry points."""
from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, make_url

TEST_DATABASE = "uni_shortlist_test"
TEST_ROLE = "uni_shortlist_test"
TEST_HOST = "db-test"
TEST_MARKER = "uni-shortlist-isolated-test-db-v1"
DEVELOPMENT_DATABASE = "uni_shortlist"
RECOVERY_DATABASE = "uni_shortlist_recovery"
RECOVERY_ROLE = "uni_shortlist_recovery"
RECOVERY_HOST = "db-recovery"
RECOVERY_MARKER = "uni-shortlist-isolated-recovery-db-v1"


def verify_development_target(url: str) -> None:
    """Fail closed before an explicitly selected development migration/seed."""
    parsed = make_url(url)
    expected_port = 5432 if parsed.host == "db" else 5433
    if (
        parsed.drivername not in {"postgresql", "postgresql+psycopg"}
        or parsed.database != DEVELOPMENT_DATABASE
        or parsed.host not in {"db", "localhost", "127.0.0.1"}
        or parsed.port != expected_port
        or parsed.username != "uni_shortlist"
        or parsed.query
    ):
        raise RuntimeError(
            "Refusing database write: expected the local uni_shortlist database, "
            "uni_shortlist role, and configured development port."
        )
    engine = create_engine(
        url,
        connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=5000"},
    )
    try:
        with engine.connect() as connection:
            row = connection.execute(text(
                "SELECT current_database() AS database_name, current_user AS role_name"
            )).one()
            if row.database_name != DEVELOPMENT_DATABASE or row.role_name != parsed.username:
                raise RuntimeError("Refusing database write: connected development identity does not match URL.")
    finally:
        engine.dispose()


def validate_test_url(url: str, *, test_mode: str | None = None) -> None:
    """Validate explicit intent and every identity-bearing URL component."""
    if test_mode is None:
        test_mode = os.environ.get("UNISHORTLIST_TEST_MODE")
    if test_mode != "1":
        raise RuntimeError("Database writes refused: set UNISHORTLIST_TEST_MODE=1 explicitly.")
    if not url:
        raise RuntimeError("Database writes refused: TEST_DATABASE_URL is required.")
    parsed = make_url(url)
    if parsed.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise RuntimeError("Database writes refused: test URL must use PostgreSQL/psycopg.")
    if parsed.database != TEST_DATABASE:
        raise RuntimeError(f"Database writes refused: expected database {TEST_DATABASE!r}.")
    if parsed.username != TEST_ROLE:
        raise RuntimeError(f"Database writes refused: expected role {TEST_ROLE!r}.")
    if parsed.host != TEST_HOST or parsed.port not in {None, 5432}:
        raise RuntimeError(f"Database writes refused: expected isolated service {TEST_HOST}:5432.")
    if parsed.query:
        raise RuntimeError("Database writes refused: query parameters are not allowed in test URLs.")


def verify_connected(connection: Connection) -> None:
    """Confirm actual server database, role and immutable test-instance marker."""
    row = connection.execute(
        text("""
            SELECT current_database() AS database_name,
                   current_user AS role_name,
                   (SELECT marker FROM unishortlist_test.instance_marker LIMIT 1) AS marker
        """)
    ).one_or_none()
    if row is None or (row.database_name, row.role_name, row.marker) != (
        TEST_DATABASE, TEST_ROLE, TEST_MARKER
    ):
        raise RuntimeError(
            "Database writes refused: connected PostgreSQL identity does not match "
            "the isolated test instance (database, role, marker)."
        )


def verify_runtime_target() -> None:
    """Startup identity check for test API instances; never mutates the target."""
    from app.core.config import settings

    if settings.unishortlist_test_mode:
        verify_test_target(settings.runtime_database_url)


def verify_test_target(url: str | None = None) -> None:
    """Validate the configured test URL and inspect the server read-only."""
    target = url or os.environ.get("TEST_DATABASE_URL")
    validate_test_url(target or "")
    engine = create_engine(
        target,
        connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=5000"},
    )
    try:
        with engine.connect() as connection:
            verify_connected(connection)
    finally:
        engine.dispose()


def verify_recovery_target(url: str) -> None:
    """Allow explicit schema rehearsals only on the marked disposable recovery DB."""
    parsed = make_url(url)
    if (
        parsed.drivername not in {"postgresql", "postgresql+psycopg"}
        or parsed.database != RECOVERY_DATABASE
        or parsed.username != RECOVERY_ROLE
        or parsed.host != RECOVERY_HOST
        or parsed.port not in {None, 5432}
        or parsed.query
    ):
        raise RuntimeError("Refusing migration: expected the isolated recovery database identity.")
    engine = create_engine(
        url,
        connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=5000"},
    )
    try:
        with engine.connect() as connection:
            row = connection.execute(text(
                "SELECT current_database(), current_user, "
                "(SELECT marker FROM unishortlist_recovery.instance_marker LIMIT 1)"
            )).one_or_none()
            if row is None or tuple(row) != (RECOVERY_DATABASE, RECOVERY_ROLE, RECOVERY_MARKER):
                raise RuntimeError("Refusing migration: connected database is not the marked recovery instance.")
    finally:
        engine.dispose()


if __name__ == "__main__" and sys.argv[1:] == ["verify"]:
    verify_test_target()
    print("Verified isolated test PostgreSQL identity.")
