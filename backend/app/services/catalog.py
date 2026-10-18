"""Catalogue search and detail queries (discovery).

Documented filter semantics (API_Contract §4.3/§5.4):
* ``max_tuition`` filters TUITION ALONE (never total cost) and only compares fees
  recorded in the requested ``currency``; no cross-currency conversion here.
* ``q`` is a case-insensitive substring match on program or university name.
* Unknown filter values raise 422 instead of being silently ignored.
* Fact statuses shown are evidence statuses; seeded demo fixtures are never ``verified``.
* Missing money is returned as ``amount=None`` with status ``unavailable`` — never 0.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import and_, asc, desc, exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import (
    AdmissionRequirement,
    Campus,
    City,
    Country,
    FactEvidence,
    FactRecord,
    FactVersion,
    Field,
    Program,
    ProgramFee,
    ProgramIntake,
    ProgramOutcomeEvidence,
    Source,
    SourceDocument,
    University,
)

DEGREE_LEVELS = ("bachelors", "masters", "phd", "other")
LANGUAGES = ("en", "de", "nl", "fr", "es", "other")
SORT_FIELDS = ("name", "deadline", "tuition", "country")
RECOGNITION_STATUSES = ("official", "candidacy", "unknown", "not_officially_recognized", "other")
# statuses whose amounts may be surfaced as a price summary (never fabricated)
PRICING_STATUSES = ("verified", "estimated", "unverified", "stale", "conflicted", "unavailable")
_STATUS_RANK = {s: i for i, s in enumerate(
    ("verified", "estimated", "unverified", "stale", "conflicted", "unavailable"))}


def _err(field: str, message: str) -> ApiError:
    return ApiError(422, "VALIDATION_ERROR", "One or more fields are invalid.",
                    [{"field": field, "code": "unknown_value", "message": message}])


def _require_known(db: Session, model, column, value, label: str):
    if value is None:
        return
    if db.scalar(select(model).where(column == value).limit(1)) is None:
        raise _err(label, f"Unknown {label} filter '{value}'.")


# --------------------------------------------------------------------------- context

def _page_context(db: Session, program_ids: list[uuid.UUID]) -> dict:
    """Batch-load related rows for a page of programs (fixed number of queries)."""
    ctx: dict = {"intakes": {}, "fees": {}, "requirements": {}, "facts": {},
                 "outcomes": {}, "fields": {}}
    if not program_ids:
        return ctx

    for row in db.scalars(select(ProgramIntake).where(ProgramIntake.program_id.in_(program_ids))
                          .order_by(ProgramIntake.application_deadline.nulls_last(),
                                    ProgramIntake.intake_year, ProgramIntake.intake_term)):
        ctx["intakes"].setdefault(row.program_id, []).append(row)
    for row in db.scalars(select(ProgramFee).where(ProgramFee.program_id.in_(program_ids))
                          .order_by(ProgramFee.id)):
        ctx["fees"].setdefault(row.program_id, []).append(row)
    for row in db.scalars(select(AdmissionRequirement)
                          .where(AdmissionRequirement.program_id.in_(program_ids))
                          .order_by(AdmissionRequirement.group_key, AdmissionRequirement.id)):
        ctx["requirements"].setdefault(row.program_id, []).append(row)
    for row in db.scalars(select(ProgramOutcomeEvidence)
                          .where(ProgramOutcomeEvidence.program_id.in_(program_ids))):
        ctx["outcomes"].setdefault(row.program_id, []).append(row)
    ctx["fields"] = {f.id: {"key": f.key, "display_name": f.display_name}
                     for f in db.scalars(select(Field))}

    # fact provenance for the programs' fees/requirements/outcomes
    fact_rows = db.execute(
        select(FactRecord, FactVersion, SourceDocument, Source)
        .join(FactVersion, FactVersion.id == FactRecord.current_version_id, isouter=True)
        .join(FactEvidence, FactEvidence.fact_version_id == FactVersion.id, isouter=True)
        .join(SourceDocument, SourceDocument.id == FactEvidence.source_document_id, isouter=True)
        .join(Source, Source.id == SourceDocument.source_id, isouter=True)
        .where(FactRecord.entity_type == "program", FactRecord.entity_id.in_(program_ids))
    ).all()
    for rec, ver, doc, src in fact_rows:
        ctx["facts"][rec.id] = _provenance(rec, ver, doc, src)
    return ctx


def _provenance(rec: FactRecord, ver: FactVersion | None, doc: SourceDocument | None,
                src: Source | None) -> dict:
    source = None
    if doc is not None and src is not None:
        source = {
            "source_id": src.id,
            "title": doc.title,
            "url": doc.canonical_url,
            "retrieved_at": doc.retrieved_at,
            "verified_at": ver.reviewed_at if ver is not None else None,
        }
    return {
        "status": rec.current_status,
        "version_number": ver.version_number if ver is not None else None,
        "value": ver.normalized_value_json if ver is not None else None,
        "extraction_method": ver.extraction_method if ver is not None else None,
        "source": source,
    }


# --------------------------------------------------------------------------- shaping

def _tuition_fee_for(fees: list[ProgramFee]) -> ProgramFee | None:
    tuition = [f for f in fees if f.fee_type == "tuition"]
    if not tuition:
        return None
    tuition.sort(key=lambda f: (_STATUS_RANK.get(f.status, 9), str(f.id)))
    tuition.sort(key=lambda f: f.academic_year or "", reverse=True)  # stable: newest year first
    return tuition[0]


def _money_object(fee: ProgramFee | None, provenance: dict | None) -> dict:
    if fee is None:
        return {"value": None, "unit": None, "period": None, "academic_year": None,
                "applicable_intake": None, "status": "unavailable", "source": None}
    return {
        "value": fee.amount,
        "unit": fee.currency,
        "period": fee.period,
        "academic_year": fee.academic_year,
        "applicable_intake": None,
        "status": fee.status,
        "source": provenance.get("source") if provenance else None,
    }


def _data_quality(tuition_status: str | None, requirement_statuses: list[str],
                  has_intake: bool, has_program_outcomes: bool) -> dict:
    warnings: list[str] = []
    if tuition_status is None:
        warnings.append("tuition_not_available")
    elif tuition_status != "verified":
        warnings.append("tuition_not_verified")
    if not requirement_statuses or any(s != "verified" for s in requirement_statuses):
        warnings.append("requirements_not_verified")
    if not has_intake:
        warnings.append("intake_deadline_unknown")
    if not has_program_outcomes:
        warnings.append("no_program_level_outcome_data")
    if tuition_status is None and not requirement_statuses:
        status = "unavailable"
    elif warnings:
        status = "partial"
    else:
        status = "verified"
    return {"status": status, "last_verified_at": None, "warnings": warnings}


def _summary(program: Program, university: University, city: City | None, ctx: dict) -> dict:
    intakes = ctx["intakes"].get(program.id, [])
    fees = ctx["fees"].get(program.id, [])
    reqs = ctx["requirements"].get(program.id, [])
    tuition = _tuition_fee_for(fees)
    prov = ctx["facts"].get(tuition.fact_id) if tuition and tuition.fact_id else None

    today = date.today()
    upcoming = [i for i in intakes if i.application_deadline and i.application_deadline >= today]
    nearest = (upcoming or intakes or [None])[0]

    return {
        "id": program.id,
        "name": program.canonical_name,
        "slug": program.slug,
        "degree_level": program.degree_level,
        "field": ctx["fields"].get(program.field_id),
        "country_code": program.country_code,
        "duration_min_months": program.duration_min_months,
        "duration_max_months": program.duration_max_months,
        "duration_months": program.duration_max_months,
        "language": program.delivery_language,
        "study_mode": program.study_mode,
        "university": {
            "id": university.id,
            "name": university.canonical_name,
            "country_code": university.country_code,
            "recognition_status": university.recognition_status,
            "city": city.name if city else None,
        },
        "nearest_intake": (
            {"intake_year": nearest.intake_year, "intake_term": nearest.intake_term,
             "application_deadline": nearest.application_deadline,
             "is_open_for_applications": nearest.is_open_for_applications}
            if nearest else None
        ),
        "tuition_summary": _money_object(tuition, prov),
        "data_quality": _data_quality(
            tuition.status if tuition else None,
            [ctx["facts"].get(r.source_fact_id, {}).get("status", "unverified") for r in reqs],
            has_intake=bool(intakes),
            has_program_outcomes=bool(ctx["outcomes"].get(program.id)),
        ),
    }


def _requirement_item(req: AdmissionRequirement, ctx: dict) -> dict:
    prov = ctx["facts"].get(req.source_fact_id) if req.source_fact_id else None
    return {
        "id": req.id,
        "requirement_type": req.requirement_type,
        "requirement_key": req.requirement_key,
        "operator": req.operator,
        "expected_value": req.expected_value,
        "is_mandatory": req.is_mandatory,
        "group_key": req.group_key,
        "group_operator": req.group_operator,
        "applicability_notes": req.applicability_notes,
        "evidence": {"status": prov["status"] if prov else "unverified",
                     "source": prov.get("source") if prov else None},
    }


def _fee_item(fee: ProgramFee, ctx: dict) -> dict:
    prov = ctx["facts"].get(fee.fact_id) if fee.fact_id else None
    return {
        "id": fee.id,
        "fee_type": fee.fee_type,
        "amount": fee.amount,
        "currency": fee.currency,
        "period": fee.period,
        "academic_year": fee.academic_year,
        "student_category": fee.student_category,
        "is_mandatory": fee.is_mandatory,
        "status": fee.status,
        "provenance": prov,
    }


def _intake_item(intake: ProgramIntake) -> dict:
    return {
        "id": intake.id,
        "intake_year": intake.intake_year,
        "intake_term": intake.intake_term,
        "application_open_date": intake.application_open_date,
        "application_deadline": intake.application_deadline,
        "start_date": intake.start_date,
        "is_open_for_applications": intake.is_open_for_applications,
        "status": intake.status,
    }


# --------------------------------------------------------------------------- endpoints

def search_programs(db: Session, *, q=None, country=None, city=None, field=None,
                    degree_level=None, language=None, min_duration_months=None,
                    max_duration_months=None, max_tuition=None, currency=None,
                    recognition_status=None, page=1, page_size=20, sort="name", order="asc") -> dict:
    # -- filter validation (422 on unknown values, per contract §4.3)
    _require_known(db, Field, Field.key, field, "field")
    _require_known(db, City, City.slug, city, "city")
    if country is not None:
        _require_known(db, Country, Country.code, country.upper(), "country")
    if degree_level is not None and degree_level not in DEGREE_LEVELS:
        raise _err("degree_level", f"degree_level must be one of {', '.join(DEGREE_LEVELS)}.")
    if language is not None and language not in LANGUAGES:
        raise _err("language", f"language must be one of {', '.join(LANGUAGES)}.")
    if recognition_status is not None and recognition_status not in RECOGNITION_STATUSES:
        raise _err("recognition_status",
                   f"recognition_status must be one of {', '.join(RECOGNITION_STATUSES)}.")
    if sort not in SORT_FIELDS:
        raise _err("sort", f"sort must be one of {', '.join(SORT_FIELDS)}.")
    if order not in ("asc", "desc"):
        raise _err("order", "order must be 'asc' or 'desc'.")
    if max_tuition is not None and currency is None:
        raise _err("currency", "currency is required when max_tuition is used "
                               "(tuition filtering compares only within one currency).")
    if currency is not None:
        currency = currency.upper()

    conds = [Program.publication_status == "published", Program.is_active.is_(True)]
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(Program.canonical_name.ilike(like), University.canonical_name.ilike(like)))
    if country:
        conds.append(Program.country_code == country.upper())
    if city:
        conds.append(City.slug == city)
    if field:
        conds.append(Program.field_id.in_(select(Field.id).where(Field.key == field)))
    if degree_level:
        conds.append(Program.degree_level == degree_level)
    if language:
        conds.append(Program.delivery_language == language)
    if recognition_status:
        conds.append(University.recognition_status == recognition_status)
    if min_duration_months is not None:
        conds.append(Program.duration_max_months >= min_duration_months)
    if max_duration_months is not None:
        conds.append(Program.duration_min_months <= max_duration_months)

    # tuition subquery conditions (correlated to Program); pricing never includes
    # 'unavailable' rows (their amount is NULL anyway)
    fee_conds = [ProgramFee.program_id == Program.id, ProgramFee.fee_type == "tuition",
                 ProgramFee.amount.is_not(None),
                 ProgramFee.status.in_(PRICING_STATUSES[:-1])]
    if currency is not None:
        fee_conds.append(ProgramFee.currency == currency)
    if max_tuition is not None:
        fee_conds.append(ProgramFee.amount <= max_tuition)

    deadline_sq = (select(func.min(ProgramIntake.application_deadline))
                   .where(ProgramIntake.program_id == Program.id)
                   .correlate(Program).scalar_subquery())
    tuition_sq = (select(func.min(ProgramFee.amount)).where(*fee_conds)
                  .correlate(Program).scalar_subquery())

    base = (select(Program, University, City)
            .join(University, Program.university_id == University.id)
            .outerjoin(Campus, Program.campus_id == Campus.id)
            .outerjoin(City, Campus.city_id == City.id)
            .where(*conds))
    if max_tuition is not None:
        base = base.where(exists(select(ProgramFee.id).where(*fee_conds)))

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    direction = desc if order == "desc" else asc
    if sort == "deadline":
        order_cols = [direction(deadline_sq).nulls_last()]
    elif sort == "tuition":
        order_cols = [direction(tuition_sq).nulls_last()]
    elif sort == "country":
        order_cols = [direction(Program.country_code)]
    else:
        order_cols = [direction(Program.canonical_name)]
    rows = db.execute(base.order_by(*order_cols, Program.id.asc())
                      .offset((page - 1) * page_size).limit(page_size)).all()

    ctx = _page_context(db, [r[0].id for r in rows])
    items = [_summary(program, university, city, ctx) for program, university, city in rows]
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total_items": total,
        "total_pages": (total + page_size - 1) // page_size,
    }


def _load_program(db: Session, program_id: uuid.UUID):
    row = db.execute(
        select(Program, University, City)
        .join(University, Program.university_id == University.id)
        .outerjoin(Campus, Program.campus_id == Campus.id)
        .outerjoin(City, Campus.city_id == City.id)
        .where(Program.id == program_id,
               Program.publication_status == "published", Program.is_active.is_(True))
    ).first()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Program not found.")
    return row


def get_program(db: Session, program_id: uuid.UUID) -> dict:
    program, university, city = _load_program(db, program_id)
    ctx = _page_context(db, [program.id])
    summary = _summary(program, university, city, ctx)
    summary.update({
        "description": program.description,
        "official_program_url": program.official_program_url,
        "intakes": [_intake_item(i) for i in ctx["intakes"].get(program.id, [])],
        "fees": [_fee_item(f, ctx) for f in ctx["fees"].get(program.id, [])],
        "requirements": [_requirement_item(r, ctx) for r in ctx["requirements"].get(program.id, [])],
        "campus": ({"id": None, "name": None, "city": city.name} if city else None),
    })
    return summary


def get_requirements(db: Session, program_id: uuid.UUID) -> list[dict]:
    program, _, _ = _load_program(db, program_id)
    ctx = _page_context(db, [program.id])
    return [_requirement_item(r, ctx) for r in ctx["requirements"].get(program.id, [])]


def get_fees(db: Session, program_id: uuid.UUID) -> list[dict]:
    program, _, _ = _load_program(db, program_id)
    ctx = _page_context(db, [program.id])
    fees = ctx["fees"].get(program.id, [])
    items = [_fee_item(f, ctx) for f in fees]
    if not any(f.fee_type == "tuition" for f in fees):
        # explicitly surface "no tuition data" instead of hiding it
        items.append(_fee_item(ProgramFee(program_id=program.id, fee_type="tuition",
                                          amount=None, currency=None, period=None,
                                          status="unavailable"), ctx))
    return items


def get_intakes(db: Session, program_id: uuid.UUID) -> list[dict]:
    program, _, _ = _load_program(db, program_id)
    ctx = _page_context(db, [program.id])
    return [_intake_item(i) for i in ctx["intakes"].get(program.id, [])]


def get_evidence(db: Session, program_id: uuid.UUID, *, page=1, page_size=20) -> dict:
    program, _, _ = _load_program(db, program_id)
    total = db.scalar(select(func.count()).select_from(FactRecord).where(
        FactRecord.entity_type == "program", FactRecord.entity_id == program.id)) or 0
    records = db.scalars(
        select(FactRecord).where(FactRecord.entity_type == "program",
                                 FactRecord.entity_id == program.id)
        .order_by(FactRecord.fact_key, FactRecord.id)
        .offset((page - 1) * page_size).limit(page_size)).all()

    items = []
    for rec in records:
        versions = db.scalars(
            select(FactVersion).where(FactVersion.fact_record_id == rec.id)
            .order_by(FactVersion.version_number.desc())).all()
        ev_rows = db.execute(
            select(FactEvidence, SourceDocument, Source)
            .join(SourceDocument, SourceDocument.id == FactEvidence.source_document_id, isouter=True)
            .join(Source, Source.id == SourceDocument.source_id, isouter=True)
            .where(FactEvidence.fact_version_id.in_([v.id for v in versions]))
        ).all() if versions else []
        items.append({
            "fact_id": rec.id,
            "fact_key": rec.fact_key,
            "applicability_key": rec.applicability_key,
            "current_status": rec.current_status,
            "current_version_id": rec.current_version_id,
            "versions": [
                {"version_number": v.version_number, "value": v.normalized_value_json,
                 "status": v.status, "extraction_method": v.extraction_method,
                 "applicable_intake_year": v.applicable_intake_year,
                 "applicable_intake_term": v.applicable_intake_term,
                 "created_at": v.created_at}
                for v in versions
            ],
            "sources": [
                {"source_id": src.id if src else None,
                 "title": doc.title if doc else None,
                 "url": doc.canonical_url if doc else None,
                 "retrieved_at": doc.retrieved_at if doc else None,
                 "excerpt": ev.evidence_excerpt,
                 "supports_or_conflicts": ev.supports_or_conflicts}
                for ev, doc, src in ev_rows
            ],
        })
    return {"items": items, "page": page, "page_size": page_size, "total_items": total,
            "total_pages": (total + page_size - 1) // page_size}


def get_outcomes(db: Session, program_id: uuid.UUID) -> list[dict]:
    program, _, _ = _load_program(db, program_id)
    rows = db.scalars(
        select(ProgramOutcomeEvidence).where(
            or_(
                ProgramOutcomeEvidence.program_id == program.id,
                and_(ProgramOutcomeEvidence.university_id == program.university_id,
                     ProgramOutcomeEvidence.field_id.is_(None)),
                and_(ProgramOutcomeEvidence.field_id == program.field_id,
                     or_(ProgramOutcomeEvidence.country_code == program.country_code,
                         ProgramOutcomeEvidence.country_code.is_(None))),
                and_(ProgramOutcomeEvidence.country_code == program.country_code,
                     ProgramOutcomeEvidence.field_id.is_(None),
                     ProgramOutcomeEvidence.university_id.is_(None)),
            )
        ).order_by(ProgramOutcomeEvidence.population_scope, ProgramOutcomeEvidence.id)).all()
    return [
        {
            "metric_key": r.metric_key,
            "metric_value": r.metric_value,
            "metric_unit": r.metric_unit,
            "currency": r.currency,
            "cohort_label": r.cohort_label,
            "cohort_year": r.cohort_year,
            "sample_size": r.sample_size,
            "population_scope": r.population_scope,
            "methodology_note": r.methodology_note,
            "applies_to_this_program": r.program_id == program.id,
            "provenance": None,
        }
        for r in rows
    ]
