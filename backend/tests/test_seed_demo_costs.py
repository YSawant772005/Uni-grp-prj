"""Database integration checks for the synthetic cost patch (SQLite fixtures)."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed_matching_demo import seed_matching_demo
from app.db.seed_demo_costs import seed_demo_costs, SYNTHETIC_2026
from app.models import Campus, City, Country, Field, LivingCostFact, Program, ProgramFee, University
from app.models.enums import RecordStatus
from app.services import scoring


@compiles(JSONB, 'sqlite')
def _jsonb_for_sqlite(element, compiler, **kwargs):
    return 'JSON'


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine, tables=[
        Country.__table__, City.__table__, University.__table__, Campus.__table__,
        Field.__table__, Program.__table__, ProgramFee.__table__, LivingCostFact.__table__,
    ])
    with Session(engine) as session:
        for code in SYNTHETIC_2026:
            session.add(Country(code=code, name=f'Demo country {code}'))
        session.commit()
        yield session
    engine.dispose()


def test_fictional_costs_seed_are_complete_and_idempotent(db):
    seed_matching_demo(db, ['GB'], 2)
    db.commit()
    counts = seed_demo_costs(db)
    db.commit()
    assert counts['eligible_demo_programs'] == 4
    assert counts['created_synthetic_tuition_fees'] == 4
    assert counts['created_demo_campuses'] == 2
    assert counts['created_demo_cities'] == 1
    assert counts['created_synthetic_living_components'] == 4
    assert seed_demo_costs(db)['created_synthetic_tuition_fees'] == 0
    db.commit()
    assert len(db.scalars(select(ProgramFee)).all()) == 4
    assert len(db.scalars(select(LivingCostFact)).all()) == 4
    assert all(f.status == RecordStatus.estimated and f.student_category == 'fictional_demo_qa'
               and f.fact_id is None for f in db.scalars(select(ProgramFee)))
    for program in db.scalars(select(Program)):
        costs = scoring.estimate_program_cost(db, program)
        assert costs['tuition_total'] == Decimal('33000.00')
        assert costs['living_total'] == Decimal('31200.00')
        amount, notes = scoring.total_in_currency(db, costs, 'GBP')
        assert amount == Decimal('64200.00')
        assert notes == []


def test_dry_run_does_not_touch_rows(db):
    seed_matching_demo(db, ['DE'], 1)
    db.commit()
    output = seed_demo_costs(db, dry_run=True)
    assert output['eligible_demo_programs'] == 2
    assert not db.scalars(select(ProgramFee)).first()
    assert not db.scalars(select(LivingCostFact)).first()


def test_real_program_cannot_receive_fictional_costs(db):
    seed_matching_demo(db, ['GB'], 1)
    db.add(University(canonical_name='Real College', slug='real-college', country_code='GB'))
    db.flush()
    real = db.scalar(select(University).where(University.slug == 'real-college'))
    original = Program(university_id=real.id, country_code='GB',
                       canonical_name='Master of Technology in Computer Engineering',
                       slug='real-mtech-computer-engineering', degree_level='masters')
    db.add(original)
    db.commit()
    seed_demo_costs(db)
    db.commit()
    assert original.campus_id is None
    assert not db.scalars(select(ProgramFee).where(ProgramFee.program_id == original.id)).first()


def test_existing_fees_are_not_overwritten(db):
    seed_matching_demo(db, ['IE'], 1)
    db.commit()
    p = db.scalar(select(Program).where(Program.country_code == 'IE').limit(1))
    db.add(ProgramFee(program_id=p.id, fee_type='tuition', amount=Decimal('123.00'),
                      currency='EUR', period='academic_year', status=RecordStatus.verified))
    db.commit()
    output = seed_demo_costs(db)
    db.commit()
    assert output['skipped_existing_fees_or_campus'] == 1
    fee = db.scalar(select(ProgramFee).where(ProgramFee.program_id == p.id))
    assert fee.amount == Decimal('123.00')
    assert fee.status == RecordStatus.verified
    assert p.campus_id is None


def test_cost_calculation_identifies_synthetic_sources(db, monkeypatch):
    # For the isolated SQLite run only, replace the optional FastAPI error
    # dependency; the actual project uses app.core.errors normally.
    import sys
    import types
    stub = types.ModuleType('app.core.errors')
    stub.ApiError = RuntimeError
    monkeypatch.setitem(sys.modules, 'app.core.errors', stub)
    from app.services.costs import calculate
    seed_matching_demo(db, ['GB'], 1)
    db.commit()
    seed_demo_costs(db)
    db.commit()
    program = db.scalar(select(Program).where(Program.country_code == 'GB').limit(1))
    result = calculate(db, program_id=program.id, currency='GBP')
    tuition = next(row for row in result['items'] if row['cost_type'] == 'tuition')
    living = next(row for row in result['items'] if row['cost_type'] == 'living')
    assert 'FICTIONAL DEMO' in tuition['note']
    assert 'FICTIONAL DEMO' in living['note']
    assert tuition['status'] == 'estimated'
    assert living['status'] == 'estimated'
