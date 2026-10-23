"""Source review and academic coverage are separate, read-only projections.

Legacy data_quality is intentionally unchanged. A populated relational value is
available, but is verified here only when a current reviewed fact supports it.
"""
from decimal import Decimal, InvalidOperation

from app.services.program_evidence import official_program_page
from app.services.review_readiness import supporting_evidence


def source_verification(program, university, ctx):
    page = official_program_page(None, program, context=ctx, university=university)
    demo = bool((university.external_identifiers or {}).get("demo_fixture"))
    identity = any(key[0] == program.id for key in ctx["accepted_program_keys"])
    status = ("demo_fixture" if demo else "verified" if page["status"] == "verified"
              else "candidate" if page["status"] == "unverified_candidate" else "unavailable")
    entry = ctx["program_facts"].get(program.id, {}).get(page.get("fact_id"))
    return {"official_program_page_status": status,
            "program_identity_status": "demo_fixture" if demo else "accepted" if identity else "unavailable",
            "official_program_url": page.get("url") if status == "verified" else None,
            "verified_at": entry["version"].reviewed_at if entry and status == "verified" else None,
            "source": ({k: page["evidence"][0][k] for k in
                        ("source_name", "source_url", "source_document_id", "retrieved_at")}
                       if status == "verified" else None),
            "reason": page.get("reason")}


def verified_entry(entry):
    record, version = entry["record"], entry["version"]
    return bool(record.current_status == "verified" and version and version.status == "verified"
        and any(supporting_evidence({"allowed_use_policy": source.allowed_use_policy,
            "fetch_status": doc.fetch_status, "http_status": doc.http_status,
            "supports_or_conflicts": evidence.supports_or_conflicts,
            "excerpt": evidence.evidence_excerpt, "locator": evidence.evidence_locator})
            for evidence, doc, source in entry["evidence"]))


def academic_completeness(program, ctx):
    entries = ctx["program_facts"].get(program.id, {})
    reviewed = [e for e in entries.values() if verified_entry(e)]
    def supports(keys, predicate):
        return any(e["record"].fact_key in keys and isinstance(e["version"].value_json, dict)
                   and predicate(e["version"].value_json) for e in reviewed)

    def status(available, verified):
        return "unavailable" if not available else "verified" if verified else "unverified"

    fees = [f for f in ctx["fees"].get(program.id, []) if f.fee_type == "tuition" and f.amount is not None]
    requirements = ctx["requirements"].get(program.id, [])
    intakes = ctx["intakes"].get(program.id, [])
    outcomes = [o for o in ctx["outcomes"].get(program.id, []) if o.metric_value is not None]
    def linked(fact_id, keys, predicate):
        return bool(fact_id in entries and verified_entry(entries[fact_id])
            and entries[fact_id]['record'].fact_key in keys
            and isinstance(entries[fact_id]['version'].value_json, dict)
            and predicate(entries[fact_id]['version'].value_json))

    def fee_supported(fee):
        return linked(fee.fact_id, {'tuition', 'tuition_fee', 'program_fee'}, lambda v:
            same_number(v.get('amount'), fee.amount)
            and v.get('currency') == fee.currency and v.get('period') == fee.period)

    def same_number(value, expected):
        try:
            return Decimal(str(value)) == expected
        except (InvalidOperation, ValueError):
            return False

    def intake_supported(row, column):
        return supports({"intake_dates"}, lambda v: v.get("intake_year") == row.intake_year
            and v.get("intake_term") == row.intake_term and getattr(row, column) is not None
            and v.get(column) == getattr(row, column).isoformat())

    fields = {
        "duration": status(program.duration_min_months is not None or program.duration_max_months is not None,
            supports({"duration", "duration_months"}, lambda v:
                v.get("min_months") == program.duration_min_months
                and v.get("max_months") == program.duration_max_months)),
        "teaching_language": status(bool(program.delivery_language), supports({"teaching_language", "language"},
            lambda v: v.get("language") == program.delivery_language)),
        "tuition": status(bool(fees), bool(fees) and all(f.status == "verified" and fee_supported(f) for f in fees)),
        "admissions_requirements": status(bool(requirements), bool(requirements)
            and all(linked(r.source_fact_id, {'admission_requirement'}, lambda v:
                all(v.get(key) == getattr(r, key) for key in
                    ('requirement_type', 'requirement_key', 'operator', 'expected_value', 'is_mandatory')))
                for r in requirements)),
        "intake_dates": status(any(i.start_date for i in intakes),
            any(intake_supported(i, "start_date") for i in intakes)),
        "application_deadline": status(any(i.application_deadline for i in intakes),
            any(intake_supported(i, "application_deadline") for i in intakes)),
        "program_outcomes": status(bool(outcomes), bool(outcomes) and all(linked(o.fact_id,
            {'program_outcome'}, lambda v: v.get('metric_key') == o.metric_key
                and same_number(v.get('metric_value'), o.metric_value) and v.get('metric_unit') == o.metric_unit)
            for o in outcomes)),
    }
    count = sum(s == "verified" for s in fields.values())
    warnings = [f"{key}_{'not_available' if value == 'unavailable' else 'not_verified'}"
                for key, value in fields.items() if value != "verified"]
    return {"status": "complete" if count == len(fields) else "partial" if count else "limited",
            "fields": fields, "verified_count": count, "field_count": len(fields), "warnings": warnings}
