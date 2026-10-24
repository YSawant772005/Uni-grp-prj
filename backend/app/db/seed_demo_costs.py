"""Opt-in synthetic QA tuition and living costs for seed_matching_demo fixtures ONLY.

Never runs during API startup. Never modifies an existing program fee or a real
university. Amounts are deliberately invented for testing and MUST NOT be used
as estimates of real market tuition, living expenses, or admissions.

Run: python -m app.db.seed_demo_costs [--dry-run]
"""
from __future__ import annotations

import argparse
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Campus, City, LivingCostFact, Program, ProgramFee, University
from app.models.enums import CostCategory, MoneyPeriod, RecordStatus

# Deliberately invented figures, NOT national averages or actual institutional fees.
# country: (local currency, annual tuition, housing/month, food/month,
#           transport/month, utilities/month).
SYNTHETIC_2026 = {
    'GB': ('GBP', '16500', '700', '300', '100', '200'),
    'DE': ('EUR', '7000',  '550', '220',  '90', '140'),
    'NL': ('EUR', '12500', '750', '260', '110', '170'),
    'IE': ('EUR', '15000', '850', '290', '100', '160'),
    'US': ('USD', '22000', '1000','360', '130', '190'),
    'CA': ('CAD', '21000', '850', '330', '120', '180'),
    'AU': ('AUD', '24000', '1000','390', '130', '200'),
}
SERIES = 'fictional-masters-cost-qa-v1'
CITY_PREFIX = 'fictional-qa-cost-city-'
CAMPUS_NAME = 'FICTIONAL DEMO Cost Campus'
TUITION_MARKER = 'fictional_demo_qa'


def _is_demo(program: Program, university: University | None) -> bool:
    identifiers = university.external_identifiers if university else None
    return bool(
        university
        and university.slug.startswith(('demo-matching-fixture-', 'demo-world-college-'))
        and isinstance(identifiers, dict) and identifiers.get('synthetic') is True
        and program.slug.startswith('demo-qa-v1-')
        and '[FICTIONAL DEMO]' in program.canonical_name
        and program.university_id == university.id
    )


def seed_demo_costs(db: Session, *, dry_run: bool = False) -> dict[str, int]:
    """Add test-only fee and living facts to matching_demo programs, idempotently.

    Abort for any malformed synthetic fixture rather than mixing into other data.
    No previously stored fee or city information is overwritten.
    """
    programs = list(db.scalars(select(Program).where(
        Program.slug.like('demo-qa-v1-%'),
        Program.canonical_name.contains('[FICTIONAL DEMO]'),
        Program.country_code.in_(SYNTHETIC_2026),
    ).order_by(Program.country_code, Program.id)))
    selected: list[tuple[Program, University]] = []
    for program in programs:
        university = db.get(University, program.university_id)
        if _is_demo(program, university):
            selected.append((program, university))

    result = {
        'eligible_demo_programs': len(selected),
        'created_demo_cities': 0,
        'created_demo_campuses': 0,
        'created_synthetic_living_components': 0,
        'created_synthetic_tuition_fees': 0,
        'skipped_existing_fees_or_campus': 0,
    }
    if dry_run or not selected:
        return result

    for code in sorted({program.country_code for program, _ in selected}):
        currency, tuition, housing, food, transport, utilities = SYNTHETIC_2026[code]
        slug = f'{CITY_PREFIX}{code.lower()}'
        city = db.scalar(select(City).where(City.country_code == code, City.slug == slug))
        if city is None:
            city = City(country_code=code,
                        name=f'FICTIONAL DEMO Cost Location ({code})', slug=slug)
            db.add(city)
            db.flush()
            result['created_demo_cities'] += 1
        elif not city.name.startswith('FICTIONAL DEMO'):
            raise RuntimeError(f'Cannot use non-demo city: {code}/{slug}')

        # Living-cost values are scoped to this dedicated synthetic city; they
        # cannot affect a real campus or its living-cost calculations.
        amounts = {
            CostCategory.housing: housing,
            CostCategory.food: food,
            CostCategory.transport: transport,
            CostCategory.utilities: utilities,
        }
        existing = list(db.scalars(select(LivingCostFact).where(LivingCostFact.city_id == city.id)))
        for category, amount in amounts.items():
            if any(row.cost_category == category for row in existing):
                continue
            mid = Decimal(amount)
            db.add(LivingCostFact(
                city_id=city.id,
                cost_category=category,
                amount_min=(mid * Decimal('0.85')).quantize(Decimal('0.01')),
                amount_typical=mid,
                amount_max=(mid * Decimal('1.15')).quantize(Decimal('0.01')),
                currency=currency,
                period=MoneyPeriod.month,
                student_lifestyle='FICTIONAL DEMO QA ONLY — NOT REAL COST DATA',
                effective_year=2026,
            ))
            result['created_synthetic_living_components'] += 1
        db.flush()

        for program, university in selected:
            if program.country_code != code:
                continue
            # Protect existing non-demo data even if a program has demo markers.
            existing_fee = db.scalar(select(ProgramFee.id).where(ProgramFee.program_id == program.id).limit(1))
            if existing_fee is not None:
                result['skipped_existing_fees_or_campus'] += 1
                continue
            if program.campus_id is not None:
                # Could point to a real location; never reattach it silently.
                result['skipped_existing_fees_or_campus'] += 1
                continue
            campus = db.scalar(select(Campus).where(
                Campus.university_id == university.id,
                Campus.name == CAMPUS_NAME,
            ))
            if campus is None:
                campus = Campus(university_id=university.id, city_id=city.id, name=CAMPUS_NAME)
                db.add(campus)
                db.flush()
                result['created_demo_campuses'] += 1
            elif campus.city_id != city.id:
                raise RuntimeError(f'Unexpected city for demo campus at {university.slug}')
            program.campus_id = campus.id
            if program.duration_max_months is None:
                program.duration_max_months = 24
            if program.duration_min_months is None:
                program.duration_min_months = program.duration_max_months
            db.add(ProgramFee(
                program_id=program.id,
                fee_type='tuition', amount=Decimal(tuition), currency=currency,
                period=MoneyPeriod.academic_year,
                status=RecordStatus.estimated,
                student_category=TUITION_MARKER,  # flag in stored data
                academic_year=None,
                is_mandatory=True,
                fact_id=None,  # intentionally no fabricated source evidence
            ))
            result['created_synthetic_tuition_fees'] += 1
        db.flush()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description='Add FICTIONAL QA prices to existing synthetic Master’s programs.')
    parser.add_argument('--dry-run', action='store_true', help='Show eligible program count without writing data.')
    args = parser.parse_args()
    from app.core.config import settings
    if settings.is_production:
        parser.error('Synthetic QA cost seeding is disabled in production.')
    from app.db.session import SessionLocal
    with SessionLocal.begin() as db:
        results = seed_demo_costs(db, dry_run=args.dry_run)
    print('FICTIONAL DEMO TUITION & LIVING COSTS — TEST VALUES ONLY')
    for key, value in results.items():
        print(f'  {key}: {value}')
    print('No verified prices, university sources, admission criteria, or job outcomes were added.')
    print('Generate a NEW shortlist after seeding; existing results remain unchanged.')

if __name__ == '__main__':
    main()
