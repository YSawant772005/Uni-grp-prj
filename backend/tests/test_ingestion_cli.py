"""Read-only ingestion verification metric coverage."""
import uuid

from sqlalchemy import func, select

from app.ingestion.cli import _is_ingested_institution
from app.models import Country, University


def test_ingestion_metrics_include_uai_reporting_units_but_exclude_demo(db):
    country = db.scalar(select(Country))
    assert country is not None
    db.add(University(
        id=uuid.uuid4(), canonical_name="Source-backed UAI institution",
        slug=f"source-backed-uai-{uuid.uuid4().hex[:8]}", country_code=country.code,
        external_identifiers={"uai": "0755976N"},
    ))
    db.flush()

    source_backed_count = db.scalar(
        select(func.count()).select_from(University).where(_is_ingested_institution())
    )
    demo_count = db.scalar(
        select(func.count()).select_from(University).where(
            University.external_identifiers["demo_fixture"].astext.is_not(None)
        )
    )

    assert source_backed_count == 1
    assert demo_count >= 1
