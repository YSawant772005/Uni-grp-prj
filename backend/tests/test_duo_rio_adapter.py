import json
import uuid
from datetime import date

import pytest

from app.ingestion.adapters.base import RunContext
from app.ingestion.adapters.duo_rio import (
    DATASET_URL, RESOURCE_ID, DuoRioAdapter, _stable_offering_id,
)
from app.ingestion.registry import get_spec


class Response:
    status = 200
    status_code = 200
    etag = '"duo-test"'
    last_modified = None
    attempts = 1
    not_modified = False
    headers = {"etag": '"duo-test"'}

    def __init__(self, payload):
        self.content = json.dumps(payload, ensure_ascii=False).encode()

    def text(self, encoding=None):
        return self.content.decode(encoding or "utf-8")


class Fetcher:
    def __init__(self, pages):
        self.pages = list(pages)
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        if not self.pages:
            return Response({"success": True, "result": {"records": [], "total": 0}})
        return Response(self.pages.pop(0))


def _row(*, offering=None, provider="109A847", grade="MASTER", **overrides):
    offering = offering or str(uuid.uuid4())
    row = {
        "_id": 1,
        "ONDERWIJSAANBIEDERID": provider,
        "ONDERWIJSAANBIEDER_NAAM": "Saxion Hogeschool",
        "ERKENDEOPLEIDINGSCODE": 49097,
        "OPLEIDINGSEENHEIDCODE": "1001O5484",
        "AANGEBODEN_OPLEIDINGCODE": offering,
        "EIGEN_AANGEBODEN_OPLEIDINGSLEUTEL": offering.lower(),
        "NAAM_LANG": "Applied Nanotechnology",
        "INTERNATIONALE_NAAM": "Applied Nanotechnology",
        "NIVEAU": "HBO-MA",
        "GRAAD": grade,
        "STUDIELAST": 120,
        "VOERTAAL": "ENG",
        "VORM": "voltijd",
        "AANGEBODEN_OPLEIDING_BEGINDATUM": "2025-09-01T00:00:00",
        "AANGEBODEN_OPLEIDING_EINDDATUM": None,
        "WEBSITE": "https://www.saxion.nl",
        "ONDERWIJSLOCATIECODE": "SAX-ENS",
        "ONDERWIJSLOCATIESTRAAT": "M.H. Tromplaan 28",
        "ONDERWIJSLOCATIEPLAATS": "Enschede",
        "SAMENWERKEND_MET": None,
        "BUITENLANDSEPARTNER": None,
    }
    row.update(overrides)
    return row


def _payload(rows, total=None):
    return {"success": True, "result": {"records": rows, "total": total or len(rows)}}


def test_duo_connector_requires_explicit_bounded_limit_and_policy_is_manual():
    adapter = DuoRioAdapter()
    with pytest.raises(ValueError, match="explicit positive --limit"):
        list(adapter.iter_batches(RunContext(fetcher=Fetcher([]))))
    with pytest.raises(ValueError, match="cannot exceed 5000"):
        list(adapter.iter_batches(RunContext(fetcher=Fetcher([]), max_records=5001)))
    spec = get_spec("duo_rio_masters")
    assert spec.allowed_use_policy == "public_dataset"
    assert spec.enabled is True
    assert spec.refresh_interval_hours is None
    assert spec.requires_explicit_limit is True
    assert "CC BY 4.0" in spec.license_notes


