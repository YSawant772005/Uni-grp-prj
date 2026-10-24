"""Import the 649 reference-only university/college names from the user's PDF.

The PDF is *not* an accredited program catalogue. These entries are useful for
search/autocomplete only. No degree/programme claims, rankings, fees or
recognition statuses are fabricated.

Usage inside the API container:
    python -m app.db.seed_university_directory --dry-run
    python -m app.db.seed_university_directory

Safe to re-run: skip same normalized names in the same country; no deletes or
updates to existing universities or programs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import slugify
from app.models import Country, University
from app.models.enums import InstitutionType, RecognitionStatus

DATA_FILE = Path(__file__).with_name("university_directory_2026.json")
SOURCE_MARKER = "user_pdf_university_directory_2026_10_22"


def normal_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def reference_slug(country_code: str, name: str) -> str:
    """Namespace these records so they cannot collide with demo fixture slugs."""
    digest = hashlib.sha1(f"{country_code}:{name}".encode("utf-8")).hexdigest()[:10]
    return f"refdir-2026-{country_code.lower()}-{slugify(name, max_len=180)}-{digest}"


def load_reference_rows() -> list[dict[str, str]]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    rows = data["institutions"]
    if len(rows) != 649 or len({r["country_code"] for r in rows}) != 102:
        raise ValueError("Directory manifest has changed; expected 649 institutions across 102 locations")
    if len({(r["country_code"], normal_name(r["name"])) for r in rows}) != len(rows):
        raise ValueError("Directory manifest contains repeated institution names")
    return rows


def import_directory(session: Session, *, dry_run: bool = False) -> dict[str, int]:
    """Add only missing names; existing catalogue rows and programme records are never altered."""
    rows = load_reference_rows()
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["country_code"]].append(row)

    stats = {"total": len(rows), "countries": len(grouped), "countries_added": 0,
             "institutions_added": 0, "already_present": 0, "slug_conflicts": 0}

    # The older demo installation might have seeded only seven countries.
    # Add any missing country codes needed for FK integrity, without modifying
    # existing country descriptions/URLs.
    for code, country_rows in grouped.items():
        if session.get(Country, code) is None:
            stats["countries_added"] += 1
            if not dry_run:
                session.add(Country(code=code, name=country_rows[0]["country_name"]))
    if not dry_run:
        session.flush()

    # Fetch existing names country by country; this covers independent real
    # catalogue rows and 50,000+ fictional demo records without trusting slugs.
    for code, country_rows in grouped.items():
        existing_rows = session.execute(
            select(University.canonical_name, University.slug)
            .where(University.country_code == code)
        ).all()
        existing_names = {normal_name(name) for name, _ in existing_rows}
        existing_slugs = {slug for _, slug in existing_rows}

        for row in country_rows:
            name = row["name"]
            key = normal_name(name)
            slug = reference_slug(code, name)
            if key in existing_names:
                stats["already_present"] += 1
                continue
            if slug in existing_slugs:
                stats["slug_conflicts"] += 1
                continue
            stats["institutions_added"] += 1
            existing_names.add(key)
            existing_slugs.add(slug)
            if dry_run:
                continue
            session.add(
                University(
                    canonical_name=name,
                    slug=slug,
                    country_code=code,
                    institution_type=InstitutionType.unknown,
                    recognition_status=RecognitionStatus.unknown,
                    official_website_url=None,
                    external_identifiers={
                        "source": SOURCE_MARKER,
                        "reference_only": True,
                        "user_provided_pdf": True,
                        "reference_date": "2026-10-22",
                        "recognition_verified": False,
                        "programmes_verified": False,
                    },
                )
            )

    if not dry_run:
        session.flush()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show counts without writing anything")
    args = parser.parse_args()
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        try:
            stats = import_directory(session, dry_run=args.dry_run)
            if args.dry_run:
                session.rollback()
            else:
                session.commit()
        except Exception:
            session.rollback()
            raise
    print("REFERENCE-ONLY university directory", "(DRY RUN)" if args.dry_run else "(IMPORTED)")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("These are names for academic-profile search; no programme offerings or accreditation were verified.")


if __name__ == "__main__":
    main()
