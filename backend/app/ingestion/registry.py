"""Global source registry.

One stable key per connector, independent of country. Adding a country, a
publisher or a whole new registry is a configuration change here — no core code
has to be rewritten, and there is no three-country allowlist anywhere.

``allowed_use_policy`` and ``enabled`` are enforced by the pipeline *and* by the
existing admin refresh endpoint: a source that is not permitted to be fetched, or
that is disabled, can never be ingested by accident.
"""
from __future__ import annotations

from app.ingestion.adapters.base import AdapterSpec, SourceAdapter
from app.ingestion.adapters.duo_rio import DuoRioAdapter
from app.ingestion.adapters.ipeds import (
    IPEDS_HD_RELEASE_YEAR,
    IPEDS_IC_RELEASE_YEAR,
    IpedsCompletionsAdapter,
    IpedsDirectoryAdapter,
    IpedsFinancialAdapter,
    NcesCipAdapter,
)
from app.ingestion.adapters.monmaster import MonMasterAdapter
from app.ingestion.adapters.ror import RorAdapter
from app.ingestion.adapters.ual import UalMastersAdapter
from app.ingestion.adapters.webpage import FieldRule, WebPageAdapter, WebPageConfig

FETCHABLE_POLICIES = ("permitted_fetch", "licensed_api", "public_dataset")


def _spec(**kw) -> AdapterSpec:
    return AdapterSpec(**kw)


