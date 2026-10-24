"""SQLite integration checks for the explicit synthetic Masters seed.

A production deployment still needs a full PostgreSQL/Docker smoke test.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed_matching_demo import seed_matching_demo
from app.models import Country, Field, Program, University, AdmissionRequirement, ProgramFee
from app.models.enums import DegreeLevel
from app.services.degree_matching import exact_award_match


@compiles(JSONB, 'sqlite')
def _jsonb_for_sqlite(element, compiler, **kwargs):
    return 'JSON'


@pytest.fixture
def session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine, tables=[
        Country.__table__, Field.__table__, University.__table__, Program.__table__,
        AdmissionRequirement.__table__, ProgramFee.__table__,
    ])
    with Session(engine) as db:
        db.add_all([
            Country(code='GB', name='United Kingdom'),
            Country(code='DE', name='Germany'),
        ])
        db.commit()
        yield db
    engine.dispose()


def test_creates_mtech_computer_eng_and_is_idempotent(session):
    first = seed_matching_demo(session, country_codes=['GB'], colleges_per_country=8)
    session.commit()
    assert first['created_demo_colleges'] == 8
    assert first['created_demo_programs'] == 16

    second = seed_matching_demo(session, country_codes=['GB'], colleges_per_country=8)
    session.commit()
    assert second['created_demo_colleges'] == 0
    assert second['created_demo_programs'] == 0

    program_list = list(session.scalars(select(Program).where(Program.country_code == 'GB')))
    assert len(program_list) == 16
    computer_eng_id = session.scalar(select(Field.id).where(Field.key == 'computer_engineering'))
    matches = [p for p in program_list if
               p.field_id == computer_eng_id and
               exact_award_match('Master of Technology', p.canonical_name)]
    assert len(matches) == 8
    assert all(p.degree_level == DegreeLevel.masters for p in matches)
    assert all('[FICTIONAL DEMO]' in p.canonical_name for p in program_list)
    assert not any(exact_award_match('Master of Science', p.canonical_name) for p in matches)
    assert all(p.description and 'not a real offering' in p.description.lower() for p in program_list)


def test_reuses_existing_demo_world_colleges(session):
    for i in range(2):
        session.add(University(
            canonical_name=f'DEMO College {i}',
            slug=f'demo-world-college-{i+1:04d}',
            country_code='GB',
            external_identifiers={'synthetic': True},
        ))
    session.commit()
    counts = seed_matching_demo(session, country_codes=['GB'], colleges_per_country=2)
    session.commit()
    assert counts == {
        'created_demo_colleges': 0,
        'reused_demo_colleges': 2,
        'created_demo_programs': 4,
    }
    counts = seed_matching_demo(session, country_codes=['GB'], colleges_per_country=2)
    assert counts['created_demo_programs'] == 0


def test_invalid_country_and_size_does_not_change_database(session):
    with pytest.raises(ValueError):
        seed_matching_demo(session, ['XX'], 4)
    with pytest.raises(RuntimeError):
        seed_matching_demo(session, ['DE', 'US'], 4)
    with pytest.raises(ValueError):
        seed_matching_demo(session, ['GB'], 100000)
    assert not session.scalars(select(Program)).first()


def test_programs_keep_uncertain_evidence_unknown(session):
    seed_matching_demo(session, ['DE'], 2)
    session.commit()
    from app.models import AdmissionRequirement, ProgramFee
    # Program rows exist, but this seeder makes NO acceptance thresholds or fees.
    # Eligibility should remain unknown rather than fabricated as 'eligible'.
    for program in session.scalars(select(Program)):
        assert not session.scalars(select(AdmissionRequirement).where(
            AdmissionRequirement.program_id == program.id)).first()
        assert not session.scalars(select(ProgramFee).where(
            ProgramFee.program_id == program.id)).first()
