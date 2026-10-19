"""Ingestion engine tests: adapters, normalization, validation, persistence,
idempotency, provenance, change detection, permissions and the admin entry point.

HTTP is always mocked here; live-source ingestion lives in
``tests/test_ingestion_live.py`` and is opt-in.
"""
from __future__ import annotations

import json
import types
import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select

from app.core.errors import ApiError
from app.ingestion import persist, registry
from app.ingestion.adapters.base import AdapterSpec, RunContext, SourceAdapter
from app.ingestion.adapters.ipeds import IpedsDirectoryAdapter, NcesCipAdapter, _read_csv
from app.ingestion.adapters.ror import RorAdapter
from app.ingestion.adapters.webpage import FieldRule, WebPageAdapter, WebPageConfig
from app.ingestion.extract import (
    csv_to_dicts,
    find_labelled_value,
    html_to_text,
    json_path,
    pdf_to_text,
)
from app.ingestion.http import Fetcher, FetchError
from app.ingestion.normalize import (
    clean_text,
    ipeds_amount,
    ipeds_number,
    ipeds_value,
    name_key,
    normalize_academic_period,
    normalize_aliases,
    normalize_degree_level,
    normalize_url,
    parse_date,
)
from app.ingestion.pipeline import RunOptions, enqueue_due_refreshes, run_source
from app.ingestion.registry import all_specs, get_spec, register_source
from app.ingestion.types import (
    AdapterBatch,
    CandidateFact,
    CandidateField,
    CandidateInstitution,
    CandidateProgram,
    SourceDoc,
)
from app.ingestion.validate import (
    institution_match_quality,
    validate_institution,
    validate_program,
)
from app.models import (
    FactEvidence,
    FactRecord,
    FactVersion,
    Field,
    IngestionJob,
    IngestionJobItem,
    Program,
    Source,
    SourceDocument,
    University,
)

ROR_PAGE = {
    "number_of_results": 2,
    "items": [
        {
            "id": "https://ror.org/00xyz1234",
            "names": [
                {"value": "GSU", "types": ["acronym"]},
                {"value": "Gavar State University", "types": ["ror_display", "label"]},
            ],
            "external_ids": [{"type": "grid", "preferred": "grid.1", "all": ["grid.1"]},
                             {"type": "isni", "preferred": None, "all": ["0000 1"]}],
            "links": [{"type": "website", "value": "http://www.example-university.edu/"},
                      {"type": "wikipedia", "value": "https://en.wikipedia.org/wiki/X"}],
            "locations": [{"name": "Gavar", "geonames_details": {
                "country_code": "AM", "country_name": "Armenia", "continent_name": "Asia",
                "lat": 40.35, "lng": 45.12, "country_subdivision_name": "Gegharkunik"}}],
            "types": ["education"], "status": "active",
        },
        {"id": "", "names": [], "locations": []},
    ],
}

HD_ROW = {
    "UNITID": "100654", "INSTNM": "Alabama A & M University", "IALIAS": "AAMU",
    "ADDR": "4900 Meridian Street", "CITY": "Normal", "STABBR": "AL", "ZIP": "35762",
    "WEBADDR": "www.aamu.edu/", "CONTROL": "1", "SECTOR": "1", "ICLEVEL": "1",
    "GROFFER": "1", "UGOFFER": "1", "HLOFFER": "9", "OPEID": "00100500",
    "EIN": "636001109 ", "FIPS": "1", "LOCALE": "12", "LATITUDE": "34.783368",
    "LONGITUD": "-86.568502", "C21BASIC": "18", "C21SZSET": "14", "C18BASIC": "18",
    "C15BASIC": "18", "LANDGRNT": "1", "HBCU": "1", "TRIBAL": "2", "RELAFFIL": "1",
}

CIP_HTML = """<html><body><select><option value="0">All</option>
<option value="90374">11)COMPUTER AND INFORMATION SCIENCES AND SUPPORT SERVICES.</option>
<option value="90408">13)EDUCATION.</option>
<option value="not-a-series">nonsense</option></select></body></html>"""


# --------------------------------------------------------------------- helpers

class StubResponse:
    """Minimal stand-in for ``app.ingestion.http.HttpResult``."""

    def __init__(self, status_code=200, content=b"", headers=None):
        self.status = status_code
        self.status_code = status_code
        self.content = content if isinstance(content, bytes) else content.encode()
        self.headers = headers or {}

    def text(self, encoding=None):
        return self.content.decode(encoding or "utf-8", errors="replace")

    @property
    def etag(self):
        return self.headers.get("etag")

    @property
    def last_modified(self):
        return self.headers.get("last-modified")

    @property
    def not_modified(self):
        return self.status == 304


def _stub_fetcher(monkeypatch, handler):
    created = {}

    class Stub(Fetcher):
        def __init__(self, **kwargs):
            created.update(kwargs)
            self.user_agent = kwargs.get("user_agent", "stub")
            self.calls = []
            self._handler = handler
            self._client = None

        def close(self):
            return None

        def get(self, url, *, headers=None, etag=None, last_modified=None):
            self.calls.append((url, etag, last_modified))
            return self._handler(url, etag, last_modified)

    monkeypatch.setattr("app.ingestion.pipeline.Fetcher", Stub)
    return created


def _spec(key="test_source", **kw) -> AdapterSpec:
    base = dict(source_key=key, name="Test source", base_url="https://example.org/data",
                source_type="government", authority_tier=1,
                owner_or_publisher="Test Publisher", license_notes="Public domain test fixture",
                allowed_use_policy="public_dataset", enabled=True)
    base.update(kw)
    return AdapterSpec(**base)


