"""Student profile validation, updates and completeness.

Validation is service-level so API errors stay in the standard envelope; DB CHECKs remain
the final backstop. Grade-scale and budget-basis rules are enforced here so an inconsistent
value produces a field-level 422 instead of a 500.

API priority importance is an integer 1..5; it is stored normalized as ``weight/5`` in
``[0.2, 1.0]`` to match the schema's ``0 <= weight <= 1`` CHECK.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import (
    BudgetBasis,
    Country,
    CountryMode,
    DegreeLevel,
    EnglishTestType,
    Field,
    GradeSystem,
    GraduationStatus,
    IntakeTerm,
    PriorityKey,
    ProfileCountryPreference,
    ProfilePriority,
    RiskTolerance,
    StudentProfile,
    TestStatus,
    User,
)

MAX_GRADUATION_YEAR = datetime.now(timezone.utc).year + 10
_SCALAR_FIELDS = [
    "intended_degree_level", "desired_degree_title", "country_mode", "risk_tolerance", "academic_degree",
    "academic_major", "institution_name", "grade_value", "grade_scale_min",
    "grade_scale_max", "grade_system", "graduation_status", "graduation_year",
    "backlog_count", "english_test_status", "english_test_type", "english_test_overall",
    "english_test_component_scores", "other_test_scores", "work_experience_months",
    "projects_summary", "career_goal", "budget_amount", "budget_currency",
    "budget_basis", "target_intake_year", "target_intake_term",
]


def _detail(field: str, code: str, message: str) -> dict:
    return {"field": field, "code": code, "message": message}


def _pick(obj, key, default=None):
    """Read a field from either a dict or an object without eager-eval pitfalls."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _check_enum(details: list[dict], field: str, value, allowed: tuple[str, ...]) -> None:
    if value is not None and value not in allowed:
        details.append(_detail(field, "invalid_choice", f"{field} must be one of {', '.join(allowed)}."))


def _get_or_create_profile(db: Session, user: User) -> StudentProfile:
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
    if profile is None:
        profile = StudentProfile(user_id=user.id)
        db.add(profile)
        db.flush()
    return profile


def current_profile(db: Session, user: User) -> StudentProfile:
    """Public accessor used by routers; creates the empty profile row on first access."""
    return _get_or_create_profile(db, user)


def validate_profile(db: Session, view: dict) -> list[dict]:
    """Enum + cross-field validation over the *effective* profile state."""
    details: list[dict] = []
    _check_enum(details, "intended_degree_level", view.get("intended_degree_level"),
                tuple(m.value for m in DegreeLevel))
    _check_enum(details, "country_mode", view.get("country_mode"), tuple(m.value for m in CountryMode))
    _check_enum(details, "risk_tolerance", view.get("risk_tolerance"), tuple(m.value for m in RiskTolerance))
    _check_enum(details, "grade_system", view.get("grade_system"), tuple(m.value for m in GradeSystem))
    _check_enum(details, "graduation_status", view.get("graduation_status"),
                tuple(m.value for m in GraduationStatus))
    _check_enum(details, "english_test_status", view.get("english_test_status"),
                tuple(m.value for m in TestStatus))
    _check_enum(details, "english_test_type", view.get("english_test_type"),
                tuple(m.value for m in EnglishTestType))
    _check_enum(details, "budget_basis", view.get("budget_basis"), tuple(m.value for m in BudgetBasis))
    _check_enum(details, "target_intake_term", view.get("target_intake_term"),
                tuple(m.value for m in IntakeTerm))

    field_key = view.get("field")
    if field_key is not None and db.scalar(select(Field.id).where(Field.key == field_key)) is None:
        details.append(_detail("field", "unknown_value", f"Unknown field '{field_key}'."))

    grade_value = view.get("grade_value")
    scale_min, scale_max = view.get("grade_scale_min"), view.get("grade_scale_max")
    if grade_value is not None:
        if scale_min is None or scale_max is None:
            details.append(_detail("grade_scale_min", "required",
                                   "Grade scale bounds are required when a grade value is given."))
        elif scale_min >= scale_max:
            details.append(_detail("grade_scale_max", "invalid_range",
                                   "grade_scale_max must exceed grade_scale_min."))
        elif not (scale_min <= grade_value <= scale_max):
            details.append(_detail("grade_value", "out_of_range",
                                   "grade_value must lie within the declared scale."))

    if view.get("budget_amount") is not None:
        if not view.get("budget_currency"):
            details.append(_detail("budget_currency", "required", "Currency is required with a budget amount."))
        if not view.get("budget_basis"):
            details.append(_detail("budget_basis", "required", "Basis is required with a budget amount."))

    if view.get("english_test_status") == TestStatus.completed.value:
        if not view.get("english_test_type"):
            details.append(_detail("english_test_type", "required",
                                   "Test type is required when the test is completed."))
        if view.get("english_test_overall") is None:
            details.append(_detail("english_test_overall", "required",
                                   "Overall score is required when the test is completed."))

    if view.get("graduation_year") is not None and view["graduation_year"] > MAX_GRADUATION_YEAR:
        details.append(_detail("graduation_year", "out_of_range",
                               f"graduation_year must be {MAX_GRADUATION_YEAR} or earlier."))

    prefs = view.get("country_preferences") or []
    ranks = []
    for pref in prefs:
        code = _pick(pref, "country_code")
        if code and db.scalar(select(Country.code).where(Country.code == code.upper())) is None:
            details.append(_detail("country_preferences", "unknown_value", f"Unknown country '{code}'."))
        rank = _pick(pref, "preference_rank")
        if rank is not None:
            ranks.append(rank)
    if len(ranks) != len(set(ranks)):
        details.append(_detail("country_preferences", "duplicate_rank",
                               "Country preference ranks must be unique."))

    for prio in view.get("priorities") or []:
        _check_enum(details, "priorities", _pick(prio, "priority_key"),
                    tuple(m.value for m in PriorityKey))

    return details


