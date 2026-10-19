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
TYPE_FILTER = "types:education"


class RorAdapter(SourceAdapter):
    source_key = "ror"

    def iter_batches(self, ctx: RunContext) -> Iterator[AdapterBatch]:
        emitted = 0
        for page in range(1, ctx.max_pages + 1):
            url = f"{API}?filter={TYPE_FILTER}&page={page}"
            try:
                result = ctx.fetcher.get(url)
            except FetchError as exc:
                if exc.status in (400, 404) or exc.permanent:
                    return  # end of the filtered result set, or a permanent refusal
                raise
            payload = json.loads(result.text())
            items = payload.get("items") or []
            if not items:
                return
            institutions = [self._to_institution(item, page) for item in items]
            institutions = [i for i in institutions if i is not None]
            if ctx.countries:
                wanted = {c.upper() for c in ctx.countries}
                institutions = [i for i in institutions if (i.country_code or "") in wanted]
            remaining = None if ctx.max_records is None else ctx.max_records - emitted
            if remaining is not None:
                if remaining <= 0:
                    return
                institutions = institutions[:remaining]
            from app.ingestion.types import SourceDoc
            doc = SourceDoc(url=url, title=f"ROR organizations (education) page {page}",
                            document_type="json", content=result.content,
                            http_status=result.status, etag=result.etag,
                            last_modified=result.last_modified)
            yield AdapterBatch(document=doc, institutions=institutions)
            emitted += len(institutions)
            if len(items) < 20:
                return

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
                          normalized={"name": name_key(official)}, locator=page_url),
            CandidateFact("aliases", {"aliases": aliases},
                          normalized={"aliases": sorted(name_key(a) for a in aliases)},
                          locator=page_url),
            # comparable key is the host only, so two sources publishing the same site in
            # different formats (http vs https, trailing slash) are not treated as a change
            CandidateFact("official_website_url", {"url": website},
                          normalized={"url": domain_of(website) or website}, locator=page_url),
            CandidateFact("location", {
                "city": candidate.city, "admin_region": candidate.admin_region,
                "country_code": candidate.country_code, "country_name": candidate.country_name,
                "region": candidate.region,
                "latitude": str(candidate.latitude) if candidate.latitude is not None else None,
                "longitude": str(candidate.longitude) if candidate.longitude is not None else None,
            }, locator=page_url),
        ]
        return candidate


def _decimal(raw) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None