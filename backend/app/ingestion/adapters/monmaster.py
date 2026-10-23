"""Official French Mon Master 2025 open-data catalogue snapshot.

The API contains application statistics alongside the public programme identity
fields. Requests select only catalogue fields; evidence excerpts are similarly
allowlisted. These are historical source candidates and are never auto-published.
"""
from __future__ import annotations

import json
import re
from typing import Iterator
from urllib.parse import urlencode

from app.ingestion.adapters.base import RunContext, SourceAdapter
from app.ingestion.types import (
    AdapterBatch,
    CandidateFact,
    CandidateField,
    CandidateInstitution,
    CandidateProgram,
    SourceDoc,
)
from app.ingestion.normalize import clean_text

API = "https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1/catalog/datasets/fr-esr-mon_master/records"
DATASET = "https://data.enseignementsup-recherche.gouv.fr/explore/dataset/fr-esr-mon_master/"
LICENSE = "https://www.etalab.gouv.fr/licence-ouverte-open-licence/"
SESSION = "2025"
PAGE_SIZE = 100
SELECT = (
    "session,eta_uai,eta_nom,ifc,inm,inmp,mention,parcours,discipline,disci_lib,"
    "secteur_disci_lib,modalite_enseignement,alternance,lieux"
)
UAI_PATTERN = re.compile(r"^[0-9]{7}[A-Z]$")


