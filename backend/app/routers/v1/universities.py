"""Fast, read-only institution search for the onboarding college name field.

Search is optional: students can still enter an institution not in the catalogue.
FICTIONAL DEMO institutions are labeled as such in search results.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import University

router = APIRouter(prefix="/universities", tags=["universities"])


@router.get("/search")
def search_universities(
    q: str = Query(..., min_length=2, max_length=120),
    limit: int = Query(12, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Search 50k+ rows on the server, returning at most ``limit`` names.

    SQLAlchemy auto-escapes LIKE wildcards in typed input, and SQL binds
    all parameters. We do not expose contact or personal data.
    """
    term = q.strip()
    if len(term) < 2:
        return {"items": []}
    prefix = University.canonical_name.istartswith(term, autoescape=True)
    stmt = (
        select(University.canonical_name, University.country_code, University.slug)
        .where(University.canonical_name.icontains(term, autoescape=True))
        .order_by(
            # A college with the searched prefix ranks before a substring match.
            ~prefix,
            func.lower(University.canonical_name),
        )
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return {
        "items": [
            {
                "name": name,
                "country_code": code,
                "is_demo": slug.startswith("demo-") or "FICTIONAL DEMO" in name.upper(),
                "directory_reference": slug.startswith("refdir-2026-"),
            }
            for name, code, slug in rows
        ]
    }