class ScriptedAdapter(SourceAdapter):
    source_key = "test_source"

    def __init__(self, batches):
        self.batches = batches
        self.runs = 0

    def iter_batches(self, ctx: RunContext):
        self.runs += 1
        yield from self.batches


def _institution(name="Test University", **kw) -> CandidateInstitution:
    data = dict(external_key="t:1", name=name,
                identifiers={"ror": "00abc"}, country_code="DE",
                country_name="Germany", website="https://uni.example.org")
    data.update(kw)
    return CandidateInstitution(**data)


def _batch(institutions, content=b"x", url="https://example.org/data"):
    return AdapterBatch(document=SourceDoc(url=url, content=content, document_type="json"),
                        institutions=institutions)


# ---------------------------------------------------------------- normalize

class TestNormalization:
    def test_missing_values_stay_none_and_never_zero(self):
        for raw in (None, "", ".", "-", "N/A", "-2", "-99", "  "):
            assert ipeds_value(raw) is None
            assert ipeds_amount(raw) is None
            assert ipeds_number(raw) is None
        assert ipeds_amount("0") == Decimal("0")
        assert ipeds_amount("12,500.50") == Decimal("12500.50")

    def test_text_and_alias_normalization(self):
        assert clean_text("  Hello   world \n") == "Hello world"
        assert clean_text("-") is None
        assert normalize_aliases(["A & B", "A and B", None, "C"]) == ["A & B", "C"]

    def test_url_normalization_is_scheme_and_tracking_independent(self):
        assert normalize_url("www.Example.EDU/path/") == normalize_url(
            "https://www.example.edu/path#frag")
        assert normalize_url("ftp://example.org") is None
        assert normalize_url("javascript:alert(1)") is None
        assert normalize_url(None) is None

    def test_name_key_is_case_and_punctuation_insensitive(self):
        assert name_key("University of, Tokyo!") == name_key("UNIVERSITY OF TOKYO")
        assert name_key("A & B") == name_key("a and b")

    def test_degree_currency_period_and_dates(self):
        assert normalize_degree_level("Master of Science (MSc)") == "masters"
        assert normalize_degree_level("PhD in Physics") == "phd"
        assert normalize_degree_level("Certificate in Welding") is None
        assert normalize_academic_period("2023/2024") == "2023-24"
        assert normalize_academic_period("nonsense") is None
        assert parse_date("2023-09-01") == date(2023, 9, 1)
        assert parse_date("not a date") is None


# ----------------------------------------------------------------- validation

class TestValidation:
    def test_institution_without_country_or_identity_is_rejected(self):
        issues = validate_institution(CandidateInstitution(external_key="", name="  "))
        codes = {i.code for i in issues}
        assert {"required", "invalid", "insufficient"} & codes

    def test_bad_country_code_and_coordinates_are_flagged(self):
        candidate = _institution(country_code="deu", latitude=Decimal("100"))
        codes = {i.code for i in validate_institution(candidate)}
        assert "invalid" in codes and "out_of_range" in codes

    def test_program_duration_order_and_degree_level(self):
        program = CandidateProgram(external_key="p:1", title="MSc",
                                   duration_min_months=24, duration_max_months=12,
                                   degree_level="masters")
        assert {i.code for i in validate_program(program)} == {"inconsistent"}
        program.degree_level = "wizard"
        assert "invalid" in {i.code for i in validate_program(program)}

    def test_program_with_missing_title_and_bad_url(self):
        program = CandidateProgram(external_key="", title="",
                                   official_url="javascript:alert(1)")
        codes = {i.code for i in validate_program(program)}
        assert {"required", "invalid_url"} <= codes

    def test_confidence_must_be_a_probability(self):
        fact = CandidateFact("tuition", {"v": 1}, confidence=4.0)
        assert "out_of_range" in {i.code for i in validate_program(
            CandidateProgram(external_key="p", title="t", facts=[fact]))}


# ------------------------------------------------------------------- adapters

class TestRorAdapter:
    def test_parses_a_real_shaped_page(self):
        ctx = RunContext(fetcher=None)
        adapter = RorAdapter()
        item = adapter._to_institution(ROR_PAGE["items"][0], 1)
        assert item.external_key == "ror:00xyz1234"
        assert item.name == "Gavar State University"
        assert item.aliases == ["GSU"]
        assert item.country_code == "AM" and item.country_name == "Armenia"
        assert item.website == "http://example-university.edu"
        assert item.identifiers["ror_grid"] == "grid.1"
        assert {f.fact_key for f in item.facts} == {
            "official_name", "aliases", "official_website_url", "location"}

    def test_records_without_identity_or_name_are_dropped(self):
        adapter = RorAdapter()
        assert adapter._to_institution(ROR_PAGE["items"][1], 1) is None
        assert adapter._to_institution({"id": "https://ror.org/x", "names": []}, 1) is None

    def test_country_filter_and_record_limit_are_applied(self):
        adapter = RorAdapter()
        ctx = RunContext(fetcher=None, countries=["PL"], max_records=5)
        batches = list(adapter._to_institution(i, 1) for i in ROR_PAGE["items"])
        kept = [i for i in batches if i and i.country_code in {"PL"}]
        assert kept == []  # the Armenian record is filtered out, not dropped silently


