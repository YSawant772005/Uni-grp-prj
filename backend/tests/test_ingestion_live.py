"""Opt-in live-source ingestion test.

Skipped by default. Run explicitly with::

    RUN_LIVE_INGESTION_TESTS=1 pytest tests/test_ingestion_live.py

It uses a separate ``*_test`` database (enforced by conftest) and only reads
public, permissively licensed sources.
"""
from __future__ import annotations

import os
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.ingestion.pipeline import RunOptions, run_source
from app.ingestion.registry import get_spec
from app.models import FactEvidence, FactRecord, FactVersion, SourceDocument, University

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_INGESTION_TESTS") != "1",
    reason="set RUN_LIVE_INGESTION_TESTS=1 to run live-source ingestion tests")


def test_ipeds_directory_live(db):
    spec = get_spec("ipeds_hd")
    assert spec and spec.enabled
    summary = run_source("ipeds_hd", RunOptions(max_records=25), db=db)
    assert summary.status == "succeeded", summary.error
    assert summary.counters.created > 0
    assert summary.counters.rejected == 0

    created = db.scalars(select(University).where(
        University.external_identifiers["ipeds_unitid"].astext.is_not(None))).all()
    assert created
    for university in created:
        assert university.country_code == "US"
        assert university.official_website_url is None or \
            university.official_website_url.startswith("http")

    records = db.execute(
        select(FactRecord.fact_key, func.count()).where(
            FactRecord.entity_type == "university",
            FactRecord.entity_id.in_([u.id for u in created])).group_by(FactRecord.fact_key)
    ).all()
    keys = {key for key, _ in records}
    assert "official_website_url" in keys
    # ingestion never verifies anything on its own: every ingested fact is a candidate
    statuses = db.scalars(select(FactRecord.current_status).where(
        FactRecord.entity_id.in_([u.id for u in created]))).all()
    assert set(statuses) == {"candidate"}

    # provenance: every fact has at least one evidence row pointing at a real document
    assert db.scalar(select(func.count()).select_from(SourceDocument)) >= 1
    assert db.scalar(select(func.count()).select_from(FactEvidence)) > 0
    assert db.scalar(select(func.count()).select_from(FactVersion)) > 0


def test_ipeds_run_is_idempotent(db):
    run_source("ipeds_hd", RunOptions(max_records=10), db=db)
    before = (db.scalar(select(func.count()).select_from(University)),
              db.scalar(select(func.count()).select_from(FactVersion)),
              db.scalar(select(func.count()).select_from(FactEvidence)))
    second = run_source("ipeds_hd", RunOptions(max_records=10), db=db)
    assert second.counters.created == 0
    assert (db.scalar(select(func.count()).select_from(University)),
            db.scalar(select(func.count()).select_from(FactVersion)),
            db.scalar(select(func.count()).select_from(FactEvidence))) == before


def test_ror_live_sample(db):
    spec = get_spec("ror")
    assert spec and spec.enabled
    summary = run_source("ror", RunOptions(max_records=20, max_pages=1), db=db)
    assert summary.status == "succeeded", summary.error
    institutions = db.scalars(select(University).where(
        University.external_identifiers["ror"].astext.is_not(None))).all()
    assert institutions
    assert all(u.country_code and len(u.country_code) == 2 for u in institutions)


def test_missing_values_are_never_zero(db):
    """An unreported figure must be absent, never zero (rule 42)."""
    run_source("ipeds_hd", RunOptions(max_records=2000), db=db)  # create the institutions
    run_source("ipeds_ic", RunOptions(), db=db)
    rows = db.execute(
        select(FactVersion.value_json).where(FactVersion.value_json.has_key("room_rate"))
    ).all()
    assert rows
    for (value,) in rows:
        for key, amount in value.items():
            if key.endswith("_rate") or key.endswith("_fee"):
                # IPEDS distinguishes "not reported" (.) from a reported 0, so a zero that
                # is stored was actually published; nothing unreported may appear at all.
                assert Decimal(amount) >= 0
        assert "currency" in value and "academic_period" in value
    # an institution that reported nothing for these items produces no fact at all
    all_costs = db.execute(
        select(FactVersion.value_json).where(
            FactVersion.fact_record_id.in_(select(FactRecord.id).where(
                FactRecord.fact_key == "institutional_costs")))).all()
    for (value,) in all_costs:
        assert any(key in value for key in
                   ("room_rate", "board_rate", "room_and_board_rate",
                    "graduate_application_fee"))