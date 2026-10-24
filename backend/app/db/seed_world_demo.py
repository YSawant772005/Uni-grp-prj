"""Opt-in demonstration catalogue, never an official university directory.

Usage from Docker API container:
  python -m app.db.seed_world_demo --colleges 90000

Country references are also seeded during the application's ordinary seed step.
The fictional institutions are created ONLY by this explicit CLI.
The 90,000-college option uses bounded database insert batches and commits
regularly so interrupted imports can be safely resumed.
"""
from __future__ import annotations

import argparse
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.world_countries import WORLD_COUNTRIES
from app.models import Country, Field, Program, University
from app.models.enums import DegreeLevel, PublicationStatus, RecognitionStatus

# Titles recognized by the project's named Master's matching engine; specializations
# map to existing Field reference keys. No fees, ranking, grades, acceptance rates,
# test scores, outcomes, accreditation or application dates are invented.
DEMO_PROGRAM_TYPES = (
    ('Master of Technology', 'computer_engineering', 'Computer Engineering'),
    ('Master of Science', 'computer_science', 'Computer Science'),
    ('Master of Science', 'artificial_intelligence', 'Artificial Intelligence'),
    ('Master of Engineering', 'mechanical_engineering', 'Mechanical Engineering'),
    ('Master of Science', 'data_science', 'Data Science'),
    ('Master of Business Administration', 'finance', 'Finance'),
    ('Master of Science', 'business_analytics', 'Business Analytics'),
    ('Master of Engineering', 'robotics', 'Robotics'),
)


def seed_world_countries(db: Session) -> int:
    """Add missing country codes only; keep existing official links and metadata."""
    existing = set(db.scalars(select(Country.code)).all())
    additions = [Country(code=code, name=name) for code, name in WORLD_COUNTRIES if code not in existing]
    db.add_all(additions)
    db.flush()
    return len(additions)


def seed_demo_colleges(
    db: Session, count: int = 90000, with_programs: bool = False, *,
    start_number: int = 1, batch_size: int = 250,
) -> dict[str, int]:
    """Generate fictional university rows without inventing degrees or outcome data.

    Ordinary inserts are issued as small UPSERT batches instead of loading tens
    of thousands of ORM entities into memory. The CLI commits every batch; a
    failed or interrupted run can be resumed without creating duplicate rows.

    The optional historical one-program-per-college fixture is intentionally
    limited to 3,000 rows to avoid accidental 90k-program recommendations.
    """
    if not 1 <= count <= 90000:
        raise ValueError('Count must be between 1 and 90000.')
    if not 1 <= start_number <= count:
        raise ValueError('start_number must be between 1 and count.')
    if not 1 <= batch_size <= 1000:
        raise ValueError('batch_size must be between 1 and 1000.')
    if with_programs and (count > 3000 or start_number != 1):
        raise ValueError('Demo programs are limited to the first 3000 colleges. Run without --with-demo-programs for 90000 colleges.')
    known_codes = set(db.scalars(select(Country.code)).all())
    if any(code not in known_codes for code, _ in WORLD_COUNTRIES):
        raise RuntimeError('Seed world countries before creating demo institutions.')

    if not with_programs:
        dialect_name = db.get_bind().dialect.name
        if dialect_name == 'postgresql':
            insert_factory = pg_insert
        elif dialect_name == 'sqlite':
            insert_factory = sqlite_insert
        else:
            raise RuntimeError(f'Bulk demo college import requires PostgreSQL or SQLite; got {dialect_name}.')
        created = 0
        for start in range(start_number, count + 1, batch_size):
            rows = []
            for number in range(start, min(start + batch_size, count + 1)):
                code, country_name = WORLD_COUNTRIES[(number - 1) % len(WORLD_COUNTRIES)]
                rows.append({
                    'id': uuid.uuid4(),
                    'canonical_name': f'DEMO College {number:04d} ({country_name})',
                    'slug': f'demo-world-college-{number:04d}',
                    'country_code': code,
                    'recognition_status': RecognitionStatus.unknown,
                    'external_identifiers': {
                        'demo_fixture': True,
                        'synthetic': True,
                        'demo_series': 'world-colleges-v1',
                        'notice': 'FICTIONAL institution for QA only; not accredited or verified',
                    },
                })
            stmt = insert_factory(University).values(rows).on_conflict_do_nothing(index_elements=['slug'])
            result = db.execute(stmt)
            created += result.rowcount
        return {'created_demo_colleges': created, 'created_demo_programs': 0}

    university_by_slug = {
        u.slug: u for u in db.scalars(
            select(University).where(University.slug.in_([
                f'demo-world-college-{n:04d}' for n in range(1, count + 1)
            ]))
        )
    }
    program_keys = {}
    if with_programs:
        field_by_key = {f.key: f for f in db.scalars(select(Field))}
        program_types = [item for item in DEMO_PROGRAM_TYPES if item[1] in field_by_key]
        if not program_types:
            raise RuntimeError('Seed study fields first: no demo programme fields were found.')
    else:
        field_by_key, program_types = {}, []

    created_colleges = 0
    created_programs = 0
    for start in range(1, count + 1, 250):
        pending = []
        for number in range(start, min(start + 250, count + 1)):
            code, country_name = WORLD_COUNTRIES[(number - 1) % len(WORLD_COUNTRIES)]
            slug = f'demo-world-college-{number:04d}'
            institution = university_by_slug.get(slug)
            if institution is None:
                institution = University(
                    canonical_name=f'DEMO College {number:04d} ({country_name})',
                    slug=slug,
                    country_code=code,
                    recognition_status=RecognitionStatus.unknown,
                    external_identifiers={
                        'demo_fixture': True, 'synthetic': True,
                        'demo_series': 'world-colleges-v1',
                        'notice': 'FICTIONAL institution for UI testing only',
                    },
                )
                db.add(institution)
                pending.append(institution)
                university_by_slug[slug] = institution
                created_colleges += 1
        if pending:
            db.flush()

        if with_programs:
            university_ids = [university_by_slug[f'demo-world-college-{n:04d}'].id
                              for n in range(start, min(start + 250, count + 1))]
            existing_programs = set(db.scalars(select(Program.university_id).where(
                Program.university_id.in_(university_ids),
                Program.slug == 'demo-masters-program'
            )).all())
            for number in range(start, min(start + 250, count + 1)):
                u = university_by_slug[f'demo-world-college-{number:04d}']
                if u.id in existing_programs:
                    continue
                award, field_key, specialization = program_types[(number - 1) % len(program_types)]
                db.add(Program(
                    university_id=u.id,
                    country_code=u.country_code,
                    canonical_name=f'{award} in {specialization} — DEMO',
                    slug='demo-masters-program',
                    degree_level=DegreeLevel.masters,
                    field_id=field_by_key[field_key].id,
                    description=(
                        'SYNTHETIC DEMO PROGRAM for testing search and matching. '
                        'The college does not exist; admission requirements, costs, '
                        'recognition, outcomes and intake dates are not available.'
                    ),
                    is_active=True,
                    publication_status=PublicationStatus.published,
                ))
                created_programs += 1
            db.flush()
    return {'created_demo_colleges': created_colleges, 'created_demo_programs': created_programs}


