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
from app.ingestion.adapters.ipeds import (
    IpedsCompletionsAdapter,
    IpedsDirectoryAdapter,
    IpedsFinancialAdapter,
    NcesCipAdapter,
)
from app.ingestion.adapters.ror import RorAdapter
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
        source_key="ipeds_hd", name="IPEDS Institutional Directory (HD 2023)",
        base_url="https://nces.ed.gov/ipeds/datacenter/data/HD2023.zip",
        source_type="government", authority_tier=1,
        owner_or_publisher="U.S. National Center for Education Statistics (NCES), IPEDS",
        license_notes=("IPEDS data files are in the public domain (U.S. federal "
                       "government work); attribution to NCES/IPEDS requested."),
        terms_url="https://nces.ed.gov/ipeds/ipeds-definitions",
        allowed_use_policy="public_dataset", enabled=True,
        supported_data=("institution_name", "address", "institution_type", "classification",
                        "official_website", "programme_offerings", "location"),
        country_scope="US", refresh_interval_hours=24 * 30,
        rate_limit_notes="One bulk file download per run; cached locally with ETag revalidation.",
        request_rps=1.0, max_workers=2, timeout_seconds=300.0),
    "ipeds_ic": _spec(
        source_key="ipeds_ic", name="IPEDS Institutional Characteristics / Student Financial (IC 2023)",
        base_url="https://nces.ed.gov/ipeds/datacenter/data/IC2023.zip",
        source_type="government", authority_tier=1,
        owner_or_publisher="U.S. National Center for Education Statistics (NCES), IPEDS",
        license_notes="Public domain U.S. federal government data (NCES/IPEDS).",
        terms_url="https://nces.ed.gov/ipeds/ipeds-definitions",
        allowed_use_policy="public_dataset", enabled=True,
        supported_data=("room_rate", "board_rate", "application_fee"),
        country_scope="US", refresh_interval_hours=24 * 30,
        request_rps=1.0, max_workers=2, timeout_seconds=300.0),
    "nces_cip": _spec(
        source_key="nces_cip", name="NCES CIP taxonomy (discipline reference data)",
        base_url="https://nces.ed.gov/ipeds/cipcode/",
        source_type="government", authority_tier=1,
        owner_or_publisher="U.S. National Center for Education Statistics (NCES)",
        license_notes="Public domain U.S. federal government taxonomy.",
        allowed_use_policy="public_dataset", enabled=True,
        supported_data=("discipline_taxonomy",), country_scope="global",
        refresh_interval_hours=24 * 90, request_rps=1.0, max_workers=1),
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
    "ipeds_hd": IpedsDirectoryAdapter(),
    "ipeds_ic": IpedsFinancialAdapter(),
    "nces_cip": NcesCipAdapter(),
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