"""Research Organization Registry (ROR) — global research/institution registry.

Access basis: the public ROR v2 API, https://api.ror.org. ROR data is released
under CC0 1.0 (https://ror.readme.io/docs/ror-data-liberation), which permits
automated retrieval and redistribution with attribution. Coverage is worldwide
(30k+ education organizations across every continent), which keeps the
architecture country-agnostic: any country can be added by configuration.

ROR is an authority for *institution identity* (name, aliases, official
website, country, identifiers). It does not publish tuition, admissions or
programme-level data; those stay unknown rather than guessed.
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Iterator
from urllib.parse import urlencode, urlsplit

from app.ingestion.adapters.base import RunContext, SourceAdapter
from app.ingestion.http import FetchError
from app.ingestion.normalize import (
    clean_text,
    domain_of,
    name_key,
    normalize_aliases,
    normalize_url,
)
from app.ingestion.types import AdapterBatch, CandidateFact, CandidateInstitution

API = "https://api.ror.org/v2/organizations"
EDUCATION_QUERY = "types:education"
ROR_API_MAX_PAGES = 500


class RorAdapter(SourceAdapter):
    source_key = "ror"

    def iter_batches(self, ctx: RunContext) -> Iterator[AdapterBatch]:
        if ctx.query:
            url = f"{API}?{urlencode({'query': ctx.query})}"
            result = ctx.fetcher.get(url)
            payload = json.loads(result.text())
            candidates = [self._to_institution(item, 1) for item in payload.get("items") or []]
            exact = [candidate for candidate in candidates if candidate and
                     (name_key(candidate.name) == name_key(ctx.query) or
                      any(name_key(alias) == name_key(ctx.query) for alias in candidate.aliases))]
            if ctx.max_records is not None:
                exact = exact[:ctx.max_records]
            from app.ingestion.types import SourceDoc
            yield AdapterBatch(
                document=SourceDoc(url=url, title=f"ROR search: {ctx.query}",
                                   document_type="json", content=result.content,
                                   http_status=result.status, etag=result.etag,
                                   last_modified=result.last_modified,
                                   retrieval_attempt_count=getattr(result, "attempts", 1)),
                institutions=exact,
                warnings=[] if exact else ["ROR query returned no exact name/alias match."],
            )
            return
        emitted = 0
        countries = list(dict.fromkeys(code.strip().upper() for code in ctx.countries)) \
            if ctx.countries else [None]
        if any(not code or len(code) != 2 or not code.isalpha() for code in countries if code):
            raise ValueError("ROR country filters must be two-letter ISO country codes.")
        max_pages = min(ctx.max_pages, ROR_API_MAX_PAGES)
        for country in countries:
            for page in range(1, max_pages + 1):
                params = {"query.advanced": EDUCATION_QUERY, "page": page}
                if country:
                    params["filter"] = f"locations.geonames_details.country_code:{country}"
                url = f"{API}?{urlencode(params)}"
                try:
                    result = ctx.fetcher.get(url)
                except FetchError as exc:
                    if exc.status in (400, 404) or exc.permanent:
                        return
                    raise
                payload = json.loads(result.text())
                if payload.get("errors"):
                    raise ValueError("ROR API rejected the requested page or filter.")
                items = payload.get("items") or []
                if not items:
                    break
                institutions = [self._to_institution(item, page) for item in items]
                institutions = [item for item in institutions if item is not None]
                remaining = None if ctx.max_records is None else ctx.max_records - emitted
                if remaining is not None:
                    if remaining <= 0:
                        return
                    institutions = institutions[:remaining]
                warnings = []
                result_count = payload.get("number_of_results")
                if isinstance(result_count, int) and result_count > 10_000:
                    warnings.append(
                        "This ROR query exceeds the API's 10,000-result ceiling; "
                        "use the official ROR data dump for complete coverage.")
                if country is None:
                    warnings.append(
                        "Global ROR API retrieval is capped at 10,000 records; "
                        "supply --country to query independent country partitions or use the data dump.")
                from app.ingestion.types import SourceDoc
                doc = SourceDoc(url=url, title=f"ROR education organizations {country or 'global'} page {page}",
                                document_type="json", content=result.content,
                                http_status=result.status, etag=result.etag,
                                last_modified=result.last_modified,
                                retrieval_attempt_count=getattr(result, "attempts", 1))
                yield AdapterBatch(document=doc, institutions=institutions,
                                   warnings=warnings if page == 1 else [])
                emitted += len(institutions)
                if ctx.max_records is not None and emitted >= ctx.max_records:
                    return
                if len(items) < 20:
                    break

    # ------------------------------------------------------------------ parsing
    def _to_institution(self, item: dict, page: int) -> CandidateInstitution | None:
        ror_url = clean_text(item.get("id")) or ""
        ror_id = ror_url.rstrip("/").rsplit("/", 1)[-1]
        if not ror_id:
            return None
        names = item.get("names") or []
        official = next((n["value"] for n in names
                         if "ror_display" in (n.get("types") or [])), None)
        official = clean_text(official) or next(
            (clean_text(n.get("value")) for n in names if "label" in (n.get("types") or [])), None)
        if not official:
            return None
        aliases = normalize_aliases(
            [n.get("value") for n in names if "ror_display" not in (n.get("types") or [])])

        location = (item.get("locations") or [{}])[0]
        geo = location.get("geonames_details") or {}
        website = next((normalize_url(link.get("value")) for link in (item.get("links") or [])
                        if link.get("type") == "website" and link.get("value")), None)

        identifiers = {"ror": ror_id}
        for ext in item.get("external_ids") or []:
            value = clean_text(ext.get("preferred")) or next(
                (clean_text(v) for v in (ext.get("all") or []) if clean_text(v)), None)
            if value:
                identifiers[f"ror_{ext.get('type')}"] = value

        candidate = CandidateInstitution(
            external_key=f"ror:{ror_id}",
            name=official,
            aliases=aliases,
            identifiers=identifiers,
            country_code=clean_text(geo.get("country_code")),
            country_name=clean_text(geo.get("country_name")),
            region=clean_text(geo.get("continent_name")),
            city=clean_text(location.get("name")),
            admin_region=clean_text(geo.get("country_subdivision_name")),
            latitude=_decimal(geo.get("lat")),
            longitude=_decimal(geo.get("lng")),
            website=website,
        )
        page_url = item.get("id")
        candidate.facts = [
            CandidateFact("official_name", {"name": official},
                          normalized={"name": name_key(official)}, excerpt=official, locator=page_url),
            CandidateFact("aliases", {"aliases": aliases},
                          normalized={"aliases": sorted(name_key(a) for a in aliases)},
                          locator=page_url),
            # comparable key is the host only, so two sources publishing the same site in
            # different formats (http vs https, trailing slash) are not treated as a change
            CandidateFact("official_website_url", {"url": website},
                          normalized={"url": domain_of(website) or website}, excerpt=website, locator=page_url),
            CandidateFact("location", {
                "city": candidate.city, "admin_region": candidate.admin_region,
                "country_code": candidate.country_code, "country_name": candidate.country_name,
                "region": candidate.region,
                "latitude": str(candidate.latitude) if candidate.latitude is not None else None,
                "longitude": str(candidate.longitude) if candidate.longitude is not None else None,
            }, locator=page_url),
        ]
        # ROR relationships are source assertions, not merge instructions. Keep
        # valid references as a candidate fact so institution review can inspect
        # the exact parent/child/related claim and evidence before any linking.
        relationship_types = {"parent", "child", "related", "predecessor", "successor"}
        relationships = []
        for relation in item.get("relationships") or []:
            if not isinstance(relation, dict):
                continue
            identifier = clean_text(relation.get("id"))
            label = clean_text(relation.get("label"))
            kind = clean_text(relation.get("type"))
            try:
                parsed = urlsplit(identifier or "")
                host = parsed.hostname
            except ValueError:
                continue
            if (parsed.scheme != "https" or host != "ror.org"
                    or not parsed.path.strip("/") or "/" in parsed.path.strip("/")
                    or kind not in relationship_types):
                continue
            relationships.append({"ror_url": identifier, "label": label, "type": kind})
        if relationships:
            relationships.sort(key=lambda r: (r["type"], r["ror_url"], r["label"] or ""))
            candidate.facts.append(CandidateFact(
                "ror_relationships_as_reported", {"relationships": relationships},
                normalized={"relationships": relationships},
                excerpt="; ".join(f"{r['type']}: {r['label'] or r['ror_url']}" for r in relationships),
                locator=page_url))
        return candidate


def _decimal(raw) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