SPECS: dict[str, AdapterSpec] = {
    "ror": _spec(
        source_key="ror", name="Research Organization Registry (ROR)",
        base_url="https://api.ror.org/v2/organizations",
        source_type="regulator", authority_tier=2,
        owner_or_publisher="ROR Community / Research Organization Registry",
        license_notes=("ROR data is released under CC0 1.0 "
                       "(https://ror.readme.io/docs/ror-data-liberation); attribution "
                       "requested, commercial reuse and redistribution permitted."),
        terms_url="https://ror.readme.io/docs/ror-data-liberation",
        allowed_use_policy="public_dataset", enabled=True,
        supported_data=("institution_name", "aliases", "official_website", "country",
                        "identifiers", "location"),
        country_scope="global", refresh_interval_hours=168,
        rate_limit_notes="Paged REST API; runs with a polite request rate and bounded concurrency.",
        request_rps=8.0, max_workers=6,
        notes="Institution identity only; publishes no tuition, admissions or programme data."),
    "ipeds_hd": _spec(
        source_key="ipeds_hd", name=f"IPEDS Institutional Directory (HD {IPEDS_HD_RELEASE_YEAR})",
        base_url=f"https://nces.ed.gov/ipeds/datacenter/data/HD{IPEDS_HD_RELEASE_YEAR}.zip",
        source_type="government", authority_tier=1,
        owner_or_publisher="U.S. National Center for Education Statistics (NCES), IPEDS",
        license_notes=("IPEDS data files are in the public domain (U.S. federal "
                       "government work); attribution to NCES/IPEDS requested."),
        terms_url="https://nces.ed.gov/ipeds/ipeds-definitions",
        allowed_use_policy="public_dataset", enabled=True,
        supported_data=("institution_name", "address", "institution_type", "classification",
                        "official_website", "graduate_offering_flags", "location"),
        country_scope="US", refresh_interval_hours=None,
        rate_limit_notes="One bulk file download per run; cached locally with ETag revalidation.",
        request_rps=1.0, max_workers=2, timeout_seconds=300.0,
        notes=(f"NCES official HD directory release {IPEDS_HD_RELEASE_YEAR}, checked against its "
               "official dictionary. Institution metadata and graduate-offering flags only; "
               "not a named Master's catalogue. Bounded manual refresh only until a schedule "
               "is explicitly approved."),
        requires_explicit_limit=True),
    "ipeds_ic": _spec(
        source_key="ipeds_ic", name=f"IPEDS Institutional Characteristics and Charges (IC {IPEDS_IC_RELEASE_YEAR})",
        base_url=f"https://nces.ed.gov/ipeds/datacenter/data/IC{IPEDS_IC_RELEASE_YEAR}.zip",
        source_type="government", authority_tier=1,
        owner_or_publisher="U.S. National Center for Education Statistics (NCES), IPEDS",
        license_notes="Public domain U.S. federal government data (NCES/IPEDS).",
        terms_url="https://nces.ed.gov/ipeds/ipeds-definitions",
        allowed_use_policy="public_dataset", enabled=True,
        integration_status="historical_snapshot_manual_only",
        supported_data=("institution_reported_room_board_charges", "graduate_application_fee"),
        country_scope="US", refresh_interval_hours=None,
        request_rps=1.0, max_workers=2, timeout_seconds=300.0,
        notes=(f"NCES official IC release {IPEDS_IC_RELEASE_YEAR}, dictionary-verified for "
               f"academic year {IPEDS_IC_RELEASE_YEAR}-{str(int(IPEDS_IC_RELEASE_YEAR) + 1)[-2:]}. "
               "IC2024 no longer contains the mapped charge fields, so this is explicitly a "
               "historical snapshot, not current tuition. Institution-level figures only; "
               "bounded manual refresh, no scheduler."),
        requires_explicit_limit=True),
    "nces_cip": _spec(
        source_key="nces_cip", name="NCES CIP taxonomy (discipline reference data)",
        base_url="https://nces.ed.gov/ipeds/cipcode/",
        source_type="government", authority_tier=1,
        owner_or_publisher="U.S. National Center for Education Statistics (NCES)",
        license_notes="Public domain U.S. federal government taxonomy.",
        allowed_use_policy="public_dataset", enabled=True,
        supported_data=("discipline_taxonomy",), country_scope="global",
        refresh_interval_hours=24 * 90, request_rps=1.0, max_workers=1),
    "ual_masters": _spec(
        source_key="ual_masters", name="University of Almería Official Master's Catalogue",
        base_url="https://campus.ual.es/ual/api/estudios/planes/titulaciones/MOF/es",
        source_type="official_university", authority_tier=1,
        owner_or_publisher="University of Almería",
        license_notes=("Datos.gob.es lists the 'Títulos Universitarios' dataset, including "
                       "the official master's JSON distribution, under CC BY. Attribute "
                       "Universidad de Almería and indicate modifications."),
        terms_url="https://datos.gob.es/es/catalogo/u04800001-titulos-universitarios",
        allowed_use_policy="public_dataset", enabled=True,
        supported_data=("official_master_program_name", "plan_code", "discipline_area",
                        "delivery_mode_as_reported"),
        country_scope="ES", refresh_interval_hours=24 * 30,
        rate_limit_notes="One JSON feed, one robots-checked catalogue and at most five programme pages; bounded redirects and retries.", request_rps=0.5, max_workers=1,
        notes=("The initial pilot excludes inter-university and double-master rows because "
               "the current program model does not represent their partner/award structure. "
               "The source does not publish tuition, deadlines, duration or admissions "
               "requirements in this feed; these remain unknown. Supplementary public webpages "
               "are bounded reference evidence, subject to robots/access checks; the dataset's "
               "CC BY declaration is not asserted as a licence for all website content.")),
    "fr_monmaster": _spec(
        source_key="fr_monmaster", name="French Mon Master 2025 official catalogue snapshot",
        base_url="https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1/catalog/datasets/fr-esr-mon_master/records",
        source_type="government", authority_tier=1,
        owner_or_publisher="French Ministry of Higher Education, Research and Space (MESRE)",
        license_notes=("The official 2025 dataset methodology identifies Licence Ouverte / Open Licence. "
                       "This connector selects programme identity, institution, discipline, delivery "
                       "mode, location and campaign fields only; application/outcome statistics are "
                       "not requested or persisted. Attribute MESRE and identify the 2025 snapshot."),
        terms_url="https://data.enseignementsup-recherche.gouv.fr/explore/dataset/fr-esr-mon_master/",
        allowed_use_policy="public_dataset", enabled=True,
        supported_data=("masters_program_name", "programme_track", "uai_reporting_unit",
                        "discipline", "delivery_mode_as_reported", "historical_campaign"),
        country_scope="FR", refresh_interval_hours=None, request_rps=0.5, max_workers=1,
        notes=("Historical 2025 application-campaign catalogue snapshot (8,167 offerings at "
               "the verified API snapshot). An explicit --limit is mandatory. It supplies no "
               "individual official programme URL; imports remain unpublished candidates. "
               "Multi-establishment INM relationships require separate validated evidence."),
        requires_explicit_limit=True),
    "duo_rio_masters": _spec(
        source_key="duo_rio_masters", name="DUO/RIO Dutch Higher-Education Master's Offerings",
        base_url="https://onderwijsdata.duo.nl/api/3/action/datastore_search",
        source_type="government", authority_tier=1,
        owner_or_publisher="Dienst Uitvoering Onderwijs (DUO), Netherlands",
        license_notes=("The official DUO Open Data catalogue identifies this dataset as CC BY 4.0. "
                       "Attribute DUO and link the dataset; preserve source row identifiers and "
                       "state that UniShortlist selected/normalized records."),
        terms_url="https://creativecommons.org/licenses/by/4.0/",
        allowed_use_policy="public_dataset", enabled=True,
        integration_status="bounded_manual_only",
        supported_data=("master_degree_offerings", "official_titles", "provider_identifiers",
                        "study_load_as_reported", "teaching_language_as_reported",
                        "study_location_as_reported", "offering_validity_dates"),
        country_scope="NL", refresh_interval_hours=None,
        rate_limit_notes="At most 0.5 requests/second; explicit limit required, max 5,000 offerings "
                         "and 10,000 scanned rows per run. Bulk development writes require an approved exact plan.",
        request_rps=0.5, max_workers=1, timeout_seconds=30.0,
        notes=("Source: DUO HO Opleidingsoverzicht (RIO), resource "
               "ffffa7ad-e6a2-4ba7-9fc2-a09df4128555; current/future offering records. "
               "Requires GRAAD=MASTER, provider id and a stable offering UUID. The row WEBSITE "
               "is treated as a candidate institution site, never as a program page. Rows with "
               "joint/foreign partner fields remain held for relationship review. No automatic "
               "identity approval, fact verification or publication. Manual only: no refresh "
               "interval has been approved."),
        requires_explicit_limit=True),
    "ipeds_completions": _spec(
        source_key="ipeds_completions",
        name="IPEDS Completions (C 2023) — programme awards by CIP code",
        base_url="https://nces.ed.gov/ipeds/datacenter/data/C2023_A.zip",
        source_type="government", authority_tier=1,
        owner_or_publisher="U.S. National Center for Education Statistics (NCES), IPEDS",
        license_notes="Public domain U.S. federal government data (NCES/IPEDS).",
        allowed_use_policy="public_dataset", enabled=False,
        integration_status="blocked_pending_data_dictionary",
        supported_data=("masters_programme_existence", "awards_conferred"),
        country_scope="US", refresh_interval_hours=24 * 30,
        notes=("Disabled: the published download set ships no data dictionary, so the "
               "meaning of the AWLEVEL codes could not be confirmed against an official "
               "label file. Enabling this would mean guessing which code is a Master's "
               "degree, i.e. fabricating programme records. Supply the official "
               "AWLEVEL label mapping to enable it.")),
    "whed": _spec(
        source_key="whed", name="World Higher Education Database (WHED)",
        base_url="https://whed.net/",
        source_type="regulator", authority_tier=2,
        owner_or_publisher="UNESCO / IAU / World Higher Education Database",
        license_notes=("WHED terms restrict copying substantial parts of the portal "
                       "without prior consent; no bulk extraction or redistribution "
                       "without written permission."),
        terms_url="https://whed.net/using-whed.html",
        allowed_use_policy="prohibited_automated_fetch", enabled=False,
        integration_status="blocked_terms_restriction",
        supported_data=("institution_name", "institution_type", "recognition"),
        country_scope="global",
        notes="Registered for transparency only; automated access is refused by policy."),
    "erasmus_mundus": _spec(
        source_key="erasmus_mundus", name="Erasmus Mundus Joint Master Degrees catalogue",
        base_url="https://erasmus-plus.ec.europa.eu/",
        source_type="government", authority_tier=1,
        owner_or_publisher="European Commission (DG EAC)",
        license_notes=("European Commission reuse policy applies (CC BY 4.0 unless the "
                       "page states otherwise); reuse must attribute the Commission."),
        terms_url="https://commission.europa.eu/legal/copyright-and-licence_en",
        allowed_use_policy="review_required", enabled=False,
        integration_status="awaiting_access_evaluation",
        supported_data=("masters_programme_name", "official_program_url", "consortium"),
        country_scope="EU",
        notes=("Registered for transparency. The host did not respond to connections "
               "from this environment during setup; evaluate accessibility and "
               "robots policy before enabling.")),
    "licensed_provider": _spec(
        source_key="licensed_provider", name="Licensed data provider (integration slot)",
        base_url="https://example.invalid/licensed-provider",
        source_type="licensed_aggregator", authority_tier=4,
        owner_or_publisher="to be contracted",
        license_notes="No licence has been agreed; no endpoints are assumed or contacted.",
        allowed_use_policy="licensed_api", enabled=False,
        integration_status="awaiting_credentials_and_licence",
        supported_data=(), country_scope="global",
        notes=("Configurable integration interface only. Supply credentials and a signed "
               "licence, then map the provider payload to CandidateInstitution in an "
               "adapter — do not invent endpoints.")),
    "kaggle_community": _spec(
        source_key="kaggle_community", name="Kaggle / community datasets (import slot)",
        base_url="https://www.kaggle.com/datasets",
        source_type="other", authority_tier=5,
        owner_or_publisher="community contributors",
        license_notes=("Per-dataset licence must be reviewed (origin, licence, "
                       "publication date, fields, intended use) before any import."),
        allowed_use_policy="review_required", enabled=False,
        integration_status="awaiting_dataset_review",
        supported_data=(), country_scope="global",
        notes=("No dataset is imported. An unverified community CSV must never be "
               "promoted into authoritative admissions or tuition data.")),
}

