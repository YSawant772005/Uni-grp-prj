"""IPEDS connectors (U.S. National Center for Education Statistics / NCES).

Access basis: the IPEDS Data Center public download files at
https://nces.ed.gov/ipeds/datacenter/data/. IPEDS is a U.S. federal statistical
programme and the data files are in the public domain; redistribution with
attribution is permitted. No login, paywall or access control is circumvented —
only the files the download centre publishes for direct download are read.

Files used
----------
``HD``  Institutional directory: official name, address, control (public /
        private not-for-profit / private for-profit), sector, Carnegie size and
        basic classification, latitude/longitude, official website, OPEID, and
        the flags for undergraduate/graduate offerings.
``IC``  Institutional characteristics / student financial: reported room and
        board rates and graduate application fee for the academic year.
``CIP`` The official CIP taxonomy page, used as discipline reference data.

The Completions file (``C``) is deliberately **not** enabled: the published
download set contains no data dictionary, so the meaning of the ``AWLEVEL``
values could not be checked against an official label file. Rather than guess
which code means "Master's degree" — which would risk creating fabricated
programmes — that source is registered with integration status
``blocked_pending_data_dictionary`` and ``enabled=false``.
"""
from __future__ import annotations

import csv
import re
import zipfile
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterator

from app.ingestion import cache
from app.ingestion.adapters.base import RunContext, SourceAdapter
from app.ingestion.http import FetchError
from app.ingestion.normalize import (
    clean_text,
    domain_of,
    ipeds_amount,
    ipeds_value,
    name_key,
    normalize_aliases,
    normalize_url,
)
from app.ingestion.types import (
    AdapterBatch,
    CandidateFact,
    CandidateField,
    CandidateInstitution,
    CandidateProgram,
    SourceDoc,
)

DATA_BASE = "https://nces.ed.gov/ipeds/datacenter/data/"
CIP_INDEX_URL = "https://nces.ed.gov/ipeds/cipcode/"
ACADEMIC_PERIOD = "2023-24"

CONTROL_TYPES = {"1": "public", "2": "non_profit", "3": "for_profit"}
SECTOR_TYPES = {"1": "public", "2": "non_profit", "3": "for_profit", "4": "public",
                "5": "public", "6": "non_profit", "7": "for_profit", "8": "public",
                "9": "non_profit", "10": "for_profit", "11": "public", "12": "public",
                "13": "non_profit", "14": "non_profit"}
OFFERINGS = {"UGOFFER": "offers_undergraduate", "GROFFER": "offers_graduate",
             "HLOFFER": "highest_level_offered"}


class _OptionCollector(HTMLParser):
    """Collects the CIP series taxonomy from the official NCES lookup page."""

    def __init__(self):
        super().__init__()
        self.options: list[tuple[str, str]] = []
        self._value: str | None = None
        self._buffer: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "option":
            self._value = dict(attrs).get("value")
            self._buffer = []

    def handle_data(self, data):
        if self._buffer is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "option" and self._buffer is not None:
            self.options.append((self._value or "", "".join(self._buffer).strip()))
            self._buffer = None


class _ZipCsvAdapter(SourceAdapter):
    """Shared download/extract helper for the IPEDS fixed-width release files."""

    file_name = ""
    csv_name = ""
    chunk_size = 500

    def iter_batches(self, ctx: RunContext) -> Iterator[AdapterBatch]:
        doc, path = self.fetch_csv(ctx)
        count = 0
        buffer: list[CandidateInstitution] = []
        for row in _read_csv(path):
            candidate = self.to_candidate(row)
            if candidate is None:
                continue
            buffer.append(candidate)
            count += 1
            if len(buffer) >= self.chunk_size:
                yield AdapterBatch(document=doc, institutions=buffer)
                buffer = []
            if ctx.max_records and count >= ctx.max_records:
                break
        if buffer:
            yield AdapterBatch(document=doc, institutions=buffer)

    def to_candidate(self, row: dict) -> CandidateInstitution | None:
        raise NotImplementedError

    def fetch_csv(self, ctx: RunContext) -> tuple[SourceDoc, Path]:
        url = DATA_BASE + self.file_name
        target = cache.cache_path(ctx, self.file_name)
        meta = cache.read_meta(ctx, self.file_name)
        if ctx.offline and target.exists():
            payload = target.read_bytes()
        else:
            result = ctx.fetcher.get(url, etag=meta.get("etag"),
                                     last_modified=meta.get("last_modified"))
            if result.not_modified and target.exists():
                payload = target.read_bytes()
            else:
                payload = result.content
                cache.store(ctx, self.file_name, payload)
                cache.write_meta(ctx, self.file_name,
                                 {"etag": result.etag, "last_modified": result.last_modified})
            meta = {"etag": result.etag, "last_modified": result.last_modified}
        return (SourceDoc(url=url, title=self.file_name, document_type="zip", content=payload,
                          http_status=200, etag=meta.get("etag"),
                          last_modified=meta.get("last_modified"),
                          academic_period=ACADEMIC_PERIOD),
                _extract_member(target, self.csv_name))