def _current_view(db: Session, profile: StudentProfile) -> dict:
    field = db.get(Field, profile.field_id) if profile.field_id else None
    view = {name: getattr(profile, name) for name in _SCALAR_FIELDS}
    view["field"] = field.key if field else None
    view["country_preferences"] = list(profile.country_preferences)
    view["priorities"] = list(profile.priorities)
    return view


def _apply(db: Session, profile: StudentProfile, data: dict, *, replace: bool) -> None:
    if "field" in data or replace:
        field_key = data.get("field")
        profile.field_id = db.scalar(select(Field.id).where(Field.key == field_key)) if field_key else None
    for name in _SCALAR_FIELDS:
        if name in data:
            setattr(profile, name, data[name])
        elif replace and name != "intended_degree_level":
            setattr(profile, name, None)

    if "country_preferences" in data and data["country_preferences"] is not None:
        db.query(ProfileCountryPreference).filter(
            ProfileCountryPreference.profile_id == profile.id).delete()
        for i, pref in enumerate(data["country_preferences"], start=1):
            db.add(ProfileCountryPreference(
                profile_id=profile.id,
                country_code=_pick(pref, "country_code").upper(),
                preference_rank=_pick(pref, "preference_rank") or i,
                is_mandatory=bool(_pick(pref, "is_mandatory", False)),
            ))
    if "priorities" in data and data["priorities"] is not None:
        db.query(ProfilePriority).filter(ProfilePriority.profile_id == profile.id).delete()
        for prio in data["priorities"]:
            db.add(ProfilePriority(
                profile_id=profile.id,
                priority_key=_pick(prio, "priority_key"),
                weight=Decimal(_pick(prio, "weight")) / Decimal(5),
            ))
    db.flush()
    db.refresh(profile)  # reload selectin collections so output reflects new rows


def _raise(details: list[dict]) -> None:
    if details:
        raise ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.", details)


def update_profile(db: Session, user: User, payload, *, replace: bool) -> StudentProfile:
    profile = _get_or_create_profile(db, user)
    if replace:
        data = payload.model_dump()
        data["country_preferences"] = list(payload.country_preferences)
        data["priorities"] = list(payload.priorities)
        view = data
    else:
        data = payload.model_dump(exclude_unset=True)
        view = _current_view(db, profile)
        for k, v in data.items():
            view[k] = v
        if "country_preferences" in data:
            view["country_preferences"] = list(payload.country_preferences)
        if "priorities" in data:
            view["priorities"] = list(payload.priorities)
    _raise(validate_profile(db, view))
    _apply(db, profile, data, replace=replace)
    return profile


def complete_onboarding(db: Session, user: User, payload) -> dict:
    data = payload.model_dump()
    view = {**data, "country_preferences": list(payload.country_preferences), "priorities": None}
    _raise(validate_profile(db, view))
    profile = _get_or_create_profile(db, user)
    _apply(db, profile, data, replace=True)
    profile.profile_completed_at = datetime.now(timezone.utc)
    db.flush()
    return {"profile": profile_out(db, profile), "completeness": completeness(profile)}


