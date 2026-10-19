"""Deterministic validation rules for candidates before anything is persisted.

Validation is rule-based and reproducible: no model output, no heuristics that
invent values. Rejections carry a machine-readable code and are recorded on the
ingestion job item so an operator can see exactly why a record was refused.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from app.ingestion.normalize import clean_text, domain_of, normalize_url
from app.ingestion.types import CandidateFact, CandidateInstitution, CandidateProgram

DEGREE_LEVELS = {"bachelors", "masters", "phd", "diploma", "certificate", "other"}
STUDY_MODES = {"full_time", "part_time", "online", "blended", "unknown"}
INSTITUTION_TYPES = {"public", "private", "non_profit", "for_profit", "unknown"}
MAX_TITLE = 250


@dataclass(frozen=True)
class Issue:
    field: str
    code: str
    message: str

    def as_dict(self) -> dict:
        return {"field": self.field, "code": self.code, "message": self.message}


def _is_real_url(url: object) -> bool:
    return normalize_url(url) is not None


def validate_institution(candidate: CandidateInstitution) -> list[Issue]:
    issues: list[Issue] = []
    name = clean_text(candidate.name)
    if not name:
        issues.append(Issue("name", "required", "Official institution name is missing."))
    elif len(name) > MAX_TITLE:
        issues.append(Issue("name", "too_long", f"Institution name exceeds {MAX_TITLE} characters."))
    if not candidate.external_key:
        issues.append(Issue("external_key", "required", "No stable source identifier for the institution."))
    code = candidate.country_code
    if not code:
        issues.append(Issue("country_code", "required", "Country is unknown; refusing to guess it."))
    elif len(code) != 2 or not code.isalpha() or not code.isupper():
        issues.append(Issue("country_code", "invalid", f"Country code {code!r} is not ISO alpha-2."))
    if not candidate.identifiers and not candidate.website:
        issues.append(Issue("identifiers", "insufficient",
                            "No external identifier and no official website: record would be unresolvable."))
    for key, value in candidate.identifiers.items():
        if not clean_text(key) or not clean_text(value):
            issues.append(Issue("identifiers", "invalid", f"Identifier {key!r} has no usable value."))
    if candidate.website and not _is_real_url(candidate.website):
        issues.append(Issue("website", "invalid_url", f"Official website {candidate.website!r} is not a usable URL."))
    if candidate.institution_type and candidate.institution_type not in INSTITUTION_TYPES:
        issues.append(Issue("institution_type", "invalid",
                            f"Institution type {candidate.institution_type!r} is not a known value."))
    if candidate.latitude is not None and not Decimal(-90) <= candidate.latitude <= Decimal(90):
        issues.append(Issue("latitude", "out_of_range", "Latitude is outside [-90, 90]."))
    if candidate.longitude is not None and not Decimal(-180) <= candidate.longitude <= Decimal(180):
        issues.append(Issue("longitude", "out_of_range", "Longitude is outside [-180, 180]."))
    issues.extend(validate_facts(candidate.facts))
    return issues


def validate_program(program: CandidateProgram) -> list[Issue]:
    issues: list[Issue] = []
    title = clean_text(program.title)
    if not title:
        issues.append(Issue("title", "required", "Program title is missing."))
    elif len(title) > MAX_TITLE:
        issues.append(Issue("title", "too_long", f"Program title exceeds {MAX_TITLE} characters."))
    if not program.external_key:
        issues.append(Issue("external_key", "required", "No stable source identifier for the program."))
    if program.degree_level not in DEGREE_LEVELS:
        issues.append(Issue("degree_level", "invalid",
                            f"Degree level {program.degree_level!r} is not a known value."))
    if program.study_mode and program.study_mode not in STUDY_MODES:
        issues.append(Issue("study_mode", "invalid", f"Study mode {program.study_mode!r} is unknown."))
    if program.official_url and not _is_real_url(program.official_url):
        issues.append(Issue("official_url", "invalid_url",
                            f"Program URL {program.official_url!r} is not a usable URL."))
    low, high = program.duration_min_months, program.duration_max_months
    if low is not None and low <= 0 or high is not None and high <= 0:
        issues.append(Issue("duration", "out_of_range", "Program duration must be a positive number of months."))
    if low is not None and high is not None and low > high:
        issues.append(Issue("duration", "inconsistent", "Minimum duration exceeds maximum duration."))
    if program.discipline_code and not program.discipline_code.replace(".", "").isdigit():
        issues.append(Issue("discipline_code", "invalid",
                            f"Discipline code {program.discipline_code!r} is not a numeric taxonomy code."))
    issues.extend(validate_facts(program.facts))
    return issues


def validate_facts(facts: Iterable[CandidateFact]) -> list[Issue]:
    issues: list[Issue] = []
    for fact in facts:
        if not fact.fact_key or len(fact.fact_key) > 80:
            issues.append(Issue("fact_key", "invalid", "Fact key is missing or too long."))
        if not isinstance(fact.value, dict):
            issues.append(Issue("value", "invalid", "Fact value must be a JSON object."))
        if fact.confidence is not None and not 0 <= fact.confidence <= 1:
            issues.append(Issue("confidence", "out_of_range",
                                "Extraction confidence must be within [0, 1]."))
    return issues


def institution_match_quality(candidate: CandidateInstitution,
                              resolved_by: str | None) -> list[Issue]:
    """Low-confidence identity merges are surfaced for review, never silently kept."""
    if resolved_by in ("external_id", None):
        return []
    return [Issue("identity", "weak_match",
                  f"Institution matched to an existing record only via {resolved_by!r}; "
                  "please confirm it is the same institution.")]


def same_website(candidate_url: str | None, stored_url: str | None) -> bool:
    return bool(candidate_url and stored_url and domain_of(candidate_url) == domain_of(stored_url))