class MonMasterAdapter(SourceAdapter):
    source_key = "fr_monmaster"

    def iter_batches(self, ctx: RunContext) -> Iterator[AdapterBatch]:
        if ctx.max_records is None:
            raise ValueError("Mon Master retrieval requires an explicit bounded --limit.")
        if ctx.max_records <= 0:
            return
        if ctx.max_records > 10_000:
            raise ValueError('Mon Master --limit cannot exceed 10000 records per run.')

        if ctx.query and not UAI_PATTERN.fullmatch(ctx.query):
            raise ValueError("Mon Master --query must be an exact UAI reporting-unit identifier.")
        offset = 0
        emitted = 0
        seen: set[str] = set()
        while emitted < ctx.max_records and offset < PAGE_SIZE * ctx.max_pages:
            limit = min(PAGE_SIZE, ctx.max_records - emitted)
            params = {
                "where": f'session="{SESSION}"' + (f' AND eta_uai="{ctx.query}"' if ctx.query else ""),
                "order_by": "ifc",
                "limit": limit,
                "offset": offset,
                "select": SELECT,
            }
            url = f"{API}?{urlencode(params)}"
            result = ctx.fetcher.get(url)
            payload = json.loads(result.text())
            rows = payload.get("results")
            if not isinstance(rows, list):
                raise ValueError("Mon Master API response is missing its results list.")
            if not rows:
                return

            institutions: dict[str, CandidateInstitution] = {}
            fields = {}
            safe_rows = []
            warnings = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if str(row.get('session')) != SESSION:
                    warnings.append('row held: academic campaign does not match the requested 2025 snapshot')
                    continue
                if re.search(r'(?:double\s+dipl[oô]me|joint\s+degree|co[- ]?dipl[oô]m)',
                             str(row.get('parcours') or ''), re.I):
                    warnings.append('joint/double award pathway held for relationship review')
                    continue
                uai = clean_text(row.get("eta_uai"))
                institution_name = clean_text(row.get("eta_nom"))
                ifc = clean_text(row.get("ifc"))
                mention = clean_text(row.get("mention"))
                if not uai or not UAI_PATTERN.fullmatch(uai) or not institution_name or not ifc or not mention:
                    continue
                if ifc in seen:
                    continue
                seen.add(ifc)
                title = _program_title(mention, row.get("parcours"))
                locator = f"results[ifc={ifc}]"
                excerpt_values = {
                    "session": clean_text(row.get("session")),
                    "eta_uai": uai,
                    "eta_nom": institution_name,
                    "ifc": ifc,
                    "inm": clean_text(row.get("inm")),
                    "inmp": clean_text(row.get("inmp")),
                    "mention": mention,
                    "parcours": clean_text(row.get("parcours")),
                    "discipline": clean_text(row.get("disci_lib")),
                    "sector": clean_text(row.get("secteur_disci_lib")),
                    "delivery_modes": _string_list(row.get("modalite_enseignement")),
                    "locations": clean_text(row.get("lieux")),
                }
                safe_rows.append(excerpt_values)

                pathway = excerpt_values["parcours"]
                discipline_code = clean_text(row.get("discipline"))
                field_key = (f"fr_sies_discipline_{discipline_code}"
                             if discipline_code and discipline_code.isdigit() and excerpt_values["discipline"] else None)
                if field_key:
                    fields[field_key] = CandidateField(field_key, excerpt_values["discipline"],
                        "French SIES source discipline; no cross-taxonomy equivalence is inferred.")
                facts = [CandidateFact(
                    "program_title_as_reported", {"title": title},
                    applicability_key=f"session:{SESSION}", excerpt=title, locator=locator),
                    CandidateFact(
                    "academic_mention_as_reported", {"mention": mention},
                    applicability_key=f"session:{SESSION}", excerpt=mention, locator=locator),
                    CandidateFact(
                    "academic_campaign", {"session": SESSION},
                    applicability_key=f"session:{SESSION}", excerpt=f"Mon Master campaign {SESSION}",
                    locator=locator)]
                if pathway:
                    facts.append(CandidateFact(
                        "pathway_as_reported", {"pathway": pathway},
                        applicability_key=f"session:{SESSION}", excerpt=pathway,
                        locator=locator))
                for key, fact_key in (("inm", "master_mention_identifier"),
                                      ("inmp", "master_track_identifier")):
                    if excerpt_values[key]:
                        facts.append(CandidateFact(
                            fact_key, {"identifier": excerpt_values[key]},
                            applicability_key=f"session:{SESSION}",
                            excerpt=f"{fact_key}: {excerpt_values[key]}", locator=locator))
                if excerpt_values["discipline"] or excerpt_values["sector"]:
                    facts.append(CandidateFact(
                        "discipline_area", {"name": excerpt_values["discipline"],
                                             "sector": excerpt_values["sector"]},
                        applicability_key=f"session:{SESSION}",
                        excerpt=f"{excerpt_values['discipline'] or ''} / {excerpt_values['sector'] or ''}".strip(" /"),
                        locator=locator))
                if excerpt_values["delivery_modes"]:
                    facts.append(CandidateFact(
                        "delivery_modes_as_reported", {"labels": excerpt_values["delivery_modes"]},
                        applicability_key=f"session:{SESSION}",
                        excerpt=", ".join(excerpt_values["delivery_modes"]), locator=locator))
                if excerpt_values["locations"]:
                    facts.append(CandidateFact(
                        "program_locations_as_reported", {"locations": excerpt_values["locations"]},
                        applicability_key=f"session:{SESSION}",
                        excerpt=excerpt_values["locations"], locator=locator))

                candidate = institutions.get(uai)
                if candidate is None:
                    candidate = CandidateInstitution(
                        external_key=f"fr-monmaster:uai:{uai}", name=institution_name,
                        country_code="FR", country_name="France",
                        identifiers={"uai": uai}, identifier_scopes={"uai": "reporting_unit"})
                    candidate.facts.append(CandidateFact(
                        "official_name", {"name": institution_name},
                        normalized={"name": institution_name.casefold()},
                        excerpt=institution_name, locator=locator))
                    institutions[uai] = candidate
                candidate.programs.append(CandidateProgram(
                    external_key=f"fr-monmaster:ifc:{ifc}", title=title,
                    degree_level="masters", discipline_name=excerpt_values["sector"] or excerpt_values["discipline"],
                    discipline_key=field_key,
                    # No individual programme URL is supplied by this statistical snapshot.
                    # Publication therefore remains blocked until reviewed official evidence exists.
                    official_url=None, facts=facts))
                emitted += 1
                if emitted >= ctx.max_records:
                    break

            if not safe_rows and not warnings:
                raise ValueError("Mon Master page contained no records with valid programme identities.")
            safe_excerpt = json.dumps(safe_rows[:3], ensure_ascii=False, separators=(",", ":"))
            yield AdapterBatch(
                document=SourceDoc(
                    url=url, title=f"Mon Master programme catalogue, campaign {SESSION}",
                    document_type="json", content=result.content, content_excerpt=safe_excerpt,
                    http_status=result.status, etag=result.etag,
                    last_modified=result.last_modified, academic_period=SESSION,
                    retrieval_attempt_count=getattr(result, "attempts", 1)),
                institutions=list(institutions.values()), fields=list(fields.values()),
                warnings=warnings, skipped_records=len(warnings))
            offset += len(rows)
            if len(rows) < limit:
                return


def _program_title(mention: str, parcours_raw: object) -> str:
    parcours = clean_text(parcours_raw)
    return mention if not parcours or parcours.casefold() == mention.casefold() else f"{mention} — {parcours}"


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [item for raw in value if (item := clean_text(raw))]
    if (text := clean_text(value)):
        return [part.strip() for part in text.split(",") if part.strip()]
    return []