def main() -> None:
    parser = argparse.ArgumentParser(description='Seed 195 countries and optional synthetic DEMO colleges.')
    parser.add_argument('--colleges', type=int, default=90000,
                        help='Number of fictional colleges to generate (default: 90000; maximum: 90000).')
    parser.add_argument('--batch-size', type=int, default=500,
                        help='College rows inserted per committed transaction (default: 500; max: 1000).')
    parser.add_argument('--with-demo-programs', action='store_true',
                        help='OPTIONAL: publish one synthetic program for each of up to 3000 colleges only.')
    args = parser.parse_args()
    if not 1 <= args.colleges <= 90000:
        parser.error('--colleges must be between 1 and 90000')
    if not 1 <= args.batch_size <= 1000:
        parser.error('--batch-size must be between 1 and 1000')
    if args.with_demo_programs and args.colleges > 3000:
        parser.error('90,000 demo programs are not supported; omit --with-demo-programs (or use <=3000).')
    with SessionLocal() as db:
        with db.begin():
            country_count = seed_world_countries(db)
        total_colleges = 0
        total_programs = 0
        if args.with_demo_programs:
            with db.begin():
                counts = seed_demo_colleges(db, count=args.colleges, with_programs=True)
            total_colleges += counts['created_demo_colleges']
            total_programs += counts['created_demo_programs']
        else:
            for start in range(1, args.colleges + 1, args.batch_size):
                end = min(args.colleges, start + args.batch_size - 1)
                with db.begin():
                    counts = seed_demo_colleges(
                        db, count=end, start_number=start, batch_size=args.batch_size,
                    )
                total_colleges += counts['created_demo_colleges']
                if end == args.colleges or end % 5000 == 0:
                    print(f'Processed {end:,}/{args.colleges:,} fictional colleges...', flush=True)
    print(f'Seeded {country_count} missing countries (195 total reference countries).')
    print(f'Created {total_colleges:,} new DEMO colleges; '
          f'{total_programs:,} DEMO programs. Existing database rows were preserved.')
    print('All institutions are fictional. Do not present these as real universities.')


if __name__ == '__main__':
    main()
