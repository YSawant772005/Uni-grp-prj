"""Explicit 50,000 FICTIONAL-college dataset seed for local QA only.

Run in the API Docker container:
    python -m app.db.seed_50k_demo
    python -m app.db.seed_50k_demo --dry-run

It uses the established demo-world-college-0001 ... 50000 slugs, without
creating fictional course offerings. It is safe to resume and run repeatedly.
It WILL NOT remove rows if a previous 90k-demo import has already run.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import University
from app.db.seed_world_demo import seed_demo_colleges, seed_world_countries

DEFAULT_TARGET = 50_000
DEFAULT_BATCH_SIZE = 500
DEMO_SLUG_PATTERN = 'demo-world-college-%'


def demo_college_count(db: Session) -> int:
    """Count only the world-demo fixture series, excluding real colleges."""
    return int(db.scalar(select(func.count()).select_from(University).where(
        University.slug.like(DEMO_SLUG_PATTERN)
    )) or 0)


def seed_target(
    db: Session,
    *,
    target: int = DEFAULT_TARGET,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
    report: Callable[[str], None] = print,
) -> dict[str, int]:
    """Fill the first ``target`` demo slugs; never delete existing data.

    Commits each batch so interrupted imports can resume. ``target`` is kept
    configurable to permit fast isolated tests, but the CLI always uses 50k.
    """
    if not 1 <= target <= DEFAULT_TARGET:
        raise ValueError('Target must be between 1 and 50,000 demo colleges.')
    if not 1 <= batch_size <= 1000:
        raise ValueError('Batch size must be between 1 and 1000.')
    existing = demo_college_count(db)
    if dry_run:
        extra = (' WARNING: above target; no rows will be removed.'
                 if existing > target else '')
        report(f'DRY RUN — currently {existing:,} world-demo colleges. '
               f'Target: {target:,}.{extra} No records changed.')
        return {'existing': existing, 'created': 0, 'total': existing}
    if existing > target:
        raise RuntimeError(
            f'There are already {existing:,} world-demo colleges, exceeding the '
            f'{target:,}-college target. No records were deleted or changed. '
            'Use a separate, reviewed cleanup if you need to reduce the existing dataset.'
        )

    # A read above may have opened an implicit SQLAlchemy transaction.
    # Close it before the first explicit batch transaction.
    db.rollback()

    # First make sure all 195 country references exist; this is the only
    # reference-data write. The API's normal country seed is not required.
    with db.begin():
        seed_world_countries(db)

    created = 0
    for start in range(1, target + 1, batch_size):
        end = min(target, start + batch_size - 1)
        with db.begin():
            result = seed_demo_colleges(db, count=end,
                                        start_number=start, batch_size=batch_size,
                                        with_programs=False)
        created += result['created_demo_colleges']
        if end == target or end % 5000 == 0:
            report(f'Processed {end:,}/{target:,} DEMO colleges; '
                   f'{created:,} new records.')

    total = demo_college_count(db)
    report(f'Done: {total:,} world-demo colleges in the database; '
           f'{created:,} newly inserted. No Master\'s programs were generated.')
    return {'existing': existing, 'created': created, 'total': total}


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Safely seed 50,000 clearly fictional colleges in a LOCAL UniShortlist database.')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                        help='Rows per transaction (1–1000; default 500).')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show current demo-college count without writing.')
    args = parser.parse_args()

    from app.core.config import settings
    if settings.is_production:
        parser.error('FICTIONAL QA seeding is disabled in production.')
    if not 1 <= args.batch_size <= 1000:
        parser.error('--batch-size must be 1–1000')

    from app.db.session import SessionLocal
    with SessionLocal() as db:
        try:
            result = seed_target(db, batch_size=args.batch_size, dry_run=args.dry_run)
        except RuntimeError as exc:
            parser.error(str(exc))
    print(f"FINISHED: {result['total']:,} DEMO colleges (new: {result['created']:,}).")
    print('FICTIONAL TEST INSTITUTIONS only. No verified programs or admission data.')


if __name__ == '__main__':
    main()
