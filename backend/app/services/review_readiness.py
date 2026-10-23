"""Evidence criteria shared by institution review and program publication.

Readiness is derived from stored evidence. It never changes a reviewer decision.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timezone

from app.ingestion.registry import FETCHABLE_POLICIES

USABLE_FACT_STATUSES = {"candidate", "unverified", "verified"}


def title_key(value: str | None) -> str:
    return " ".join(unicodedata.normalize("NFKC", value or "").casefold().split())


def supporting_evidence(evidence: dict) -> bool:
    return (
        evidence.get("allowed_use_policy") in FETCHABLE_POLICIES
        and evidence.get("fetch_status") in {"fetched", "not_modified"}
        and (evidence.get("http_status") is None or 200 <= evidence["http_status"] < 300
             or evidence["http_status"] == 304)
        and evidence.get("supports_or_conflicts", "supports") == "supports"
        and bool(evidence.get("excerpt")) and bool(evidence.get("locator"))
    )


def program_package(program: dict, *, today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    blockers, warnings = [], []
    facts = program["program_facts"]
    identities = program["source_identities"]
    usable = [fact for fact in facts if fact["status"] in USABLE_FACT_STATUSES]
    if program["degree_level"] != "masters":
        blockers.append("The record is not classified as a Master's qualification.")
    if not program.get("is_active", True):
        blockers.append("This offering is inactive.")
    permitted = [identity for identity in identities
                 if identity["claim_status"] == "accepted"
                 and identity.get("institution_linked")
                 and identity.get("source_binding_valid")
                 and identity["allowed_use_policy"] in FETCHABLE_POLICIES
                 and identity["source_document"]
                 and supporting_evidence({**identity["source_document"],
                     "allowed_use_policy": identity["allowed_use_policy"],
                     "excerpt": "identifier", "locator": "identifier"})]
    if not permitted:
        blockers.append("An accepted program identity with a permitted source and institution link is required.")
    titles = [fact for fact in usable if fact["fact_key"] == "program_title_as_reported"
              and title_key((fact.get("value") or {}).get("title")) == title_key(program["title"])]
    matched = [evidence for fact in titles for evidence in fact["evidence"]
               if supporting_evidence(evidence) and any(
                   evidence["source_document_id"] == identity["source_document"]["id"]
                   and evidence.get("source_id") == identity.get("source_id")
                   for identity in permitted)]
    if not matched:
        blockers.append("The named program needs matching title and supporting row evidence from its identity document.")
    periods = {str(e["academic_period"]) for e in matched if e.get("academic_period")}
    for fact in usable:
        if fact["fact_key"] == "academic_campaign":
            periods.add(str((fact.get("value") or {}).get("session") or ""))
        if fact["fact_key"] == "offering_validity_period":
            end = (fact.get("value") or {}).get("valid_to")
            if end and end < today.isoformat():
                blockers.append("The source offering validity period has ended.")
    historical = any((years := re.findall(r"\b(?:19|20)\d{2}\b", period))
                     and max(map(int, years)) < today.year for period in periods)
    if historical:
        blockers.append("Only a historical academic campaign is evidenced; current availability is unestablished.")
    if not periods:
        warnings.append("Academic year/campaign is not supplied; assess the source's current-offering scope.")
    checked = [e.get("last_checked_at") or e.get("retrieved_at") for e in matched]
    if checked and all((datetime.now(timezone.utc) - datetime.fromisoformat(value)).days > 180
                       for value in checked if value):
        blockers.append("Program evidence has not been checked within 180 days; refresh before approval.")
    return {"eligible": not blockers, "blockers": blockers, "warnings": warnings,
            "academic_periods": sorted(filter(None, periods)),
            "applicability": "historical" if historical else ("source_period" if periods else "unspecified")}


def discovery_stage(eligibility: dict, coverage: dict, context: dict, claims: list) -> str:
    if eligibility["eligible"]:
        return "ready_for_review"
    if coverage["program_count"] == 0:
        return "discovery"
    if coverage["evidence_backed_program_count"] == 0:
        return "program_evidence_needed"
    if context["website_evidence_status"] != "verified":
        return "website_evidence_needed"
    return "institution_evidence_needed"


def program_semantics(program: dict) -> dict:
    """Expose qualification/pathway/offering layers without merging shared titles."""
    facts = {fact["fact_key"]: fact.get("value") or {} for fact in program["program_facts"]
             if fact["status"] in USABLE_FACT_STATUSES}
    rio = facts.get("rio_program_identity", {})
    return {
        "record_scope": "source_program_offering",
        "qualification": {"level": program["degree_level"],
                          "mention": facts.get("academic_mention_as_reported", {}).get("mention"),
                          "source_identifier": facts.get("master_mention_identifier", {}).get("identifier")
                              or rio.get("recognized_program_code")},
        "pathway": {"name": facts.get("pathway_as_reported", {}).get("pathway"),
                    "source_identifier": facts.get("master_track_identifier", {}).get("identifier")},
        "study_stage": facts.get("study_stage_as_reported", {}).get("stage"),
        "location_as_reported": facts.get("study_location_as_reported") or facts.get("program_locations_as_reported"),
        "awarding_institutions": None,
        "relationship_note": "The linked institution owns the source offering. Awarding, joint and consortium roles require separate evidence.",
    }
