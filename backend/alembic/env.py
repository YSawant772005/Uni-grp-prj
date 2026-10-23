"""Alembic environment configuration.

The migration target is explicit. All ORM models are imported through ``app.models``
so autogenerate sees the complete metadata.
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.safety import verify_development_target, verify_recovery_target, verify_test_target
from app.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

target = os.environ.get("MIGRATION_TARGET")
if target == "test":
    if not settings.unishortlist_test_mode:
        raise RuntimeError("Refusing migration: test target requires UNISHORTLIST_TEST_MODE=1.")
    verify_test_target(settings.database_url)
elif target == "development":
    if settings.is_production:
        raise RuntimeError("Refusing development migration while ENVIRONMENT=production.")
    verify_development_target(settings.database_url)
elif target == "recovery":
    verify_recovery_target(settings.database_url)
else:
    raise RuntimeError("Refusing migration: set MIGRATION_TARGET=development, test, or recovery explicitly.")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