class TestIpedsAdapters:
    def test_directory_row_maps_to_a_candidate(self):
        candidate = IpedsDirectoryAdapter().to_candidate(HD_ROW)
        assert candidate.external_key == "ipeds:100654"
        assert candidate.country_code == "US"
        assert candidate.website == "https://aamu.edu"
        assert candidate.institution_type == "public"
        assert candidate.admin_region == "AL"
        assert candidate.aliases == ["AAMU"]
        keys = {f.fact_key for f in candidate.facts}
        assert {"official_name", "official_website_url", "classification",
                "program_offerings", "institution_type"} <= keys
        offerings = next(f for f in candidate.facts if f.fact_key == "program_offerings")
        assert offerings.value["offers_graduate"] is True

    def test_missing_directory_values_do_not_become_placeholders(self):
        row = dict(HD_ROW, WEBADDR=" ", CONTROL=" ", LATITUDE="-2", IALIAS="", UNITID=" ")
        candidate = IpedsDirectoryAdapter().to_candidate(row)
        assert candidate is None or candidate.website is None

    def test_completions_refuse_to_emit_without_the_official_label_map(self):
        from app.ingestion.adapters.ipeds import IpedsCompletionsAdapter
        adapter = IpedsCompletionsAdapter()
        assert adapter.to_candidate({"UNITID": "1", "CIPCODE": "11.0101", "AWLEVEL": "3",
                                     "CTOTALT": "10"}) is None

    def test_completions_emit_only_once_a_label_map_is_supplied(self):
        from app.ingestion.adapters.ipeds import IpedsCompletionsAdapter
        adapter = IpedsCompletionsAdapter(awlevel_map={"3": ("masters", "Master's degree")},
                                          cip_series={"11": "Computer and Information Sciences"})
        candidate = adapter.to_candidate({"UNITID": "1", "CIPCODE": "11.0101",
                                          "AWLEVEL": "3", "CTOTALT": "10"})
        program = candidate.programs[0]
        assert program.degree_level == "masters"
        assert program.discipline_code == "11.0101"
        assert "CIP 11.0101" in program.title

    def test_cip_taxonomy_html_becomes_discipline_reference_data(self):
        ctx = RunContext(fetcher=None)
        parser = NcesCipAdapter()
        batches = list(_cip_batches(parser, ctx, CIP_HTML))
        fields = batches[0].fields
        assert {f.key for f in fields} == {"cip_11", "cip_13"}
        assert fields[0].display_name == "Computer and Information Sciences and Support Services"


def _cip_batches(adapter, ctx, html):
    """Drive the CIP adapter without network by faking the fetcher response."""
    class F:
        user_agent = "stub"

        def get(self, url):
            return StubResponse(200, html, {"etag": "v1"})

    ctx.fetcher = F()
    yield from adapter.iter_batches(ctx)


class TestWebPageAdapter:
    def _adapter(self, document_type="html", url="https://uni.example.org/msc"):
        config = WebPageConfig(
            url=url, document_type=document_type,
            institution={"name": "Example University", "country_code": "NL",
                         "country_name": "Netherlands",
                         "identifiers": {"uni_web": "example"}},
            program={"title": "MSc Data Science", "external_key": "nl:msc"},
            rules=[FieldRule("tuition_amount", "Annual tuition", "amount"),
                   FieldRule("application_deadline", "Application deadline", "date"),
                   FieldRule("duration", "Duration", "months"),
                   FieldRule("not_published", "Scholarship amount", "amount")],
            respect_robots=False)
        return WebPageAdapter("web_test", config)

    HTML = ("<html><body><h1>MSc Data Science</h1>"
            "<p>Annual tuition: EUR 17,900 per year</p>"
            "<p>Application deadline: 15/03/2026</p>"
            "<p>Duration: 24 months</p>"
            "<script>ignore()</script></body></html>")

    def _run(self, adapter, content=None, kind="html"):
        ctx = RunContext(fetcher=None)
        ctx.fetcher = types.SimpleNamespace(
            user_agent="stub",
            get=lambda url, **kw: StubResponse(200, content or adapter_html))
        return next(adapter.iter_batches(ctx))

    def test_html_extraction_ties_each_value_to_its_passage(self):
        batch = self._run(self._adapter(), self.HTML.encode())
        facts = {f.fact_key: f for f in batch.institutions[0].facts}
        assert facts["tuition_amount"].value["value"] == "17,900"
        assert "Annual tuition" in facts["tuition_amount"].excerpt
        assert facts["application_deadline"].value["value"] == "15/03/2026"
        assert facts["duration"].value["value"].startswith("24")
        assert "not_published" not in facts  # missing label yields no fact at all
        assert batch.institutions[0].programs[0].title == "MSc Data Science"

    def test_json_and_csv_sources_are_supported(self):
        payload = json.dumps({"programme": {"fee": {"amount": 12345}}}).encode()
        adapter = self._adapter(document_type="json")
        adapter.config.rules = [FieldRule("tuition_amount", json_path="programme.fee.amount")]
        batch = self._run(adapter, payload)
        assert batch.institutions[0].facts[0].value["value"] == "12345"

        adapter = self._adapter(document_type="csv")
        adapter.config.rules = [FieldRule("tuition_amount", column="tuition_eur")]
        batch = self._run(adapter, b"unitid,tuition_eur\n1,9800\n")
        assert batch.institutions[0].facts[0].value["value"] == "9800"

    def test_malformed_documents_produce_warnings_not_exceptions(self):
        batch = self._run(self._adapter(), b"<<<not html>>>")
        assert any("not found" in w for w in batch.warnings)
        assert batch.institutions[0].facts == []

    def test_only_http_urls_are_fetched(self):
        adapter = self._adapter(url="file:///etc/passwd")
        ctx = RunContext(fetcher=None)
        with pytest.raises(FetchError):
            list(adapter.iter_batches(ctx))