class IpedsDirectoryAdapter(_ZipCsvAdapter):
    """HD2023 — official institution directory for the United States."""

    source_key = "ipeds_hd"
    file_name = "HD2023.zip"
    csv_name = "HD2023.csv"

    def to_candidate(self, row: dict) -> CandidateInstitution | None:
        unitid = ipeds_value(row.get("UNITID"))
        name = clean_text(row.get("INSTNM"))
        if not unitid or not name:
            return None
        identifiers = {"ipeds_unitid": unitid}
        for column, key in (("OPEID", "ipeds_opeid"), ("EIN", "ipeds_ein"), ("FIPS", "ipeds_fips")):
            value = ipeds_value(row.get(column))
            if value:
                identifiers[key] = value
        city = clean_text(row.get("CITY"))
        address = ", ".join(filter(None, [clean_text(row.get("ADDR")), city,
                                          clean_text(row.get("STABBR")),
                                          ipeds_value(row.get("ZIP"))]))
        candidate = CandidateInstitution(
            external_key=f"ipeds:{unitid}",
            name=name,
            aliases=normalize_aliases([row.get("IALIAS")]),
            identifiers=identifiers,
            country_code="US",
            country_name="United States",
            region="North America",
            city=city,
            admin_region=clean_text(row.get("STABBR")),
            address=address,
            latitude=_decimal(row.get("LATITUDE")),
            longitude=_decimal(row.get("LONGITUD")),
            website=normalize_url(row.get("WEBADDR")),
            institution_type=CONTROL_TYPES.get(ipeds_value(row.get("CONTROL")) or ""),
        )
        locator = f"HD2023.csv: UNITID={unitid}"
        control = ipeds_value(row.get("CONTROL"))
        sector = ipeds_value(row.get("SECTOR"))
        offerings = {label: ipeds_value(row.get(col)) == "1"
                     for col, label in OFFERINGS.items()
                     if ipeds_value(row.get(col)) is not None}
        candidate.facts = [
            CandidateFact("official_name", {"name": name},
                          normalized={"name": name_key(name)}, locator=locator, confidence=1.0),
            CandidateFact("aliases", {"aliases": candidate.aliases},
                          normalized={"aliases": sorted(name_key(a) for a in candidate.aliases)},
                          locator=locator),
            CandidateFact("official_website_url", {"url": candidate.website},
                          normalized={"url": domain_of(candidate.website)
                                      or candidate.website}, locator=locator),
            CandidateFact("location", {
                "address": address, "city": city, "admin_region": candidate.admin_region,
                "country_code": "US",
                "latitude": str(candidate.latitude) if candidate.latitude is not None else None,
                "longitude": str(candidate.longitude) if candidate.longitude is not None else None,
            }, locator=locator),
            CandidateFact("institution_type", {"control_code": control,
                                               "type": candidate.institution_type},
                          locator=locator, confidence=1.0),
            CandidateFact("classification", {
                "sector": sector, "sector_type": SECTOR_TYPES.get(sector or ""),
                "carnegie_basic_2021": ipeds_value(row.get("C21BASIC")),
                "carnegie_size_2021": ipeds_value(row.get("C21SZSET")),
                "carnegie_basic_2018": ipeds_value(row.get("C18BASIC")),
                "carnegie_basic_2015": ipeds_value(row.get("C15BASIC")),
                "locale": ipeds_value(row.get("LOCALE")),
                "land_grant": ipeds_value(row.get("LANDGRNT")) == "1",
                "hbcu": ipeds_value(row.get("HBCU")) == "1",
                "tribal": ipeds_value(row.get("TRIBAL")) == "1",
                "religious_affiliation": ipeds_value(row.get("RELAFFIL")),
            }, locator=locator),
            CandidateFact("program_offerings", offerings, locator=locator, confidence=1.0),
        ]
        return candidate


class IpedsFinancialAdapter(_ZipCsvAdapter):
    """IC2023 — institution-reported room/board rates and graduate application fee."""

    source_key = "ipeds_ic"
    file_name = "IC2023.zip"
    csv_name = "IC2023.csv"

    def to_candidate(self, row: dict) -> CandidateInstitution | None:
        unitid = ipeds_value(row.get("UNITID"))
        if not unitid:
            return None
        reported = {}
        for key, column in (("room_rate", "ROOMAMT"), ("board_rate", "BOARDAMT"),
                            ("room_and_board_rate", "RMBDAMT"),
                            ("graduate_application_fee", "APPLFEEG")):
            amount = ipeds_amount(row.get(column))
            if amount is not None:
                reported[key] = str(amount)
        if not reported:
            return None  # institution reported nothing for this item: stays unknown, never 0
        candidate = CandidateInstitution(
            external_key=f"ipeds:{unitid}", name=f"IPEDS UNITID {unitid}",
            identifiers={"ipeds_unitid": unitid}, country_code="US",
            require_existing=True)
        candidate.facts = [CandidateFact(
            "institutional_costs", {**reported, "currency": "USD",
                                    "academic_period": ACADEMIC_PERIOD,
                                    "student_category": "institution-wide reported rate"},
            normalized=reported, applicability_key=ACADEMIC_PERIOD,
            locator=f"IC2023.csv: UNITID={unitid}", confidence=1.0)]
        return candidate


