"""Deterministic admission-eligibility engine (API_Contract §5.5, plan §4.3).

States: ``eligible``, ``conditionally_eligible``, ``ineligible``, ``unknown_needs_review``.
Rules are evidence-based and reproducible; a missing/unknown mandatory requirement is
NEVER converted into "eligible". Requirement groups use ALL/ANY logic; groups combine
with AND (every group must be satisfied).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models import AdmissionRequirement, EligibilityStatus, EvalStatus, StudentProfile


def _parse_scale(value) -> Decimal | None:
    """Best-effort numeric scale from a requirement's declared scale string/number."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _grade_result(req: AdmissionRequirement, profile: StudentProfile) -> tuple[str, object, str]:
    expected = req.expected_value or {}
    req_value = _parse_scale(expected.get("value"))
    req_max = _parse_scale(expected.get("scale")) or Decimal("4.0")
    if profile.grade_value is None or profile.grade_scale_max in (None, 0):
        return EvalStatus.unknown.value, None, "No grade on profile to compare against this requirement."
    student = Decimal(profile.grade_value) / Decimal(profile.grade_scale_max)
    target = req_value / req_max if req_value is not None else None
    if target is None:
        return EvalStatus.unknown.value, profile.grade_value, "Requirement value missing; cannot evaluate."
    op = req.operator
    ok = {"gte": student >= target, "gt": student > target, "lte": student <= target,
          "lt": student < target, "eq": student == target}.get(op, student >= target)
    scale_note = (f"compared on a normalized 0-1 basis "
                  f"(profile {profile.grade_value}/{profile.grade_scale_max} vs "
                  f"required {req_value}/{req_max})")
    status = EvalStatus.pass_.value if ok else EvalStatus.fail.value
    return status, float(round(student, 4)), f"Grade {scale_note}."


def _language_result(req: AdmissionRequirement, profile: StudentProfile) -> tuple[str, object, str]:
    expected = req.expected_value or {}
    req_value = _parse_scale(expected.get("value"))
    required_test = (expected.get("test") or "ielts")
    if profile.english_test_status != "completed":
        return (EvalStatus.unknown.value, profile.english_test_status,
                "English test not marked completed; score cannot be verified yet.")
    if profile.english_test_overall is None:
        return EvalStatus.unknown.value, None, "English test completed but no overall score recorded."
    if (profile.english_test_type or "").lower() != required_test.lower():
        return (EvalStatus.unknown.value, profile.english_test_overall,
                f"Profile shows {profile.english_test_type}; a verified conversion to "
                f"{required_test} is needed before this requirement can be evaluated.")
    if req_value is None:
        return EvalStatus.unknown.value, float(profile.english_test_overall), "Required score missing."
    student = Decimal(profile.english_test_overall)
    op = req.operator
    ok = {"gte": student >= req_value, "gt": student > req_value, "lte": student <= req_value,
          "lt": student < req_value, "eq": student == req_value}.get(op, student >= req_value)
    status = EvalStatus.pass_.value if ok else EvalStatus.fail.value
    return (status, float(student),
            f"{required_test.upper()} overall {student} vs required {req_value} ({op}).")


def _work_result(req: AdmissionRequirement, profile: StudentProfile) -> tuple[str, object, str]:
    expected = req.expected_value or {}
    req_months = expected.get("months")
    if profile.work_experience_months is None:
        return EvalStatus.unknown.value, None, "Work experience not recorded on profile."
    if req_months is None:
        return EvalStatus.unknown.value, profile.work_experience_months, "Required months missing."
    ok = Decimal(profile.work_experience_months) >= Decimal(str(req_months))
    status = EvalStatus.pass_.value if ok else EvalStatus.fail.value
    return (status, profile.work_experience_months,
            f"{profile.work_experience_months} months vs required {req_months}+.")


def _text_result(req: AdmissionRequirement, profile: StudentProfile, value: str | None,
                 label: str) -> tuple[str, object, str]:
    expected = req.expected_value or {}
    accepted = expected.get("degrees") or expected.get("values") or expected.get("majors") or []
    if value is None:
        return EvalStatus.unknown.value, None, f"{label} not recorded on profile."
    if not accepted:
        return EvalStatus.conditional.value, value, f"{label} present; mapping needs review."
    vl = value.lower()
    if any(str(a).lower() in vl or vl in str(a).lower() for a in accepted):
        return EvalStatus.pass_.value, value, f"{label} matches an accepted value."
    return (EvalStatus.conditional.value, value,
            f"{label} '{value}' not explicitly mapped to accepted values; needs review.")