_ADAPTERS: dict[str, SourceAdapter] = {
    "ror": RorAdapter(),
    "ual_masters": UalMastersAdapter(),
    "ipeds_hd": IpedsDirectoryAdapter(),
    "ipeds_ic": IpedsFinancialAdapter(),
    "nces_cip": NcesCipAdapter(),
    "fr_monmaster": MonMasterAdapter(),
    "duo_rio_masters": DuoRioAdapter(),
    "ipeds_completions": IpedsCompletionsAdapter(),
}


def register_source(source_key: str, spec: AdapterSpec, adapter: SourceAdapter) -> None:
    """Add a connector at runtime (used by operator scripts and tests)."""
    SPECS[source_key] = spec
    _ADAPTERS[source_key] = adapter


def get_adapter(source_key: str) -> SourceAdapter | None:
    return _ADAPTERS.get(source_key)


def get_spec(source_key: str) -> AdapterSpec | None:
    return SPECS.get(source_key)


def enabled_specs() -> dict[str, AdapterSpec]:
    return {k: v for k, v in SPECS.items() if v.enabled}


def all_specs() -> dict[str, AdapterSpec]:
    return dict(SPECS)


__all__ = ["SPECS", "FETCHABLE_POLICIES", "AdapterSpec", "FieldRule", "WebPageAdapter",
           "WebPageConfig", "all_specs", "enabled_specs", "get_adapter", "get_spec",
           "register_source"]
