"""Run with pytest tests/test_seed_50k_demo.py in the patched backend."""
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed_50k_demo import seed_target, demo_college_count
from app.models import Country, University

@compiles(JSONB, 'sqlite')
def _jsonb_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return 'JSON'

@pytest.fixture
def db():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine, tables=[Country.__table__, University.__table__])
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_50k_idempotent_and_countries(db):
    noop = lambda _: None
    first = seed_target(db, target=50_000, batch_size=500, report=noop)
    assert first['created'] == 50_000
    assert first['total'] == 50_000
    assert db.scalar(select(func.count()).select_from(Country)) == 195
    second = seed_target(db, target=50_000, batch_size=500, report=noop)
    assert second['created'] == 0
    assert second['total'] == 50_000
    assert demo_college_count(db) == 50_000


def test_dry_run_does_not_write(db):
    result = seed_target(db, target=20, dry_run=True, report=lambda _: None)
    assert result == {'existing': 0, 'created': 0, 'total': 0}
    assert demo_college_count(db) == 0


def test_previously_over_target_is_not_deleted(db):
    seed_target(db, target=20, batch_size=7, report=lambda _: None)
    with pytest.raises(RuntimeError, match='No records were deleted'):
        seed_target(db, target=10, report=lambda _: None)
    assert demo_college_count(db) == 20


def test_partial_import_can_resume_without_duplicates(db):
    seed_target(db, target=12, batch_size=5, report=lambda _: None)
    resumed = seed_target(db, target=27, batch_size=6, report=lambda _: None)
    assert resumed['created'] == 15
    assert resumed['total'] == 27
