"""Deterministic normalization helpers (no guessing, no invented values).

Every function either returns a faithful normalized form of what the source
supplied or ``None``. A missing value never becomes 0/""/"unknown value".
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit

MISSING_TOKENS = {"", ".", "-", "--", "n/a", "na", "none", "null", "not available",
                  "not applicable", "no data", "unknown", "undefined"}
# IPEDS sentinel codes meaning "not applicable"/"not collected"/"suppressed"
IPEDS_MISSING = {"-1", "-2", "-3", "-4", "-5", "-6", "-7", "-9", "-99"}
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                   "utm_content", "gclid", "fbclid", "_ga"}

_DEGREE_PATTERNS = [
    (r"\b(?:masters?|msc|m\.?sc|mba|ma|ms|m\.?s|mas|mmgt|meng|mres)\b", "masters"),
    (r"\bdoctor|phd|ph\.d\b|dphil|dba|m\.?ph\b", "phd"),
    (r"\bbachelor|bsc|b\.?sc\b|ba\b|bs\b|b\.?s\b|llb|be\b", "bachelors"),
]


def clean_text(value: object) -> str | None:
    """Collapse whitespace; return None when the source supplied nothing."""
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return None if text.lower() in MISSING_TOKENS else text


def program_title_matches(expected: str, observed: str) -> bool:
    """Conservative title words, including UAL's explicit Spanish ELE abbreviation.

    No translation or approximate subject similarity is inferred. A bilingual
    page must actually supply a matching title in either language.
    """
    def terms(value):
        text = ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                       if not unicodedata.combining(c))
        text = re.sub(r'\bele\b', 'espanol lengua extranjera', text)
        ignored = {'master', 'masters', 'universitario', 'universitaria', 'en', 'de', 'del',
                   'la', 'las', 'el', 'los', 'y', 'para', 'como', 'sobre', 'of', 'in', 'the',
                   'degree', 'universidad', 'university', 'almeria'}
        return {word[:-1] if word.endswith('s') else word
                for word in re.findall(r'[a-z0-9]+', text) if len(word) > 2 and word not in ignored}
    wanted, actual = terms(expected), terms(observed)
    return bool(wanted) and wanted <= actual


def ipeds_value(raw: object) -> str | None:
    """IPEDS encodes 'not applicable'/suppressed cells with sentinels and dots."""
    if raw is None:
        return None
    text = re.sub(r"\s+", " ", str(raw)).strip()
    if not text or text.lower() in MISSING_TOKENS or text in IPEDS_MISSING:
        return None
    return text


def ipeds_number(raw: object) -> int | None:
    text = ipeds_value(raw)
    if text is None:
        return None
    try:
        return int(float(text.replace(",", "")))
    except ValueError:
        return None


def ipeds_amount(raw: object) -> Decimal | None:
    """Money from a survey cell. Returns None rather than 0 for absent values."""
    text = ipeds_value(raw)
    if text is None:
        return None
    try:
        return Decimal(text.replace(",", "").replace("$", "").strip())
    except (InvalidOperation, ValueError):
        return None


def name_key(value: str) -> str:
    """Aggressive key for entity matching: case/punctuation insensitive."""
    text = (value or "").lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [w for w in text.split() if w]
    return " ".join(words)


def normalize_url(value: object) -> str | None:
    """Absolute http(s) URL with a normalized host; None when not usable."""
    text = clean_text(value)
    if not text:
        return None
    scheme = re.match(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):", text)
    if scheme and scheme.group(1).lower() not in ("http", "https"):
        return None  # javascript:, data:, file: and friends are never usable sources
    if "://" not in text:
        text = "https://" + text
    try:
        parts = urlsplit(text)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    host = parts.netloc.lower().split("@")[-1]
    if host.startswith("www."):
        host = host[4:]
    if (parts.scheme == "http" and host.endswith(":80")) or (
            parts.scheme == "https" and host.endswith(":443")):
        host = host.rsplit(":", 1)[0]
    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/")
    query = "&".join(
        p for p in parts.query.split("&")
        if p and p.split("=", 1)[0].lower() not in TRACKING_PARAMS)
    return urlunsplit((parts.scheme, host, path, query, ""))


def domain_of(url: object) -> str | None:
    """Host of a normalized URL (no scheme, no ``www.``).

    The full host is kept rather than the registrable domain: collapsing to the
    last two labels would make ``a.example.org`` and ``b.example.org`` look like
    the same institution and silently merge unrelated universities.
    """
    normalized = normalize_url(url)
    return urlsplit(normalized).netloc if normalized else None


def title_case_key(value: str) -> str:
    return name_key(value)


def normalize_degree_level(value: object) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    low = text.lower()
    for pattern, level in _DEGREE_PATTERNS:
        if re.search(pattern, low):
            return level
    return None


def normalize_currency(value: object) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    code = re.sub(r"[^A-Za-z]", "", text).upper()
    return code if len(code) == 3 else None


def normalize_academic_period(value: object) -> str | None:
    """e.g. '2023-24', '2023/2024' -> '2023-24'."""
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"(20\d{2})\s*[-/]\s*(\d{2,4})", text)
    if not match:
        return None
    start = match.group(1)
    tail = match.group(2)
    end = tail[:2] if len(tail) == 2 else tail[:4]
    return f"{start}-{end[-2:] if len(end) > 2 else end}"


def parse_date(value: object) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    match = re.search(r"(20\d{2})-(\d{2})-(\d{2})", text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def normalize_aliases(values: object) -> list[str]:
    """De-duplicate alias lists without discarding any distinct source string."""
    if not values:
        return []
    items = values if isinstance(values, (list, tuple, set)) else [values]
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = clean_text(item)
        if not text:
            continue
        key = name_key(text)
        if key in seen:
            continue
        seen.add(key)
        out.append(text[:250])
    return out


def stable_json(value: object) -> str:
    import json
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