def _course_result(req: AdmissionRequirement, profile: StudentProfile) -> tuple[str, object, str]:
    return (EvalStatus.unknown.value, None,
            "Course completion is not tracked in the MVP profile; a transcript review is required.")


def _generic_result(req: AdmissionRequirement, profile: StudentProfile) -> tuple[str, object, str]:
    if req.operator == "manual_review":
        return EvalStatus.conditional.value, None, "This requirement is flagged for manual review."
    return (EvalStatus.unknown.value, None,
            f"No automated rule for requirement type '{req.requirement_type}'; needs review.")


def evaluate_requirement(req: AdmissionRequirement, profile: StudentProfile) -> dict:
    rtype = req.requirement_type
    if rtype == "grade":
        status, value, expl = _grade_result(req, profile)
    elif rtype == "language_test":
        status, value, expl = _language_result(req, profile)
    elif rtype == "work_experience":
        status, value, expl = _work_result(req, profile)
    elif rtype == "degree":
        status, value, expl = _text_result(req, profile, profile.academic_degree, "Degree")
    elif rtype == "major":
        status, value, expl = _text_result(req, profile, profile.academic_major, "Major")
    elif rtype == "prerequisite_course":
        status, value, expl = _course_result(req, profile)
    else:
        status, value, expl = _generic_result(req, profile)
    return {
        "requirement_id": req.id,
        "requirement_key": req.requirement_key,
        "requirement_type": req.requirement_type,
        "is_mandatory": req.is_mandatory,
        "group_key": req.group_key,
        "operator": req.operator,
        "expected_value": req.expected_value,
        "status": status,
        "evaluated_value": value,
        "explanation": expl,
    }


def _combine_group(results: list[dict], operator: str) -> str:
    statuses = [r["status"] for r in results]
    if operator == "ANY":
        if EvalStatus.pass_.value in statuses:
            return EvalStatus.pass_.value
        if EvalStatus.fail.value in statuses and EvalStatus.conditional.value not in statuses \
                and EvalStatus.unknown.value not in statuses:
            return EvalStatus.fail.value
        if EvalStatus.conditional.value in statuses:
            return EvalStatus.conditional.value
        return EvalStatus.unknown.value
    # ALL
    if EvalStatus.fail.value in statuses:
        return EvalStatus.fail.value
    if EvalStatus.unknown.value in statuses:
        return EvalStatus.unknown.value
    if EvalStatus.conditional.value in statuses:
        return EvalStatus.conditional.value
    return EvalStatus.pass_.value


def _overall(group_statuses: list[str]) -> str:
    if not group_statuses:
        return EligibilityStatus.unknown_needs_review.value
    if EvalStatus.fail.value in group_statuses:
        return EligibilityStatus.ineligible.value
    if EvalStatus.unknown.value in group_statuses:
        return EligibilityStatus.unknown_needs_review.value
    if EvalStatus.conditional.value in group_statuses:
        return EligibilityStatus.conditionally_eligible.value
    return EligibilityStatus.eligible.value


def evaluate_program(profile: StudentProfile, requirements: list[AdmissionRequirement]) -> dict:
    """Evaluate one program's requirements against a profile. Pure given loaded rows."""
    req_results = [evaluate_requirement(r, profile) for r in requirements]
    groups: dict[str, list[dict]] = {}
    for r in req_results:
        groups.setdefault(r["group_key"] or "default", []).append(r)

    group_out, group_statuses = [], []
    for key, members in groups.items():
        operator = next((r.group_operator for r in requirements
                         if (r.group_key or "default") == key), "AND")
        status = _combine_group(members, operator)
        group_statuses.append(status)
        group_out.append({"group_key": key, "group_operator": operator, "status": status,
                          "requirement_keys": [m["requirement_key"] for m in members]})

    overall = _overall(group_statuses)
    return {
        "status": overall,
        "requirements": req_results,
        "groups": group_out,
        "unsatisfied": [r["requirement_key"] for r in req_results if r["status"] == EvalStatus.fail.value],
        "unknowns": [r["requirement_key"] for r in req_results if r["status"] == EvalStatus.unknown.value],
        "conditions": [r["requirement_key"] for r in req_results
                       if r["status"] == EvalStatus.conditional.value],
    }


def load_requirements(db: Session, program_id) -> list[AdmissionRequirement]:
    return list(db.query(AdmissionRequirement)
                .filter(AdmissionRequirement.program_id == program_id)
                .order_by(AdmissionRequirement.group_key, AdmissionRequirement.id).all())