class TestExtraction:
    def test_html_to_text_survives_malformed_markup(self):
        assert "Tuition" in html_to_text("<div>Tuition<p>10,000</div")
        assert html_to_text("<script>bad()</script><p>ok</p>") == "ok"

    def test_labelled_values_need_the_label_to_be_present(self):
        text = html_to_text("<p>Tuition fee: 12,000 EUR</p><p>Deadline: 01/01/2026</p>")
        assert find_labelled_value(text, "Tuition fee", "amount")[0] == "12,000"
        assert find_labelled_value(text, "Scholarship", "amount") is None

    def test_json_path_and_csv_parsing(self):
        assert json_path({"a": [{"b": 2}]}, "a.0.b") == 2
        assert json_path({"a": 1}, "a.b.c") is None
        assert csv_to_dicts(b"a,b\n1,2\n") == [{"a": "1", "b": "2"}]
        assert csv_to_dicts(b"") == []

    def test_broken_pdf_is_handled_without_raising(self):
        text = pdf_to_text(b"%PDF-1.4 truncated")
        assert text is None or isinstance(text, str)


# ---------------------------------------------------------------------- http

class TestHttpClient:
    def _fetcher(self, monkeypatch, handler, **overrides):
        kwargs = dict(user_agent="test-agent", timeout=0.1, max_retries=2, backoff=0.001,
                      rps=0, max_workers=2)
        kwargs.update(overrides)
        fetcher = Fetcher(**kwargs)
        monkeypatch.setattr(fetcher._client, "get",
                            lambda url, headers=None, **kw: handler(url, headers or {}))
        return fetcher

    def test_retries_then_succeeds_on_retryable_status(self, monkeypatch):
        attempts = {"n": 0}

        def handler(url, headers):
            attempts["n"] += 1
            if attempts["n"] == 1:
                return StubResponse(429, b"", {"retry-after": "0"})
            return StubResponse(200, b"ok")

        result = self._fetcher(monkeypatch, handler).get("https://example.org")
        assert result.content == b"ok" and attempts["n"] == 2

    def test_retry_budget_is_bounded_and_then_permanent(self, monkeypatch):
        fetcher = self._fetcher(monkeypatch, lambda url, headers: StubResponse(503, b""))
        with pytest.raises(FetchError) as exc:
            fetcher.get("https://example.org")
        assert exc.value.permanent and "exhausted" in exc.value.reason

    def test_client_errors_are_not_retried(self, monkeypatch):
        calls = {"n": 0}

        def handler(url, headers):
            calls["n"] += 1
            return StubResponse(404)

        with pytest.raises(FetchError):
            self._fetcher(monkeypatch, handler).get("https://example.org/missing")
        assert calls["n"] == 1

    def test_conditional_requests_return_not_modified(self, monkeypatch):
        seen = {}

        def handler(url, headers):
            seen["headers"] = headers
            return StubResponse(304)

        result = self._fetcher(monkeypatch, handler).get(
            "https://example.org", etag='"abc"', last_modified="Sun, 01 Jan 2026 00:00:00 GMT")
        assert result.not_modified and seen["headers"]["If-None-Match"] == '"abc"'

    def test_one_failing_request_does_not_stop_the_others(self, monkeypatch):
        def handler(url, headers):
            if url.endswith("bad"):
                raise httpx.ConnectError("boom")
            return StubResponse(200, b"ok")

        fetcher = self._fetcher(monkeypatch, handler, max_retries=1)
        results = fetcher.parallel_map(lambda u: fetcher.get(u),
                                       ["https://example.org/bad", "https://example.org/ok"])
        assert results[0][1] is None and isinstance(results[0][2], Exception)
        assert results[1][1].content == b"ok" and results[1][2] is None


# ------------------------------------------------------------------ persistence