class NcesCipAdapter(SourceAdapter):
    """Official NCES CIP taxonomy, used as discipline reference data."""

    source_key = "nces_cip"

    def iter_batches(self, ctx: RunContext) -> Iterator[AdapterBatch]:
        result = ctx.fetcher.get(CIP_INDEX_URL)
        parser = _OptionCollector()
        parser.feed(result.text())
        fields, seen = [], set()
        for _value, label in parser.options:
            match = re.match(r"^(\d{2})\)\s*(.+?)\.?$", label)
            if not match:
                continue
            series, title = match.group(1), match.group(2).strip()
            if series in seen:
                continue
            seen.add(series)
            fields.append(CandidateField(
                key=f"cip_{series}", display_name=_title_case(title),
                description=f"NCES CIP taxonomy series {series} (codes {series}.xxxx)."))
        yield AdapterBatch(
            document=SourceDoc(url=CIP_INDEX_URL, title="NCES CIP code lookup",
                               document_type="html", content=result.content,
                               http_status=result.status, etag=result.etag,
                               last_modified=result.last_modified),
            fields=fields, warnings=[] if fields else ["no CIP series could be parsed"])


class IpedsCompletionsAdapter(_ZipCsvAdapter):
    """C2023_A — awards conferred by CIP code and award level.

    **Blocked by design.** IPEDS award levels are identified by the numeric
    ``AWLEVEL`` column. The published download set (including the ``*_RV``
    variant) contains no data dictionary or label file, so this adapter refuses
    to emit a single programme record until an operator supplies the official
    AWLEVEL label mapping (``{code: (degree_level, official_label)}``) in its
    constructor. Guessing the mapping would fabricate programme records, which
    the project rules forbid, so the source ships disabled.
    """

    source_key = "ipeds_completions"
    file_name = "C2023_A.zip"
    csv_name = "C2023_a.csv"

    def __init__(self, awlevel_map: dict[str, tuple[str, str]] | None = None,
                 cip_series: dict[str, str] | None = None):
        self.awlevel_map = awlevel_map or {}
        self.cip_series = cip_series or {}

    def to_candidate(self, row: dict) -> CandidateInstitution | None:
        if not self.awlevel_map:
            return None
        unitid = ipeds_value(row.get("UNITID"))
        cip = ipeds_value(row.get("CIPCODE"))
        awlevel = ipeds_value(row.get("AWLEVEL"))
        awards = ipeds_amount(row.get("CTOTALT"))
        if not (unitid and cip and awlevel) or awlevel not in self.awlevel_map or not awards:
            return None
        degree_level, label = self.awlevel_map[awlevel]
        series = cip.split(".")[0]
        candidate = CandidateInstitution(
            external_key=f"ipeds:{unitid}", name=f"IPEDS UNITID {unitid}",
            identifiers={"ipeds_unitid": unitid}, country_code="US")
        program = CandidateProgram(
            external_key=f"ipeds:{unitid}:{awlevel}:{cip}",
            title=f"{label} — {self.cip_series.get(series, 'CIP ' + series)} (CIP {cip})",
            degree_level=degree_level, discipline_code=cip,
            discipline_name=self.cip_series.get(series))
        program.facts = [CandidateFact(
            "awards_conferred", {"count": str(awards), "award_level_code": awlevel,
                                  "award_level_label": label, "cip_code": cip,
                                  "academic_period": ACADEMIC_PERIOD},
            normalized={"count": str(awards)}, applicability_key=ACADEMIC_PERIOD,
            locator=f"{self.csv_name}: UNITID={unitid}, CIPCODE={cip}, AWLEVEL={awlevel}",
            confidence=1.0)]
        candidate.programs.append(program)
        return candidate

    def iter_batches(self, ctx: RunContext):
        if not self.awlevel_map:
            logger.warning("%s is disabled: no official AWLEVEL label mapping configured",
                           self.source_key)
            return
        yield from super().iter_batches(ctx)


# --------------------------------------------------------------------- helpers

def _title_case(text: str) -> str:
    small = {"and", "or", "of", "the", "in", "for", "to", "with", "other"}
    words = text.lower().split()
    return " ".join(w if i and w in small else w.capitalize() for i, w in enumerate(words))


def _decimal(raw) -> Decimal | None:
    value = ipeds_value(raw)
    if value is None:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def _read_csv(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def _extract_member(zip_path: Path, member: str) -> Path:
    extracted = zip_path.with_suffix(".member")
    if not extracted.exists() or extracted.stat().st_mtime < zip_path.stat().st_mtime:
        with zipfile.ZipFile(zip_path) as archive:
            names = [n for n in archive.namelist() if n.lower() == member.lower()]
            if not names:
                names = [n for n in archive.namelist() if n.lower().endswith(member.lower())]
            if not names:
                raise KeyError(f"{member} not present in {zip_path.name}")
            with archive.open(names[0]) as src, extracted.open("wb") as dst:
                dst.write(src.read())
    return extracted