# --------------------------------------------------------------------------- output

def serialize_profile(profile: StudentProfile, field_key: str | None = None) -> dict:
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "intended_degree_level": profile.intended_degree_level,
        "desired_degree_title": profile.desired_degree_title,
        "field_key": field_key,
        "country_mode": profile.country_mode,
        "risk_tolerance": profile.risk_tolerance,
        "academic_degree": profile.academic_degree,
        "academic_major": profile.academic_major,
        "institution_name": profile.institution_name,
        "grade_value": profile.grade_value,
        "grade_scale_min": profile.grade_scale_min,
        "grade_scale_max": profile.grade_scale_max,
        "grade_system": profile.grade_system,
        "graduation_status": profile.graduation_status,
        "graduation_year": profile.graduation_year,
        "backlog_count": profile.backlog_count,
        "english_test_status": profile.english_test_status,
        "english_test_type": profile.english_test_type,
        "english_test_overall": profile.english_test_overall,
        "english_test_component_scores": profile.english_test_component_scores,
        "other_test_scores": profile.other_test_scores,
        "work_experience_months": profile.work_experience_months,
        "projects_summary": profile.projects_summary,
        "career_goal": profile.career_goal,
        "budget_amount": profile.budget_amount,
        "budget_currency": profile.budget_currency,
        "budget_basis": profile.budget_basis,
        "target_intake_year": profile.target_intake_year,
        "target_intake_term": profile.target_intake_term,
        "profile_completed_at": profile.profile_completed_at.isoformat()
        if profile.profile_completed_at else None,
        "country_preferences": [
            {"country_code": p.country_code, "preference_rank": p.preference_rank,
             "is_mandatory": p.is_mandatory}
            for p in sorted(profile.country_preferences, key=lambda p: p.preference_rank)
        ],
        "priorities": [
            {"priority_key": p.priority_key, "weight": p.weight}
            for p in sorted(profile.priorities, key=lambda p: p.priority_key)
        ],
    }


def profile_out(db: Session, profile: StudentProfile) -> dict:
    field = db.get(Field, profile.field_id) if profile.field_id else None
    return serialize_profile(profile, field_key=field.key if field else None)


REQUIRED_GROUPS = [
    ("degree_level", "Intended degree level"),
    ("field", "Field of study"),
    ("countries", "Preferred countries"),
    ("academics", "Academic background"),
    ("graduation", "Graduation details"),
    ("english", "English test status"),
    ("budget", "Budget"),
    ("intake", "Target intake"),
]


def completeness(profile: StudentProfile) -> dict:
    def done(key: str) -> bool:
        if key == "degree_level":
            return bool(profile.intended_degree_level)
        if key == "field":
            return profile.field_id is not None
        if key == "countries":
            return bool(profile.country_preferences)
        if key == "academics":
            return all([profile.academic_degree, profile.institution_name,
                        profile.grade_value is not None, profile.grade_scale_min is not None,
                        profile.grade_scale_max is not None, profile.grade_system])
        if key == "graduation":
            return bool(profile.graduation_status and profile.graduation_year)
        if key == "english":
            if profile.english_test_status == TestStatus.completed.value:
                return bool(profile.english_test_type and profile.english_test_overall is not None)
            return bool(profile.english_test_status)
        if key == "budget":
            return bool(profile.budget_amount is not None and profile.budget_currency
                        and profile.budget_basis)
        if key == "intake":
            return bool(profile.target_intake_year and profile.target_intake_term)
        return False

    optional = {
        "work_experience": profile.work_experience_months is not None,
        "projects": bool(profile.projects_summary),
        "career_goal": bool(profile.career_goal),
        "priorities": bool(profile.priorities),
        "risk_tolerance": bool(profile.risk_tolerance),
    }
    items = [{"key": k, "label": lbl, "required": True, "complete": done(k)}
             for k, lbl in REQUIRED_GROUPS]
    items += [{"key": k, "label": k.replace("_", " ").title(), "required": False, "complete": v}
              for k, v in optional.items()]
    required_done = sum(1 for i in items if i["required"] and i["complete"])
    return {
        "required_complete": required_done == len(REQUIRED_GROUPS),
        "optional_complete": all(i["complete"] for i in items if not i["required"]),
        "percentage": round(100 * required_done / len(REQUIRED_GROUPS)),
        "items": items,
    }