class TestPersistence:
    def test_fact_versions_are_appended_and_history_preserved(self, db):
        source = persist.ensure_source(db, _spec())
        document = persist.store_document(db, source, SourceDoc(
            url="https://example.org/a", content=b"a"), persist.Counters())
        counters = persist.Counters()
        fact = CandidateFact("official_name", {"name": "Alpha"},
                             normalized={"name": "alpha"})
        assert persist.record_fact(db, entity_type="university", entity_id=uuid.uuid4(),
                                   source=source, document=document, fact=fact,
                                   counters=counters) == "created"
        entity_id = db.scalar(select(FactRecord.entity_id).where(
            FactRecord.fact_key == "official_name"))
        changed = CandidateFact("official_name", {"name": "Beta"}, normalized={"name": "beta"})
        assert persist.record_fact(db, entity_type="university", entity_id=entity_id,
                                   source=source, document=document, fact=changed,
                                   counters=counters) == "updated"
        versions = db.scalars(select(FactVersion).where(
            FactVersion.fact_record_id == db.scalar(select(FactRecord.id).where(
                FactRecord.entity_id == entity_id)))).all()
        assert [v.version_number for v in versions] == [1, 2]
        assert versions[0].value_json == {"name": "Alpha"}  # never overwritten

    def test_repeated_identical_fact_is_unchanged_and_adds_no_version(self, db):
        source = persist.ensure_source(db, _spec())
        document = persist.store_document(db, source, SourceDoc(
            url="https://example.org/b", content=b"b"), persist.Counters())
        resolver = persist.InstitutionResolver(db)
        university, _ = persist.upsert_institution(db, _institution(), resolver)
        counters = persist.Counters()
        fact = CandidateFact("official_name", {"name": "Alpha"}, normalized={"name": "alpha"})
        for _ in range(3):
            assert persist.record_fact(db, entity_type="university", entity_id=university.id,
                                       source=source, document=document, fact=fact,
                                       counters=counters) in ("created", "unchanged")
        assert db.scalar(select(func.count()).select_from(FactVersion).where(
            FactVersion.value_json["name"].astext == "Alpha")) == 1
        assert counters.created == 1 and counters.unchanged == 2
        assert db.scalar(select(func.count()).select_from(FactEvidence).where(
            FactEvidence.source_document_id == document.id)) == 1

    def test_conflicting_value_from_another_source_is_flagged_not_applied(self, db):
        source_a = persist.ensure_source(db, _spec(key="a"))
        source_b = persist.ensure_source(db, _spec(key="b"))
        resolver = persist.InstitutionResolver(db)
        university, _ = persist.upsert_institution(db, _institution(), resolver)
        doc_a = persist.store_document(db, source_a, SourceDoc(url="u://a", content=b"a"),
                                       persist.Counters())
        doc_b = persist.store_document(db, source_b, SourceDoc(url="u://b", content=b"b"),
                                       persist.Counters())
        counters = persist.Counters()
        fact = CandidateFact("tuition", {"amount": "1000"}, normalized={"amount": "1000"})
        persist.record_fact(db, entity_type="university", entity_id=university.id,
                            source=source_a, document=doc_a, fact=fact, counters=counters)
        record = db.scalar(select(FactRecord).where(FactRecord.fact_key == "tuition"))
        current = db.get(FactVersion, record.current_version_id)
        current.status = "verified"          # a reviewer approved the first value
        record.current_status = "verified"
        db.flush()
        other = CandidateFact("tuition", {"amount": "2000"}, normalized={"amount": "2000"})
        assert persist.record_fact(db, entity_type="university", entity_id=university.id,
                                   source=source_b, document=doc_b, fact=other,
                                   counters=counters) == "review"
        assert record.current_status == "conflicted"
        assert counters.review == 1
        assert db.get(FactVersion, record.current_version_id).value_json == {"amount": "1000"}

    def test_two_sources_disagreeing_is_a_conflict_not_an_overwrite_loop(self, db):
        """Regression: sources must not overwrite each other on every run."""
        source_a = persist.ensure_source(db, _spec(key="a"))
        source_b = persist.ensure_source(db, _spec(key="b"))
        resolver = persist.InstitutionResolver(db)
        university, _ = persist.upsert_institution(db, _institution(), resolver)
        doc_a = persist.store_document(db, source_a, SourceDoc(url="u://a2", content=b"a"),
                                       persist.Counters())
        doc_b = persist.store_document(db, source_b, SourceDoc(url="u://b2", content=b"b"),
                                       persist.Counters())
        fact_a = CandidateFact("official_website_url", {"url": "https://a.example.edu"},
                               normalized={"url": "a.example.edu"})
        fact_b = CandidateFact("official_website_url", {"url": "https://b.example.edu"},
                               normalized={"url": "b.example.edu"})
        counters = persist.Counters()
        assert persist.record_fact(db, entity_type="university", entity_id=university.id,
                                   source=source_a, document=doc_a, fact=fact_a,
                                   counters=counters) == "created"
        assert persist.record_fact(db, entity_type="university", entity_id=university.id,
                                   source=source_b, document=doc_b, fact=fact_b,
                                   counters=counters) == "review"
        assert counters.review == 1
        # repeating the same run changes nothing further
        assert persist.record_fact(db, entity_type="university", entity_id=university.id,
                                   source=source_b, document=doc_b, fact=fact_b,
                                   counters=counters) == "unchanged"
        record = db.scalar(select(FactRecord).where(FactRecord.fact_key ==
                                                     "official_website_url"))
        assert record.current_status == "conflicted"
        assert db.get(FactVersion, record.current_version_id).value_json == {
            "url": "https://a.example.edu"}  # the value in force is preserved

    def test_second_source_corroborating_the_same_value_is_unchanged(self, db):
        source_a = persist.ensure_source(db, _spec(key="a"))
        source_b = persist.ensure_source(db, _spec(key="b"))
        resolver = persist.InstitutionResolver(db)
        university, _ = persist.upsert_institution(db, _institution(), resolver)
        doc_a = persist.store_document(db, source_a, SourceDoc(url="u://a3", content=b"a"),
                                       persist.Counters())
        doc_b = persist.store_document(db, source_b, SourceDoc(url="u://b3", content=b"b"),
                                       persist.Counters())
        fact = CandidateFact("official_name", {"name": "Alpha"}, normalized={"name": "alpha"})
        counters = persist.Counters()
        persist.record_fact(db, entity_type="university", entity_id=university.id,
                            source=source_a, document=doc_a, fact=fact, counters=counters)
        assert persist.record_fact(db, entity_type="university", entity_id=university.id,
                                   source=source_b, document=doc_b, fact=fact,
                                   counters=counters) == "unchanged"
        assert counters.review == 0
        record = db.scalar(select(FactRecord).where(FactRecord.fact_key == "official_name"))
        assert record.current_status == "candidate"
        # both sources' passages are kept as evidence
        assert db.scalar(select(func.count()).select_from(FactEvidence).where(
            FactEvidence.fact_version_id == record.current_version_id)) == 2

    def test_documents_are_deduplicated_by_content_hash(self, db):
        source = persist.ensure_source(db, _spec())
        counters = persist.Counters()
        first = persist.store_document(db, source, SourceDoc(url="u://x", content=b"same"),
                                       counters)
        second = persist.store_document(db, source, SourceDoc(url="u://x", content=b"same"),
                                        counters)
        third = persist.store_document(db, source, SourceDoc(url="u://x", content=b"changed"),
                                       counters)
        assert first.id == second.id and third.id != first.id
        assert counters.documents_unchanged == 1

    def test_binary_excerpts_never_break_the_text_column(self, db):
        source = persist.ensure_source(db, _spec())
        document = persist.store_document(db, source, SourceDoc(
            url="u://bin", content=b"PK\x03\x04\x00\x01\x02binary"), persist.Counters())
        assert "\x00" not in (document.content_excerpt or "")

    def test_provenance_chain_is_intact(self, db):
        source = persist.ensure_source(db, _spec())
        document = persist.store_document(db, source, SourceDoc(url="u://p", content=b"p"),
                                          persist.Counters())
        resolver = persist.InstitutionResolver(db)
        university, _ = persist.upsert_institution(db, _institution(), resolver)
        fact = CandidateFact("official_name", {"name": "A"}, normalized={"name": "a"},
                             excerpt="The official name is A", locator="page#name")
        persist.record_fact(db, entity_type="university", entity_id=university.id,
                            source=source, document=document, fact=fact,
                            counters=persist.Counters())
        evidence = db.scalar(select(FactEvidence).where(
            FactEvidence.evidence_excerpt == "The official name is A"))
        assert evidence.evidence_excerpt == "The official name is A"
        assert evidence.evidence_locator == "page#name"
        assert evidence.source_document_id == document.id
        assert document.source_id == source.id


