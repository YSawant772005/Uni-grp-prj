"""Deterministic text/value extraction for permitted web documents.

Supports plain HTML, PDF (via the optional ``pypdf`` dependency) and structured
JSON/CSV. Extraction is rule-based: a value is only returned when it can be
located next to the label that the source actually published, and the matched
passage is returned so it can be stored as evidence with a locator.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any

logger = logging.getLogger("uni.ingestion")

SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}
BLOCK_TAGS = {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6",
              "section", "article", "table", "ul", "ol", "dt", "dd", "td", "th"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip += 1
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip:
            self._skip -= 1
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        joined = "".join(self.parts)
        lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in joined.split("\n")]
        return "\n".join(line for line in lines if line)


def html_to_text(markup: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(markup)
        parser.close()
    except Exception as exc:  # malformed HTML must not abort the run
        logger.warning("html parse stopped early: %s", exc)
    return parser.text()


def pdf_to_text(data: bytes) -> str | None:
    try:
        from pypdf import PdfReader
    except ImportError:  # optional dependency
        logger.warning("pypdf is not installed; PDF sources cannot be parsed")
        return None
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages[:200])
    except Exception as exc:
        logger.warning("pdf parse failed: %s", exc)
        return None


def json_to_dict(data: bytes) -> Any:
    try:
        return json.loads(data.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning("json parse failed: %s", exc)
        return None


def csv_to_dicts(data: bytes) -> list[dict]:
    try:
        text = data.decode("utf-8-sig", errors="replace")
    except UnicodeDecodeError:
        return []
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    return [row for row in reader]


def json_path(payload: Any, path: str) -> Any:
    """Resolve a dotted path, tolerating list indices. Returns None when absent."""
    current = payload
    for part in path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
                continue
            except (ValueError, IndexError):
                return None
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return None
    return current


_NUMBER = r"[-+]?[$€£¥₹]?\s?\d[\d,\s]*(?:\.\d+)?"

_VALUE_PATTERNS: dict[str, re.Pattern] = {
    "text": re.compile(rf"(?P<value>[^\n]{{1,200}})"),
    "amount": re.compile(rf"(?P<value>{_NUMBER})"),
    "integer": re.compile(r"(?P<value>\d+)"),
    "months": re.compile(r"(?P<value>\d{1,2}(?:\.\d)?)\s*(?P<unit>months?|semesters?|years?)", re.I),
    "date": re.compile(r"(?P<value>\d{1,2}[/. -]\d{1,2}[/. -]\d{2,4}|\d{4}-\d{2}-\d{2})"),
    "url": re.compile(r"(?P<value>https?://[^\s\"'<>]+)"),
    "boolean": re.compile(r"(?P<value>yes|no|true|false|full[- ]time|part[- ]time)", re.I),
    "percent": re.compile(r"(?P<value>\d{1,3}(?:\.\d+)?)\s*(?P<unit>%|percent)"),
}


def find_labelled_value(text: str, label: str, kind: str = "text",
                        *, max_chars: int = 400) -> tuple[str, str] | None:
    """Return ``(value, passage)`` when ``label`` is followed by a matching value."""
    pattern = _VALUE_PATTERNS.get(kind, _VALUE_PATTERNS["text"])
    escaped = re.escape(label.strip())
    label_re = re.compile(
        rf"^[^\n]{{0,120}}{escaped}[^\n]{{0,120}}?[:\u2013\u2014-]?\s*", re.I | re.M)
    for line in text.split("\n"):
        if not label_re.match(line):
            continue
        match = pattern.search(line[label_re.match(line).end():])
        if match:
            value = match.group("value").strip(" \t:,;-")
            if not value:
                continue
            passage = line[:max_chars]
            if match.lastindex and match.groupdict().get("unit"):
                value = f"{value} {match.group('unit')}"
            return value, passage
    return None


def parse_amount(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(re.sub(r"[^0-9.\-]", "", value))
    except (InvalidOperation, ValueError):
        return None