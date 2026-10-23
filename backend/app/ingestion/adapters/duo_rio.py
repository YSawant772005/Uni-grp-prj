"""Bounded connector for the official Dutch DUO/RIO higher-education overview.

The source is CC BY. It describes institution offerings, not university course
pages. Only rows explicitly classified as MASTER and carrying both a RIO
provider identifier and a stable offered-program UUID are emitted. Joint rows
are held out until the catalogue can represent all participating institutions.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from typing import Iterator
from urllib.parse import urlencode

from app.ingestion import cache
from app.ingestion.adapters.base import RunContext, SourceAdapter
from app.ingestion.normalize import clean_text, normalize_url, parse_date
from app.ingestion.types import (
    AdapterBatch, CandidateFact, CandidateInstitution, CandidateProgram, SourceDoc,
)

API = "https://onderwijsdata.duo.nl/api/3/action/datastore_search"
DATASET_URL = "https://onderwijsdata.duo.nl/datasets/ho_opleidingsoverzicht"
RESOURCE_ID = "ffffa7ad-e6a2-4ba7-9fc2-a09df4128555"
PAGE_SIZE = 100
MAX_RECORDS_PER_RUN = 5_000
MAX_ROWS_SCANNED_PER_RUN = 10_000

IDENTITY_COLUMNS = (
    "ONDERWIJSAANBIEDERID", "ONDERWIJSAANBIEDER_NAAM", "ERKENDEOPLEIDINGSCODE",
    "OPLEIDINGSEENHEIDCODE", "AANGEBODEN_OPLEIDINGCODE",
)


class DuoRioAdapter(SourceAdapter):
    """Emit Dutch Master's offering candidates with row-level RIO identifiers."""

    source_key = "duo_rio_masters"

    def iter_batches(self, ctx: RunContext) -> Iterator[AdapterBatch]:
        if ctx.max_records is None or ctx.max_records <= 0:
            raise ValueError("DUO/RIO retrieval requires an explicit positive --limit.")
        if ctx.max_records > MAX_RECORDS_PER_RUN:
            raise ValueError(f"DUO/RIO --limit cannot exceed {MAX_RECORDS_PER_RUN} records per run.")
        if ctx.max_records > 100 and not ctx.checkpoint.get('bounded_bulk_snapshot'):
            raise ValueError('DUO/RIO runs above 100 require the frozen, exact-plan bulk import tool.')

        target_count = ctx.max_records
        scan_budget = min(MAX_ROWS_SCANNED_PER_RUN, target_count * 40)
        offset = 0
        emitted = 0
        seen_offerings: set[str] = set()

        while emitted < target_count and offset < scan_budget and offset // PAGE_SIZE < ctx.max_pages:
            limit = min(PAGE_SIZE, scan_budget - offset)
            params = {
                "resource_id": RESOURCE_ID,
                "filters": json.dumps({"GRAAD": "MASTER", **({"ONDERWIJSAANBIEDERID": ctx.query} if ctx.query else {})}, separators=(",", ":")),
                "limit": limit,
                "offset": offset,
                "sort": "_id asc",
            }
            url = f"{API}?{urlencode(params)}"
            content, status, etag, last_modified, attempts, retrieved_at = _fetch_page(
                ctx, offset=offset, limit=limit, url=url)
            try:
                payload = json.loads(content)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"DUO/RIO returned invalid JSON at offset {offset}.") from exc
            if not isinstance(payload, dict) or payload.get("success") is not True:
                raise ValueError(f"DUO/RIO API response was unsuccessful at offset {offset}.")
            data = payload.get("result")
            rows = data.get("records") if isinstance(data, dict) else None
            if not isinstance(rows, list):
                raise ValueError(f"DUO/RIO response has no records list at offset {offset}.")
            if not rows:
                return

            grouped: dict[str, CandidateInstitution] = {}
            accepted_rows: list[dict] = []
            warnings: list[str] = []
            for row in rows:
                if not isinstance(row, dict) or clean_text(row.get("GRAAD")) != "MASTER":
                    warnings.append("row skipped: source degree classification is not MASTER")
                    continue
                if (clean_text(row.get("SAMENWERKEND_MET")) or clean_text(row.get("BUITENLANDSEPARTNER"))
                        or "joint degree" in (clean_text(row.get("NAAM_LANG")) or "").casefold()):
                    warnings.append("joint/partner offering held for relationship review")
                    continue
                provider_id = clean_text(row.get("ONDERWIJSAANBIEDERID"))
                provider_name = clean_text(row.get("ONDERWIJSAANBIEDER_NAAM"))
                offered_id = _stable_offering_id(row)
                title = clean_text(row.get("NAAM_LANG")) or clean_text(row.get("INTERNATIONALE_NAAM"))
                if not provider_id or not provider_name or not offered_id or not title:
                    warnings.append("row skipped: missing provider identity, offering UUID, or official title")
                    continue
                offering_key = f"duo:offering:{offered_id}"
                if offering_key in seen_offerings:
                    warnings.append(f"duplicate offering row skipped: {offering_key}")
                    continue
                seen_offerings.add(offering_key)

                institution = grouped.get(provider_id)
                if institution is None:
                    website = normalize_url(row.get("WEBSITE"))
                    institution = CandidateInstitution(
                        external_key=f"duo:rio-provider:{provider_id}",
                        name=provider_name[:250], country_code="NL", country_name="Netherlands",
                        # Registry WEBSITE is captured as a candidate fact below.
                        # Do not write it into University's canonical website field
                        # until a reviewer validates the destination.
                        website=None,
                        identifiers={"rio_provider_id": provider_id},
                        identifier_scopes={"rio_provider_id": "reporting_unit"},
                    )
                    institution.facts.extend([
                        CandidateFact(
                            "official_name", {"name": provider_name, "source_field": "ONDERWIJSAANBIEDER_NAAM"},
                            normalized={"name": provider_name.casefold()},
                            excerpt=provider_name,
                            locator=f"records[AANGEBODEN_OPLEIDINGCODE={offered_id}]"),
                        CandidateFact(
                            "official_website_url", {"url": website, "verification": "candidate_from_registry"},
                            normalized={"url": website},
                            excerpt=website,
                            locator=f"records[AANGEBODEN_OPLEIDINGCODE={offered_id}]"),
                    ])
                    grouped[provider_id] = institution
                elif institution.name != provider_name:
                    warnings.append(f"provider name conflicts for RIO ID {provider_id}; row held")
                    continue

                offering_end = parse_date(row.get("AANGEBODEN_OPLEIDING_EINDDATUM"))
                if offering_end and offering_end < date.today():
                    warnings.append(f"expired offering held out of current pilot: {offering_key}")
                    continue
                facts = _program_facts(row, title, offered_id)
                institution.programs.append(CandidateProgram(
                    external_key=offering_key,
                    title=title,
                    degree_level="masters",
                    delivery_language={"ENG": "en", "NLD": "nl", "DEU": "de", "FRA": "fr"}.get((clean_text(row.get("VOERTAAL")) or "").upper()),
                    study_mode={"voltijd": "full_time", "deeltijd": "part_time"}.get((clean_text(row.get("VORM")) or "").casefold()),
                    # The source WEBSITE field is an institution-level URL in
                    # this schema; it is deliberately not assigned as a course URL.
                    official_url=None,
                    facts=facts,
                ))
                accepted_rows.append({
                    key: row.get(key) for key in (
                        "_id", *IDENTITY_COLUMNS, "NIVEAU", "GRAAD", "NAAM_LANG",
                        "INTERNATIONALE_NAAM", "STUDIELAST", "VOERTAAL", "VORM",
                        "AANGEBODEN_OPLEIDING_BEGINDATUM", "AANGEBODEN_OPLEIDING_EINDDATUM",
                        "WEBSITE", "ONDERWIJSLOCATIECODE", "ONDERWIJSLOCATIESTRAAT",
                        "ONDERWIJSLOCATIEPLAATS",
                    )
                })
                emitted += 1
                if emitted >= target_count:
                    break

            excerpt = json.dumps({"dataset": DATASET_URL, "resource_id": RESOURCE_ID,
                                  "offset": offset, "rows": accepted_rows},
                                 ensure_ascii=False, separators=(",", ":"))
            yield AdapterBatch(
                document=SourceDoc(
                    url=url, canonical_url=url,
                    title="DUO/RIO HO Opleidingsoverzicht — Master's offerings",
                    document_type="json", content=content,
                    content_excerpt=excerpt[:20_000], http_status=status,
                    etag=etag, last_modified=last_modified,
                    retrieved_at=retrieved_at,
                    retrieval_attempt_count=attempts,
                ),
                institutions=[i for i in grouped.values() if i.programs], warnings=warnings, skipped_records=len(warnings),
            )
            offset += len(rows)
            if len(rows) < limit:
                return