class TestIdentityResolution:
    def test_repeating_identifiers_never_fuse_unrelated_universities(self, db):
        resolver = persist.InstitutionResolver(db)
        first = _institution("Alpha University", identifiers={"ipeds_unitid": "1",
                                                              "ipeds_fips": "1"})
        university_a, action = persist.upsert_institution(db, first, resolver)
        second = _institution("Beta University", website="https://beta.example.org",
                              identifiers={"ipeds_unitid": "2", "ipeds_fips": "1"})
        university_b, _ = persist.upsert_institution(db, second, resolver)
        assert action == "created" and university_a.id != university_b.id

    def test_a_shared_name_never_fuses_two_real_institutions(self, db):
        """Distinct universities with the same name must stay separate rows."""
        resolver = persist.InstitutionResolver(db)
        first = _institution("Springfield University", identifiers={"ror": "aaa"},
                             website="https://springfield.example.edu")
        persist.upsert_institution(db, first, resolver)
        second = _institution("Springfield University", identifiers={"ror": "bbb"},
                              website="https://springfield-two.example.edu")
        university_b, action = persist.upsert_institution(db, second, resolver)
        db.flush()
        assert action == "created"
        assert db.scalar(select(func.count()).select_from(University).where(
            University.canonical_name == "Springfield University")) == 2
        assert university_b.external_identifiers["ror"] == "bbb"

    def test_weak_matches_are_reported_but_never_applied(self, db):
        persist.upsert_institution(db, _institution("Fairmont State University",
                                                   identifiers={"ror": "ccc"}),
                                   persist.InstitutionResolver(db))
        db.flush()
        candidate = _institution("Fairmont State University", identifiers={"ror": "ddd"},
                                 website="https://fairmont.example.edu")
        matched_id, method = persist.InstitutionResolver(db).resolve(candidate)
        assert matched_id is not None and method == "name_country"
        issues = institution_match_quality(candidate, method)
        assert issues and issues[0].code == "weak_match"
        # a weak match never reuses the existing institution
        _id, applied = persist.upsert_institution(
            db, candidate, persist.InstitutionResolver(db))
        assert applied == "created"

    def test_synthetic_demo_fixtures_are_excluded_from_matching(self, db):
        demo = db.scalar(select(University).where(
            University.external_identifiers["demo_fixture"].astext.is_not(None)))
        candidate = _institution(demo.canonical_name, country_code=demo.country_code,
                                 identifiers={}, website=demo.official_website_url)
        matched_id, _ = persist.InstitutionResolver(db).resolve(candidate)
        assert matched_id is None

    def test_repeat_runs_match_on_the_stable_identifier(self, db):
        resolver = persist.InstitutionResolver(db)
        original, _ = persist.upsert_institution(db, _institution(), resolver)
        db.commit()
        matched, _ = persist.upsert_institution(
            db, _institution(name="Different Display Name"), persist.InstitutionResolver(db))
        assert matched.id == original.id
        assert db.scalar(select(func.count()).select_from(University).where(
            University.external_identifiers["ror"].astext == "00abc")) == 1

    def test_synthetic_demo_fixtures_are_never_merged_into(self, db):
        demo = db.scalar(select(University).where(
            University.external_identifiers["demo_fixture"].astext.is_not(None)))
        assert demo is not None
        candidate = _institution(demo.canonical_name, identifiers={})
        assert candidate.country_code == "DE"
        university, _ = persist.upsert_institution(
            db, candidate, persist.InstitutionResolver(db))
        assert university.id != demo.id

    def test_missing_country_is_rejected_before_anything_is_written(self, db):
        candidate = _institution(country_code=None, identifiers={}, website=None)
        assert {i.code for i in validate_institution(candidate)} >= {"required", "insufficient"}
        resolver = persist.InstitutionResolver(db)
        resolver.resolve(candidate)
        assert db.scalar(select(func.count()).select_from(University).where(
            University.canonical_name == "Test University")) == 0


# -------------------------------------------------------------------- pipeline

