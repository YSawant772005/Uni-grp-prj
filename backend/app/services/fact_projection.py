"""Apply explicitly reviewed structured facts to the existing relational model.

Raw prose remains evidence. It cannot become money or an executable admissions
rule until its required fields and applicability are explicitly structured.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from app.core.errors import ApiError
from app.ingestion.normalize import normalize_url
from app.models import AdmissionRequirement, Program, ProgramFee, ProgramIntake, University
from app.models.enums import FeeType, GroupOperator, IntakeTerm, MoneyPeriod, Operator, RequirementType


def _invalid(message):
    raise ApiError(422, "INVALID_FACT_PROJECTION", message)


def apply_reviewed_fact(db, fact, version) -> str:
    value = version.value_json or {}
    if not isinstance(value, dict):
        return "evidence_only"
    if fact.entity_type == "university" and fact.fact_key == "official_website_url":
        url = normalize_url(value.get("url"))
        if not url:
            _invalid("The reviewed website must contain a usable HTTP(S) URL.")
        university = db.get(University, fact.entity_id)
        if university:
            university.official_website_url = url
            return "applied"
    if fact.entity_type != "program":
        return "evidence_only"
    program = db.get(Program, fact.entity_id)
    if not program:
        _invalid("The reviewed fact has no active programme.")
    if fact.fact_key == "program_description":
        from app.services.program_descriptions import apply_description
        return apply_description(db, program, version)
    if fact.fact_key == "program_title_as_reported":
        title = value.get("title")
        if not isinstance(title, str) or not title.strip() or len(title) > 250:
            _invalid("The reviewed program title must contain 1–250 characters.")
        program.canonical_name = title.strip()
        return "applied"
    if fact.fact_key == "official_program_page_url":
        from urllib.parse import urlsplit
        from app.services.source_urls import classify_program_url
        url = normalize_url(value.get("url"))
        university = db.get(University, program.university_id)
        host = urlsplit(normalize_url(university.official_website_url) or "").hostname if university else None
        page_host = urlsplit(url or "").hostname
        if (not url or classify_program_url(url) != "unverified_candidate" or not host or not page_host
                or not (page_host == host or page_host.endswith("." + host))):
            _invalid("The course page must be an individual URL on the established university domain. Registry and catalogue links have separate roles.")
        from app.services.program_evidence import supporting_program_page_evidence
        if not supporting_program_page_evidence(db, program, version, url):
            _invalid("The URL needs a successful permitted document with matching programme and link evidence before verification.")
        program.official_program_url = url
        return "applied"
    if fact.fact_key in ("tuition", "tuition_fee", "program_fee"):
        if not {"amount", "currency", "period"} <= value.keys():
            return "evidence_only"
        try:
            amount = Decimal(str(value["amount"]))
        except (InvalidOperation, TypeError):
            _invalid("A structured fee needs a finite, nonnegative amount.")
        currency, period = value["currency"], value["period"]
        fee_type = value.get("fee_type", "tuition" if fact.fact_key in ("tuition", "tuition_fee") else None)
        if (not amount.is_finite() or amount < 0 or amount >= Decimal("1000000000000") or not isinstance(currency, str)
                or len(currency) != 3 or not currency.isalpha() or currency != currency.upper()
                or period not in {item.value for item in MoneyPeriod}
                or fee_type not in {item.value for item in FeeType}):
            _invalid("A structured fee needs a valid amount, currency, time basis and fee type.")
        if not value.get("academic_year") and not version.applicable_intake_year:
            _invalid("A reviewed fee needs an academic year or applicable intake.")
        for key, length in (("academic_year", 16), ("student_category", 40)):
            if value.get(key) is not None and (not isinstance(value[key], str) or not 1 <= len(value[key]) <= length):
                _invalid(f"The structured fee {key} must contain 1–{length} characters.")
        row = db.scalar(select(ProgramFee).where(ProgramFee.fact_id == fact.id).with_for_update())
        if row is None:
            row = ProgramFee(program_id=program.id, fact_id=fact.id)
            db.add(row)
        row.amount, row.currency, row.period, row.fee_type = amount, currency, period, fee_type
        row.academic_year = value.get("academic_year")
        row.student_category = value.get("student_category")
        row.status = "verified"
        return "applied"
    if fact.fact_key == "admission_requirement":
        if not {"requirement_type", "requirement_key", "operator", "expected_value"} <= value.keys():
            return "evidence_only"
        if (value["requirement_type"] not in {item.value for item in RequirementType}
                or value["operator"] not in {item.value for item in Operator}
                or not isinstance(value["expected_value"], dict)
                or not isinstance(value["requirement_key"], str)
                or not 1 <= len(value["requirement_key"]) <= 80
                or not isinstance(value.get("is_mandatory"), bool)):
            _invalid("Admissions rules need an explicit type, key, operator, expected value and mandatory flag.")
        if (value.get("group_operator") is not None
                and value["group_operator"] not in {item.value for item in GroupOperator}):
            _invalid("The admissions group operator must be AND or OR.")
        if value.get("group_key") is not None and (not isinstance(value["group_key"], str) or not 1 <= len(value["group_key"]) <= 60):
            _invalid("The admissions group key must contain 1–60 characters.")
        if value.get("applicability_notes") is not None and not isinstance(value["applicability_notes"], str):
            _invalid("Admissions applicability notes must be text.")
        row = db.scalar(select(AdmissionRequirement).where(AdmissionRequirement.source_fact_id == fact.id).with_for_update())
        if row is None:
            row = AdmissionRequirement(program_id=program.id, source_fact_id=fact.id)
            db.add(row)
        for key in ("requirement_type", "requirement_key", "operator", "expected_value", "is_mandatory"):
            setattr(row, key, value[key])
        row.group_key = value.get("group_key")
        row.group_operator = value.get("group_operator")
        row.applicability_notes = value.get("applicability_notes")
        return "applied"
    if fact.fact_key == "intake_dates":
        year = value.get("intake_year")
        term = value.get("intake_term")
        if not isinstance(year, int) or isinstance(year, bool) or not 1900 <= year <= 2200 or term not in {item.value for item in IntakeTerm}:
            return "evidence_only"
        try:
            dates = {key: date.fromisoformat(value[key]) if value.get(key) else None
                     for key in ("application_open_date", "application_deadline", "start_date")}
        except (TypeError, ValueError):
            _invalid("Intake dates must use ISO YYYY-MM-DD values.")
        opened, deadline, start = dates.values()
        if (opened and deadline and opened > deadline) or (deadline and start and deadline > start):
            _invalid("Intake opening, deadline and start dates must be in order.")
        if value.get("is_open_for_applications") is not None and not isinstance(value["is_open_for_applications"], bool):
            _invalid("Application availability must be true, false or unknown.")
        row = db.scalar(select(ProgramIntake).where(ProgramIntake.program_id == program.id,
            ProgramIntake.intake_year == year, ProgramIntake.intake_term == term).with_for_update())
        if row is None:
            row = ProgramIntake(program_id=program.id, intake_year=year, intake_term=term)
            db.add(row)
        for key, item in dates.items():
            setattr(row, key, item)
        row.is_open_for_applications = value.get("is_open_for_applications")
        row.status = "verified"
        return "applied"
    return "evidence_only"