def _fetch_page(ctx: RunContext, *, offset: int, limit: int, url: str
                ) -> tuple[bytes, int, str | None, str | None, int, datetime | None]:
    if ctx.checkpoint.get('frozen_replay'):
        result = ctx.fetcher.get(url)
        return result.content, result.status, result.etag, result.last_modified, 0, None
    # Provider-specific requests must not reuse another provider's cached rows.
    import hashlib
    scope = '-' + hashlib.sha256(ctx.query.encode()).hexdigest()[:16] if ctx.query else ''
    label = f"duo-rio-masters{scope}-{offset}-{limit}.json"
    path = cache.cache_path(ctx, label)
    metadata = cache.read_meta(ctx, label)
    if ctx.offline:
        if not path.exists():
            raise ValueError(f"Offline DUO/RIO page cache is missing for offset {offset}.")
        timestamp = _parse_timestamp(metadata.get("retrieved_at"))
        if timestamp is None:
            raise ValueError(
                f"Offline DUO/RIO page cache at offset {offset} has no retrieval timestamp.")
        return (path.read_bytes(), 200, metadata.get("etag"), metadata.get("last_modified"),
                0, timestamp)

    result = ctx.fetcher.get(url, etag=metadata.get("etag"),
                             last_modified=metadata.get("last_modified"))
    if result.not_modified:
        if not path.exists():
            raise ValueError(f"DUO/RIO returned not-modified without a cached page at offset {offset}.")
        content = path.read_bytes()
    else:
        content = result.content
        cache.store(ctx, label, content)
    cache.write_meta(ctx, label, {"etag": result.etag, "last_modified": result.last_modified})
    return (content, result.status, result.etag, result.last_modified,
            getattr(result, "attempts", 1), None)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _stable_offering_id(row: dict) -> str | None:
    """Use the official UUID for the provider-specific offered degree row."""
    for key in ("AANGEBODEN_OPLEIDINGCODE", "EIGEN_AANGEBODEN_OPLEIDINGSLEUTEL"):
        value = clean_text(row.get(key))
        if not value:
            continue
        try:
            return str(uuid.UUID(value))
        except (ValueError, AttributeError):
            return None
    return None


