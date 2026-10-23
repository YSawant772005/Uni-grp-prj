"""The official UAL feed is parsed as source-backed candidates only."""
import json
import uuid
from types import SimpleNamespace

from app.ingestion.adapters.base import RunContext
from app.ingestion.adapters.ror import RorAdapter
from app.ingestion.adapters.ual import API, UalMastersAdapter
from app.ingestion.persist import InstitutionResolver
from app.ingestion.http import FetchError
from app.ingestion.types import CandidateInstitution
from app.models import Country, InstitutionIdentityReview, Source, SourceDocument, University


class _Fetcher:
    def __init__(self, payload):
        self.payload = payload
        self.url = None
        self.calls = []
        self.user_agent = 'test-agent'

    def get(self, url, **_kwargs):
        self.url = url
        self.calls.append(url)
        if 'planes' in self.payload and url != API:
            raise FetchError(url, 'no page fixture', status=404, permanent=True)
        content = json.dumps(self.payload, ensure_ascii=False).encode()
        return SimpleNamespace(text=lambda: content.decode(), content=content, status=200,
                               etag=None, last_modified=None)


def test_ual_adapter_keeps_only_unambiguous_single_institution_masters():
    fetcher = _Fetcher({"planes": [
        {"cod_plan": "7101", "nom_plan": "Máster en Comunicación Social",
         "nom_rama": "Artes y Humanidades", "interuni_sn": "N", "l_doble_sn": "N",
         "d_tip_ensenanza": "Semipresencial"},
        {"cod_plan": "7102", "nom_plan": "Joint Master", "interuni_sn": "S",
         "l_doble_sn": "N"},
        {"cod_plan": "7103", "nom_plan": "Doble Máster", "interuni_sn": "N",
         "l_doble_sn": "S"},
    ]})
    batch = next(UalMastersAdapter().iter_batches(RunContext(fetcher=fetcher)))
    assert fetcher.calls[0] == API
    assert len(batch.institutions) == 1
    candidate = batch.institutions[0]
    assert candidate.external_key == "ual:publisher:u04800001"
    assert candidate.programs[0].external_key == "ual:master:plan:7101"
    assert candidate.programs[0].title == "Máster en Comunicación Social"
    assert candidate.programs[0].official_url is None
    assert candidate.programs[0].facts[0].fact_key == "program_title_as_reported"
    assert candidate.programs[0].facts[0].excerpt == "Máster en Comunicación Social"
    assert candidate.programs[0].facts[0].status == "candidate"


def test_ror_query_emits_only_exact_name_or_alias_results():
    fetcher = _Fetcher({"items": [
        {"id": "https://ror.org/003d3xx08", "names": [
            {"types": ["ror_display", "label"], "value": "University of Almería"},
            {"types": ["alias", "label"], "value": "Universidad de Almería"}],
         "locations": [{"name": "Almería", "geonames_details": {"country_code": "ES"}}]},
        {"id": "https://ror.org/006zjws59", "names": [
            {"types": ["ror_display", "label"], "value": "University of Vic"}],
         "locations": [{"name": "Vic", "geonames_details": {"country_code": "ES"}}]},
    ]})
    batch = next(RorAdapter().iter_batches(RunContext(
        fetcher=fetcher, query="Universidad de Almería", max_records=1)))
    assert "query=Universidad" in fetcher.url
    assert [item.identifiers["ror"] for item in batch.institutions] == ["003d3xx08"]


def test_ror_bulk_country_partition_uses_supported_query_and_filter():
    fetcher = _Fetcher({"number_of_results": 1, "items": [
        {"id": "https://ror.org/003d3xx08", "names": [
            {"types": ["ror_display", "label"], "value": "University of Almería"}],
         "locations": [{"name": "Almería", "geonames_details": {"country_code": "ES"}}]},
    ]})
    batch = next(RorAdapter().iter_batches(RunContext(
        fetcher=fetcher, countries=["es"], max_pages=1)))
    assert "query.advanced=types%3Aeducation" in fetcher.url
    assert "filter=locations.geonames_details.country_code%3AES" in fetcher.url
    assert [item.identifiers["ror"] for item in batch.institutions] == ["003d3xx08"]


def test_ror_reports_global_api_cap_instead_of_claiming_complete_coverage():
    fetcher = _Fetcher({"number_of_results": 12000, "items": [
        {"id": "https://ror.org/003d3xx08", "names": [
            {"types": ["ror_display", "label"], "value": "University of Almería"}],
         "locations": [{"name": "Almería", "geonames_details": {"country_code": "ES"}}]},
    ]})
    batch = next(RorAdapter().iter_batches(RunContext(fetcher=fetcher, max_records=1)))
    assert any("10,000" in warning and "data dump" in warning for warning in batch.warnings)


def test_approved_identity_review_is_a_durable_source_scoped_link(db):
    country = db.query(Country).first()
    university = University(
        id=uuid.uuid4(), canonical_name="University of Almería", slug="university-almeria-test",
        country_code=country.code, external_identifiers={"ror": "003d3xx08"})
    source = Source(
        id=uuid.uuid4(), name="UAL", base_url=API, source_type="official_university",
        authority_tier=1, allowed_use_policy="public_dataset", license_notes="CC BY",
        enabled=True, metadata_json={"adapter_key": "ual_masters"})
    document = SourceDocument(
        id=uuid.uuid4(), source_id=source.id, canonical_url=API, title="UAL master's listing")
    db.add_all([university, source, document])
    db.flush()
    review = InstitutionIdentityReview(
        id=uuid.uuid4(), source_id=source.id, source_document_id=document.id,
        external_key="ual:publisher:u04800001", candidate_payload={},
        resolved_university_id=university.id, status="approved")
    db.add(review)
    db.flush()
    candidate = CandidateInstitution(
        external_key=review.external_key, name="Universidad de Almería", country_code="ES",
        website="https://www.ual.es", identifiers={"ual_dataset_publisher": "u04800001"})
    resolved, reason = InstitutionResolver(db).resolve(candidate, source.id)
    assert resolved == university.id
    assert reason == "reviewed_link"