def test_only_master_rows_with_provider_and_stable_offering_identity_are_emitted(
        monkeypatch, tmp_path):
    monkeypatch.setenv("INGESTION_CACHE_DIR", str(tmp_path))
    offering_id = str(uuid.uuid4()).upper()
    rows = [
        _row(offering=offering_id),
        _row(grade="BACHELOR"),
        _row(provider=None),
        _row(SAMENWERKEND_MET="Other University"),
        _row(AANGEBODEN_OPLEIDINGCODE=None,
             EIGEN_AANGEBODEN_OPLEIDINGSLEUTEL="not-a-uuid"),
    ]
    fetcher = Fetcher([_payload(rows)])
    batch = next(DuoRioAdapter().iter_batches(
        RunContext(fetcher=fetcher, max_records=1)))
    assert len(batch.institutions) == 1
    institution = batch.institutions[0]
    assert institution.name == "Saxion Hogeschool"
    assert institution.country_code == "NL"
    assert institution.website is None
    assert institution.identifiers == {"rio_provider_id": "109A847"}
    site_fact = next(f for f in institution.facts if f.fact_key == "official_website_url")
    assert site_fact.value["verification"] == "candidate_from_registry"
    assert site_fact.value["url"] == "https://saxion.nl"
    program = institution.programs[0]
    assert program.external_key == f"duo:offering:{offering_id.lower()}"
    assert program.degree_level == "masters"
    assert program.official_url is None  # WEBSITE is not a program page
    keys = {fact.fact_key for fact in program.facts}
    assert {"study_load_as_reported", "teaching_language_as_reported",
            "study_location_as_reported", "offering_validity_period"} <= keys
    period = next(f for f in program.facts if f.fact_key == "offering_validity_period")
    assert period.effective_from == date(2025, 9, 1)
    assert batch.document.content
    assert DATASET_URL in batch.document.content_excerpt
    assert RESOURCE_ID in fetcher.urls[0]


def test_same_offering_row_repeated_across_pages_is_emitted_once(monkeypatch, tmp_path):
    monkeypatch.setenv("INGESTION_CACHE_DIR", str(tmp_path))
    row = _row()
    fetcher = Fetcher([_payload([row, row])])
    batches = list(DuoRioAdapter().iter_batches(
        RunContext(fetcher=fetcher, max_records=2, max_pages=1)))
    programs = [p for b in batches for i in b.institutions for p in i.programs]
    assert len(programs) == 1
    assert any("duplicate offering" in warning for b in batches for warning in b.warnings)


def test_partner_offerings_never_get_assigned_as_single_institution_programs(
        monkeypatch, tmp_path):
    monkeypatch.setenv("INGESTION_CACHE_DIR", str(tmp_path))
    row = _row(SAMENWERKEND_MET="Partner provider")
    fetcher = Fetcher([_payload([row])])
    batches = list(DuoRioAdapter().iter_batches(
        RunContext(fetcher=fetcher, max_records=1)))
    assert batches[0].institutions == []
    assert batches[0].warnings


def test_malformed_source_response_fails_with_actionable_message(monkeypatch, tmp_path):
    monkeypatch.setenv("INGESTION_CACHE_DIR", str(tmp_path))
    fetcher = Fetcher([{"success": False, "result": {}}])
    with pytest.raises(ValueError, match="unsuccessful"):
        list(DuoRioAdapter().iter_batches(RunContext(fetcher=fetcher, max_records=1)))


def test_stable_offering_identifier_is_a_uuid_not_an_arbitrary_source_row():
    identifier = str(uuid.uuid4())
    assert _stable_offering_id(_row(offering=identifier)) == identifier
    assert _stable_offering_id(_row(AANGEBODEN_OPLEIDINGCODE="bad")) is None


def test_offline_mode_uses_timestamped_cache_without_claiming_a_new_fetch(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from app.ingestion import cache

    monkeypatch.setenv("INGESTION_CACHE_DIR", str(tmp_path))
    label = "duo-rio-masters-0-40.json"
    payload = _payload([_row()])
    cache.store(None, label, json.dumps(payload).encode())
    fetched_at = datetime(2026, 10, 20, tzinfo=timezone.utc).isoformat()
    cache.write_meta(None, label, {"retrieved_at": fetched_at})

    batch = next(DuoRioAdapter().iter_batches(
        RunContext(fetcher=Fetcher([]), max_records=1, offline=True)))
    assert batch.document.retrieval_attempt_count == 0
    assert batch.document.retrieved_at == datetime.fromisoformat(fetched_at)


def test_large_runs_require_the_frozen_exact_plan_workflow():
    with pytest.raises(ValueError,match='exact-plan bulk import tool'):
        list(DuoRioAdapter().iter_batches(RunContext(fetcher=Fetcher([]),max_records=101)))