def _program_facts(row: dict, title: str, offered_id: str) -> list[CandidateFact]:
    locator = f"records[AANGEBODEN_OPLEIDINGCODE={offered_id}]"
    facts = [CandidateFact(
        "program_title_as_reported", {"title": title, "language": "source NAAM_LANG"},
        normalized={"title": title.casefold()}, excerpt=title, locator=locator),
        CandidateFact(
        "rio_program_identity", {
            "offering_id": offered_id,
            "recognized_program_code": clean_text(row.get("ERKENDEOPLEIDINGSCODE")),
            "program_unit_code": clean_text(row.get("OPLEIDINGSEENHEIDCODE")),
            "offering_local_key": clean_text(row.get("EIGEN_AANGEBODEN_OPLEIDINGSLEUTEL")),
            "level": clean_text(row.get("NIVEAU")), "degree": clean_text(row.get("GRAAD")),
            "offering_type": clean_text(row.get("SOORT")),
        }, excerpt=f"DUO/RIO offered-program UUID {offered_id}", locator=locator),
    ]
    english_title = clean_text(row.get("INTERNATIONALE_NAAM"))
    if english_title:
        facts.append(CandidateFact(
            "international_program_title_as_reported", {"title": english_title},
            normalized={"title": english_title.casefold()}, excerpt=english_title, locator=locator))

    study_load = clean_text(row.get("STUDIELAST"))
    if study_load:
        facts.append(CandidateFact(
            "study_load_as_reported", {"value": study_load, "source_field": "STUDIELAST"},
            normalized={"value": study_load}, excerpt=f"STUDIELAST: {study_load}", locator=locator))
    language = clean_text(row.get("VOERTAAL"))
    if language:
        facts.append(CandidateFact(
            "teaching_language_as_reported", {"code": language, "source_field": "VOERTAAL"},
            normalized={"code": language.upper()}, excerpt=f"VOERTAAL: {language}", locator=locator))
    mode = clean_text(row.get("VORM"))
    if mode:
        facts.append(CandidateFact(
            "study_form_as_reported", {"value": mode}, normalized={"value": mode.casefold()},
            excerpt=f"VORM: {mode}", locator=locator))
    website = normalize_url(row.get("WEBSITE"))
    if website:
        facts.append(CandidateFact(
            "website_as_reported", {"url": website, "classification": "institution_or_source_candidate"},
            normalized={"url": website}, excerpt=f"WEBSITE: {website}", locator=locator))
    location = {
        "code": clean_text(row.get("ONDERWIJSLOCATIECODE")),
        "street": clean_text(row.get("ONDERWIJSLOCATIESTRAAT")),
        "city": clean_text(row.get("ONDERWIJSLOCATIEPLAATS")),
    }
    if any(location.values()):
        facts.append(CandidateFact(
            "study_location_as_reported", location,
            normalized={k: v for k, v in location.items() if v},
            excerpt="; ".join(f"{k}: {v}" for k, v in location.items() if v), locator=locator))

    start = parse_date(row.get("AANGEBODEN_OPLEIDING_BEGINDATUM"))
    end = parse_date(row.get("AANGEBODEN_OPLEIDING_EINDDATUM"))
    facts.append(CandidateFact(
        "offering_validity_period", {"valid_from": start.isoformat() if start else None,
                                      "valid_to": end.isoformat() if end else None},
        normalized={"valid_from": start.isoformat() if start else None,
                    "valid_to": end.isoformat() if end else None},
        excerpt=f"Offering period: {start or 'unknown'} to {end or 'open-ended'}",
        locator=locator, effective_from=start, effective_to=end))
    return facts