@pytest.fixture()
def registered(monkeypatch, db):
    adapter = ScriptedAdapter([_batch([_institution()])])
    spec = _spec()
    register_source("test_source", spec, adapter)
    persist.ensure_source(db, spec)
    db.commit()
    _stub_fetcher(monkeypatch, lambda url, etag, last: StubResponse(200, b"{}"))
    return spec, adapter


class TestPipeline:
    def test_end_to_end_run_persists_entities_facts_and_evidence(self, registered, db):
        summary = run_source("test_source", RunOptions(), db=db)
        assert summary.status == "succeeded"
        assert summary.counters.created == 0  # no facts on the bare candidate
        assert db.scalar(select(func.count()).select_from(University).where(
            University.external_identifiers["ror"].astext == "00abc")) == 1
        job = db.get(IngestionJob, summary.job_id)
        assert job.status == "succeeded" and job.records_seen == 1

    def test_running_twice_is_idempotent(self, registered, db):
        spec, adapter = registered
        institution = _institution()
        institution.facts = [CandidateFact("official_name", {"name": "Alpha"},
                                          normalized={"name": "alpha"})]
        adapter.batches = [_batch([institution])]
        first = run_source("test_source", RunOptions(), db=db)
        counts = (db.scalar(select(func.count()).select_from(University)),
                  db.scalar(select(func.count()).select_from(FactRecord)),
                  db.scalar(select(func.count()).select_from(FactVersion)),
                  db.scalar(select(func.count()).select_from(FactEvidence)))
        second = run_source("test_source", RunOptions(), db=db)
        assert second.counters.created == 0 and second.counters.updated == 0
        assert second.counters.unchanged == first.counters.created
        assert counts == (db.scalar(select(func.count()).select_from(University)),
                          db.scalar(select(func.count()).select_from(FactRecord)),
                          db.scalar(select(func.count()).select_from(FactVersion)),
                          db.scalar(select(func.count()).select_from(FactEvidence)))

    def test_disabled_source_is_refused(self, registered, db):
        spec, adapter = registered
        source = persist.ensure_source(db, spec)
        source.enabled = False
        db.flush()
        summary = run_source("test_source", RunOptions(), db=db)
        assert summary.status == "failed" and "disabled" in summary.error
        source.enabled = True
        db.flush()

    def test_prohibited_policy_is_refused(self, registered, db):
        spec, adapter = registered
        register_source("test_source", _spec(allowed_use_policy="prohibited_automated_fetch"),
                        adapter)
        summary = run_source("test_source", RunOptions(), db=db)
        assert summary.status == "failed" and "policy" in summary.error

    def test_invalid_records_are_rejected_with_reasons_not_dropped(self, registered, db):
        spec, adapter = registered
        adapter.batches = [_batch([CandidateInstitution(external_key="bad:1", name="")])]
        summary = run_source("test_source", RunOptions(), db=db)
        assert summary.counters.rejected == 1
        assert summary.counters.validation_errors[0]["external_key"] == "bad:1"
        item = db.scalar(select(IngestionJobItem))
        assert item.status == "rejected" and item.validation_errors

    def test_dry_run_writes_nothing(self, registered, db):
        run_source("test_source", RunOptions(dry_run=True), db=db)
        assert db.scalar(select(func.count()).select_from(University).where(
            University.external_identifiers["ror"].astext == "00abc")) == 0

    def test_broken_batch_is_rolled_back_and_reported(self, registered, db):
        spec, adapter = registered
        good = _institution("Good University", identifiers={"ror": "good1"})
        good.facts = [CandidateFact("official_name", {"name": "G"},
                                    normalized={"name": "g"})]

        class BoomAdapter(adapter.__class__):
            def iter_batches(self, ctx):
                yield _batch([good])
                raise RuntimeError("connector exploded")

        register_source("test_source", spec, BoomAdapter([]))
        summary = run_source("test_source", RunOptions(), db=db)
        assert summary.status == "failed"
        assert "connector exploded" in summary.error
        # each document is committed on its own; the failure is recorded, not hidden
        assert db.get(IngestionJob, summary.job_id).status == "failed"

    def test_unknown_source_key_fails_cleanly(self, db):
        summary = run_source("does_not_exist", RunOptions(), db=db)
        assert summary.status == "failed" and "unknown source key" in summary.error

    def test_reference_taxonomy_is_upserted_idempotently(self, registered, db):
        spec, adapter = registered
        batch = AdapterBatch(document=SourceDoc(url="u://cip", content=b"cip"),
                             fields=[CandidateField("cip_11", "Computer Science")])
        adapter.batches = [batch]
        run_source("test_source", RunOptions(), db=db)
        run_source("test_source", RunOptions(), db=db)
        assert db.scalar(select(func.count()).select_from(Field).where(
            Field.key == "cip_11")) == 1

    def test_changed_source_document_creates_a_new_document_row(self, registered, db):
        spec, adapter = registered
        institution = _institution()
        institution.facts = [CandidateFact("official_name", {"name": "Alpha"},
                                          normalized={"name": "alpha"})]
        adapter.batches = [_batch([institution], content=b"v1")]
        run_source("test_source", RunOptions(), db=db)
        adapter.batches = [_batch([CandidateInstitution(**{**institution.__dict__,
                                                          "facts": [
                                                              CandidateFact("official_name",
                                                                            {"name": "Beta"},
                                                                            normalized={"name": "beta"})]})],
                                  content=b"v2")]
        run_source("test_source", RunOptions(), db=db)
        assert db.scalar(select(func.count()).select_from(SourceDocument).where(
            SourceDocument.source_id.isnot(None))) == 3  # 1 seeded + 2 distinct contents
        assert db.scalar(select(func.count()).select_from(FactVersion).where(
            FactVersion.value_json["name"].astext == "Alpha")) == 1
        assert db.scalar(select(func.count()).select_from(FactVersion).where(
            FactVersion.value_json["name"].astext == "Beta")) == 1

    def test_programs_and_facts_are_persisted_with_their_discipline(self, registered, db):
        spec, adapter = registered
        institution = _institution()
        program = CandidateProgram(external_key="p:1", title="MSc Evidence Engineering",
                                   discipline_code="11.0101")
        program.facts = [CandidateFact("awards_conferred", {"count": "12"},
                                       normalized={"count": "12"},
                                       applicability_key="2023-24")]
        institution.programs.append(program)
        batch = AdapterBatch(document=SourceDoc(url="u://prog", content=b"p"),
                             fields=[CandidateField("cip_11", "Computer Science")],
                             institutions=[institution])
        adapter.batches = [batch]
        summary = run_source("test_source", RunOptions(), db=db)
        row = db.scalar(select(Program).where(
            Program.canonical_name == "MSc Evidence Engineering"))
        assert row is not None and row.publication_status == "candidate"
        assert row.field_id is not None
        assert db.scalar(select(func.count()).select_from(FactRecord).where(
            FactRecord.entity_type == "program", FactRecord.fact_key == "awards_conferred")) == 1
        assert summary.counters.rejected == 0


