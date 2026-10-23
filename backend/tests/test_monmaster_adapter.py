"""Mon Master exposes a field-limited, bounded programme identity feed."""
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from app.ingestion.adapters.base import RunContext
from app.ingestion.adapters.monmaster import API, MonMasterAdapter
from app.ingestion.pipeline import RunOptions, run_source
from app.models import (
    FactEvidence,
    FactRecord,
    FactVersion,
    IngestionJob,
    Program,
    ProgramIdentifier,
    SourceDocument,
    University,
)


class _Fetcher:
    def __init__(self, rows):
        self.rows = rows
        self.urls = []

    def get(self, url, **_kwargs):
        self.urls.append(url)
        body = json.dumps({"total_count": len(self.rows), "results": self.rows},
                          ensure_ascii=False).encode()
        return SimpleNamespace(text=lambda: body.decode(), content=body, status=200,
                               etag=None, last_modified=None)


def _row(ifc="0900820SVFY8", track="Biologie Informatique", **overrides):
    row = {
        "session": "2025", "eta_uai": "0751717J", "eta_nom": "Université Exemple",
        "ifc": ifc, "inm": "0900820S", "inmp": "0900820-06Z",
        "mention": "BIO-INFORMATIQUE", "parcours": track, "discipline": "09",
        "disci_lib": "Sciences de la vie", "secteur_disci_lib": "Biologie",
        "modalite_enseignement": ["INITIALE"], "alternance": "0",
        "lieux": "Campus Exemple - Paris",
        # This API includes aggregate applicant statistics; the adapter must not retain them.
        "n_can_pp": 400,
    }
    row.update(overrides)
    return row


def test_monmaster_limits_fields_and_keeps_program_identity_and_scope():
    fetcher = _Fetcher([_row()])
    batch = next(MonMasterAdapter().iter_batches(RunContext(fetcher=fetcher, max_records=1)))
    params = parse_qs(urlparse(fetcher.urls[0]).query)
    assert urlparse(fetcher.urls[0]).scheme == "https"
    assert params["where"] == ['session="2025"']
    assert "n_can_pp" not in params["select"][0]
    assert len(batch.institutions) == 1
    institution = batch.institutions[0]
    assert institution.country_code == "FR"
    assert institution.identifiers == {"uai": "0751717J"}
    assert institution.identifier_scopes == {"uai": "reporting_unit"}
    program = institution.programs[0]
    assert program.external_key == "fr-monmaster:ifc:0900820SVFY8"
    assert program.title == "BIO-INFORMATIQUE — Biologie Informatique"
    assert program.degree_level == "masters"
    assert program.official_url is None
    assert {fact.fact_key for fact in program.facts} >= {
        "program_title_as_reported", "academic_mention_as_reported", "pathway_as_reported",
        "academic_campaign", "master_mention_identifier", "master_track_identifier",
        "discipline_area", "delivery_modes_as_reported", "program_locations_as_reported",
    }
    assert all(fact.status == "candidate" for fact in program.facts)
    assert "n_can_pp" not in (batch.document.content_excerpt or "")
    assert "400" not in (batch.document.content_excerpt or "")
    assert batch.document.academic_period == "2025"
    assert API in fetcher.urls[0]


def test_monmaster_groups_same_reporting_unit_without_collapsing_programs():
    fetcher = _Fetcher([_row("first"), _row("second", "Physique appliquée")])
    batch = next(MonMasterAdapter().iter_batches(RunContext(fetcher=fetcher, max_records=2)))
    assert len(batch.institutions) == 1
    assert {p.external_key for p in batch.institutions[0].programs} == {
        "fr-monmaster:ifc:first", "fr-monmaster:ifc:second",
    }


def test_monmaster_requires_explicit_bound():
    with pytest.raises(ValueError, match="explicit bounded --limit"):
        next(MonMasterAdapter().iter_batches(RunContext(fetcher=_Fetcher([]))))


def test_monmaster_source_run_refuses_an_unbounded_request():
    summary = run_source("fr_monmaster", RunOptions())
    assert summary.status == "failed"
    assert "explicit --limit" in summary.error


def test_monmaster_rejects_rows_without_authoritative_keys():
    fetcher = _Fetcher([_row(eta_uai="bad", ifc="")])
    with pytest.raises(ValueError, match="valid programme identities"):
        next(MonMasterAdapter().iter_batches(RunContext(fetcher=fetcher, max_records=1)))


def test_monmaster_persists_source_identity_and_evidence_idempotently(db, monkeypatch):
    rows = [_row("first", "Biologie Informatique"),
            _row("second", "Physique appliquée")]
    content = json.dumps({"total_count": len(rows), "results": rows},
                         ensure_ascii=False).encode()

    class Fetcher:
        def __init__(self, **_kwargs):
            pass

        def get(self, _url, **_kwargs):
            return SimpleNamespace(text=lambda: content.decode(), content=content, status=200,
                                   etag=None, last_modified=None)

        def close(self):
            pass

    monkeypatch.setattr("app.ingestion.pipeline.Fetcher", Fetcher)
    ids_before = {row[0] for row in db.query(Program.id).all()}
    first = run_source("fr_monmaster", RunOptions(max_records=2), db=db)
    assert first.status == "succeeded", first.error
    ids_after_first = {row[0] for row in db.query(Program.id).all()}
    assert len(ids_after_first - ids_before) == 2
    assert first.counters.programs_seen == 2
    assert first.counters.programs_created == 2
    assert first.counters.institutions_created == 1
    job = db.get(IngestionJob, first.job_id)
    assert job.records_seen == 3 and job.records_created == 3
    assert job.checkpoint["entities"]["programs_created"] == 2
    assert db.query(University).filter(
        University.external_identifiers["uai"].astext == "0751717J").count() == 1
    assert db.query(ProgramIdentifier).filter(
        ProgramIdentifier.source_key == "fr_monmaster").count() == 2
    # The persisted excerpt is allowlisted and never copies applicant statistics.
    doc = db.query(SourceDocument).filter(
        SourceDocument.canonical_url.like(f"{API}%")).one()
    assert "n_can_pp" not in (doc.content_excerpt or "")
    assert "400" not in (doc.content_excerpt or "")
    count_before = (db.query(FactRecord).count(), db.query(FactVersion).count(),
                    db.query(FactEvidence).count(), db.query(Program).count())

    second = run_source("fr_monmaster", RunOptions(max_records=2), db=db)
    assert second.status == "succeeded", second.error
    assert {row[0] for row in db.query(Program.id).all()} == ids_after_first
    assert (db.query(FactRecord).count(), db.query(FactVersion).count(),
            db.query(FactEvidence).count(), db.query(Program).count()) == count_before
    assert second.counters.unchanged > 0
