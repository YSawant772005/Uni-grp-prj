"""Explicitly opt-in, idempotent FICTIONAL Master's programme data for QA only.

    python -m app.db.seed_matching_demo
    python -m app.db.seed_matching_demo --countries GB --colleges-per-country 8

Never runs on API startup. Does not seed admission requirements, cost figures,
acceptance rates, published rankings, verified sources, or job outcomes.
The 90,000-college test corpus is independent; this script can reuse its
synthetic institutions if they exist, or create a small named demo fixture.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Country, Field, Program, University
from app.models.enums import DegreeLevel, PublicationStatus, RecognitionStatus

DEFAULT_COUNTRIES = ('GB', 'DE', 'NL', 'IE', 'US', 'CA', 'AU')

# Actual degree-title designation is at the START of the name, as required
# by degree_matching.recognized_award(). These are synthetic examples only.
DEMO_AWARDS: tuple[tuple[str, str, str], ...] = (
    ('Master of Technology', 'computer_engineering', 'Computer Engineering'),
    ('Master of Science', 'computer_science', 'Computer Science'),
    ('Master of Science', 'artificial_intelligence', 'Artificial Intelligence'),
    ('Master of Science', 'data_science', 'Data Science'),
    ('Master of Business Administration', 'finance', 'Finance'),
    ('Master of Science', 'business_analytics', 'Business Analytics'),
    ('Master of Engineering', 'mechanical_engineering', 'Mechanical Engineering'),
    ('Master of Engineering', 'robotics', 'Robotics'),
)
DEMO_SERIES = 'matching-masters-qa-v1'


def _choose_colleges(db: Session, code: str, country_name: str, per_country: int) -> tuple[list[University], int]:
    """Reuse stable sample fixtures, or the existing *fictional* 90k dataset."""
    fixtures = list(db.scalars(
        select(University)
        .where(University.slug.like(f'demo-matching-fixture-{code.lower()}-%'))
        .order_by(University.slug).limit(per_country)
    ))
    if fixtures:
        # Once we create dedicated fixtures, keep using them on later runs.
        colleges = fixtures[:]
    else:
        world_colleges = list(db.scalars(
            select(University)
            .where(University.country_code == code,
                   University.slug.like('demo-world-college-%'))
            .order_by(University.slug).limit(per_country)
        ))
        # Never mix an incomplete imported subset with newly created fixtures:
        # that would change identities if the imported 90k dataset grows.
        colleges = world_colleges if len(world_colleges) == per_country else []

    created = 0
    for number in range(len(colleges) + 1, per_country + 1):
        slug = f'demo-matching-fixture-{code.lower()}-{number:03d}'
        # Use unique stable slug, and never modify a real institution.
        institution = db.scalar(select(University).where(University.slug == slug))
        if institution is None:
            institution = University(
                canonical_name=f'DEMO Masters Test College {number:02d} ({country_name})',
                slug=slug,
                country_code=code,
                recognition_status=RecognitionStatus.unknown,
                external_identifiers={
                    'demo_fixture': True, 'synthetic': True, 'demo_series': DEMO_SERIES,
                    'notice': 'FICTIONAL QA institution, not a real or accredited university',
                },
            )
            db.add(institution)
            db.flush()
            created += 1
        colleges.append(institution)
    return colleges, created


def seed_matching_demo(db: Session, country_codes: Sequence[str] = DEFAULT_COUNTRIES,
                       colleges_per_country: int = 8) -> dict[str, int]:
    """Insert recognizable synthetic Master+specialization pairs, idempotently.

    Every college gets a demo MTech Computer Engineering program (for the
    reported user profile) and one additional degree/specialization pair,
    distributed to exercise other profile choices. Missing data stays unknown.
    """
    if not 1 <= colleges_per_country <= 12:
        raise ValueError('colleges_per_country must be between 1 and 12')
    normalized = tuple(code.upper().strip() for code in country_codes)
    if not normalized or len(normalized) != len(set(normalized)):
        raise ValueError('Provide one or more unique country codes')
    if any(code not in DEFAULT_COUNTRIES for code in normalized):
        raise ValueError(f'Demo country must be one of: {", ".join(DEFAULT_COUNTRIES)}')

    # Validate first so a missing country doesn't result in a partial import.
    countries = {code: db.get(Country, code) for code in normalized}
    missing = [code for code, item in countries.items() if item is None]
    if missing:
        raise RuntimeError(f'Missing country reference(s): {", ".join(missing)}. Run the normal API seed first.')

    field_keys = {field_key: display for _, field_key, display in DEMO_AWARDS}
    fields = {f.key: f for f in db.scalars(select(Field).where(Field.key.in_(field_keys)))}
    for key, name in field_keys.items():
        if key not in fields:
            # Reference taxonomy is safe to add; program *requirements* are not.
            field = Field(key=key, display_name=name)
            db.add(field)
            db.flush()
            fields[key] = field

    created_colleges = 0
    created_programs = 0
    reused_colleges = 0
    for code in normalized:
        colleges, created = _choose_colleges(db, code, countries[code].name, colleges_per_country)
        created_colleges += created
        reused_colleges += len(colleges) - created
        for index, college in enumerate(colleges):
            # Include MTech Computer Engineering in every sample destination;
            # each college also offers a rotating second demo Masters award.
            examples = (DEMO_AWARDS[0], DEMO_AWARDS[1 + (index % (len(DEMO_AWARDS) - 1))])
            for award, field_key, specialization in examples:
                slug = f'demo-qa-v1-{field_key}-{award.lower().replace(" ", "-")}'
                exists = db.scalar(select(Program.id).where(
                    Program.university_id == college.id,
                    Program.slug == slug,
                    Program.degree_level == DegreeLevel.masters,
                ))
                if exists is not None:
                    continue
                db.add(Program(
                    university_id=college.id,
                    country_code=code,
                    canonical_name=f'{award} in {specialization} [FICTIONAL DEMO]',
                    slug=slug,
                    degree_level=DegreeLevel.masters,
                    field_id=fields[field_key].id,
                    description=(
                        'FICTIONAL DEMO programme for testing degree/specialization matching only. '
                        'Not a real offering; tuition, cost of living, rankings, admission rules, '
                        'entry requirements, applications and employment outcomes are unavailable. '
                        'Eligibility is unknown until actual evidence is collected.'
                    ),
                    is_active=True,
                    publication_status=PublicationStatus.published,
                ))
                created_programs += 1
        db.flush()

    return {
        'created_demo_colleges': created_colleges,
        'reused_demo_colleges': reused_colleges,
        'created_demo_programs': created_programs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Opt-in fictional demo Masters programmes for local development.')
    parser.add_argument('--countries', nargs='+', default=list(DEFAULT_COUNTRIES),
                        help='Country codes from GB DE NL IE US CA AU (default: all seven).')
    parser.add_argument('--colleges-per-country', type=int, default=8,
                        help='1–12 fictional institutions per country (default 8).')
    args = parser.parse_args()
    from app.core.config import settings
    if settings.is_production:
        parser.error('This fictional fixture is blocked when ENVIRONMENT=production.')
    # Import late so the module can be tested without a PostgreSQL driver.
    from app.db.session import SessionLocal
    with SessionLocal.begin() as session:
        result = seed_matching_demo(session, args.countries, args.colleges_per_country)
    print('FICTIONAL QA PROGRAM DATA — NOT REAL UNIVERSITY OFFERS')
    for key, value in result.items():
        print(f'  {key}: {value}')
    print('No tuition fees, entry requirements, or outcome statistics were generated.')
    print('Generate a NEW shortlist to see the synthetic programs; past runs are unchanged.')


if __name__ == '__main__':
    main()