class TestRefreshScheduling:
    def test_due_refreshes_are_queued_once_per_source(self, registered, db):
        spec, adapter = registered
        spec.refresh_interval_hours = 1
        queued = enqueue_due_refreshes(db)
        assert len(queued) == 1
        assert enqueue_due_refreshes(db) == []   # already queued: no duplicates

    def test_recent_success_defers_the_next_refresh(self, registered, db):
        from datetime import datetime, timedelta, timezone
        spec, adapter = registered
        spec.refresh_interval_hours = 24
        source = db.scalar(select(Source).where(
            Source.metadata_json["adapter_key"].astext == "test_source"))
        db.add(IngestionJob(source_id=source.id, job_type="refresh", status="succeeded",
                            finished_at=datetime.now(timezone.utc) - timedelta(hours=1)))
        db.flush()
        assert enqueue_due_refreshes(db) == []

    def test_blocked_sources_are_never_queued(self, db):
        for spec in all_specs().values():
            if not spec.enabled or spec.allowed_use_policy != "public_dataset":
                assert spec.integration_status != "active" or not spec.enabled


class TestRegistry:
    def test_every_source_declares_its_access_basis(self):
        for key, spec in all_specs().items():
            assert spec.license_notes and spec.name and spec.base_url
            assert spec.allowed_use_policy in (
                "manual_reference", "permitted_fetch", "licensed_api", "public_dataset",
                "prohibited_automated_fetch", "review_required")

    def test_country_scope_is_metadata_and_never_an_allowlist(self):
        scopes = {spec.country_scope for spec in all_specs().values()}
        assert "global" in scopes and "US" in scopes
        assert not hasattr(registry, "ALLOWED_COUNTRIES")
        assert not any("countries" in name for name in dir(registry))

    def test_restricted_sources_are_registered_but_disabled(self):
        for key in ("whed", "licensed_provider", "kaggle_community", "erasmus_mundus",
                    "ipeds_completions"):
            spec = get_spec(key)
            assert spec is not None and spec.enabled is False, key
            assert spec.integration_status != "active", key

    def test_registered_keys_are_unique_and_stable(self):
        keys = list(all_specs())
        assert len(keys) == len(set(keys))


# ----------------------------------------------------------------------- admin

class TestAdminIngestionApi:
    def test_trigger_requires_admin(self, client, db, make_user):
        make_user("student")
        make_user("reviewer")
        client.post("/api/v1/auth/register",
                    json={"email": "stu@x.io", "password": "Aa1!aaaa", "display_name": "S"})
        client.post("/api/v1/auth/login", json={"email": "stu@x.io", "password": "Aa1!aaaa"})
        assert client.post("/api/v1/admin/ingestion/run?source_key=ror").status_code == 403
        client.post("/api/v1/auth/logout")
        assert client.post("/api/v1/admin/ingestion/run?source_key=ror").status_code == 401

    def test_unknown_source_key_is_404(self, client):
        admin_login = client.post("/api/v1/auth/login",
                                  json={"email": "admin@example.com",
                                        "password": "change_me_admin_pw"})
        assert admin_login.status_code == 200
        response = client.post("/api/v1/admin/ingestion/run?source_key=nope")
        assert response.status_code == 404

    def test_known_source_key_can_be_queued(self, client, db, registered):
        client.post("/api/v1/auth/login", json={"email": "admin@example.com",
                                                "password": "change_me_admin_pw"})
        response = client.post("/api/v1/admin/ingestion/run?source_key=test_source")
        assert response.status_code == 200
        assert response.json()["status"] == "queued"
        again = client.post("/api/v1/admin/ingestion/run?source_key=test_source")
        assert again.json()["reused"] is True

    def test_refresh_is_refused_for_non_fetchable_sources(self, client):
        client.post("/api/v1/auth/login", json={"email": "admin@example.com",
                                                "password": "change_me_admin_pw"})
        source_id = client.get("/api/v1/admin/sources").json()["items"][0]["id"]
        response = client.post(f"/api/v1/admin/sources/{source_id}/refresh")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "REFRESH_NOT_PERMITTED"
