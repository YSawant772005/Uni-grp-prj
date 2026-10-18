"""Idempotent development seed data.

IMPORTANT — honesty rules for this file:
* Every catalogue row below is a SYNTHETIC DEMO FIXTURE. Universities and programs are
  fictional and carry ``external_identifiers.demo_fixture = true``.
* Every demo source is named "DEMO FIXTURE ..." and points at ``example.invalid`` URLs.
* Fact statuses are only ``candidate`` / ``unverified`` / ``estimated`` — never
  ``verified``. Nothing here may be shown to a user as an official verified fact.
* Official rule resources link to genuine official pages but state no invented values.

Run: ``python -m app.db.seed`` (safe to re-run; existing rows are left untouched).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import slugify
from app.models import (
    Campus,
    City,
    Country,
    FactEvidence,
    FactRecord,
    FactVersion,
    Field,
    FundingOpportunity,
    FxRate,
    LivingCostFact,
    OfficialRuleResource,
    Program,
    ProgramFee,
    ProgramIntake,
    ProgramOutcomeEvidence,
    RecommendationRuleset,
    Role,
    Scholarship,
    ScholarshipEligibilityRule,
    ScholarshipProgramLink,
    Source,
    SourceDocument,
    University,
    User,
    UserRole,
    AdmissionRequirement,
)

DEMO_PASSWORD_ENV = "SEED_ADMIN_PASSWORD"
DEMO_PASSWORD_DEFAULT = "change_me_admin_pw"

COUNTRIES = [
    ("DE", "Germany", "Europe", "https://www.daad.de/en/", "https://www.make-it-in-germany.com/en/"),
    ("NL", "Netherlands", "Europe", "https://www.studyinholland.nl/", "https://www.government.nl/topics/immigration"),
    ("IE", "Ireland", "Europe", "https://www.educationinireland.com/", "https://www.irishimmigration.ie/"),
    ("GB", "United Kingdom", "Europe", "https://www.gov.uk/study-in-the-uk", "https://www.gov.uk/browse/visas-immigration"),
    ("US", "United States", "North America", "https://educationusa.state.gov/", "https://travel.state.gov/"),
    ("AU", "Australia", "Oceania", "https://studyaustralia.gov.au/", "https://immi.homeaffairs.gov.au/"),
    ("CA", "Canada", "North America", "https://www.educanada.ca/", "https://www.canada.ca/en/immigration-refugees-citizenship.html"),
]

CITIES = [
    ("DE", "Berlin", "berlin"), ("DE", "Munich", "munich"),
    ("NL", "Amsterdam", "amsterdam"), ("NL", "Delft", "delft"),
    ("IE", "Dublin", "dublin"), ("GB", "London", "london"),
    ("US", "Boston", "boston"), ("AU", "Sydney", "sydney"), ("CA", "Toronto", "toronto"),
]

FIELDS = [
    ("computer_science", "Computer Science"),
    ("artificial_intelligence", "Artificial Intelligence"),
    ("data_science", "Data Science"),
    ("business_analytics", "Business Analytics"),
    ("robotics", "Robotics"),
    ("mechanical_engineering", "Mechanical Engineering"),
    ("finance", "Finance"),
]

SCORING_WEIGHTS = {
    "academic_fit": "0.20",
    "career_fit": "0.20",
    "affordability": "0.20",
    "quality": "0.15",
    "outcomes": "0.15",
    "destination": "0.10",
}


def seed_roles(session: Session) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for key, desc in [
        ("student", "Student applicant"),
        ("reviewer", "Data reviewer"),
        ("admin", "Administrator"),
    ]:
        role = session.scalar(select(Role).where(Role.key == key))
        if role is None:
            role = Role(key=key, description=desc)
            session.add(role)
            session.flush()
        roles[key] = role
    return roles


def seed_demo_users(session: Session, roles: dict[str, Role]) -> None:
    if not settings.seed_demo_data:
        return
    password = hash_password(DEMO_PASSWORD_DEFAULT)
    for email, name, role_keys in [
        ("admin@demo.local", "Demo Admin", ["admin", "reviewer"]),
        ("student@demo.local", "Demo Student", ["student"]),
    ]:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, display_name=name, password_hash=password)
            session.add(user)
            session.flush()
        for rk in role_keys:
            exists = session.scalar(
                select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == roles[rk].id)
            )
            if exists is None:
                session.add(UserRole(user_id=user.id, role_id=roles[rk].id))


def seed_reference(session: Session) -> None:
    for code, name, region, study_url, immig_url in COUNTRIES:
        if session.get(Country, code) is None:
            session.add(
                Country(code=code, name=name, region=region,
                        official_study_url=study_url, official_immigration_url=immig_url)
            )
    session.flush()
    for code, name, slug in CITIES:
        exists = session.scalar(select(City).where(City.country_code == code, City.slug == slug))
        if exists is None:
            session.add(City(country_code=code, name=name, slug=slug))
    for key, display in FIELDS:
        if session.scalar(select(Field).where(Field.key == key)) is None:
            session.add(Field(key=key, display_name=display))


def _get_demo_source(session: Session) -> SourceDocument:
    """One shared demo source + document used as evidence for every seeded fact."""
    source = session.scalar(select(Source).where(Source.name == "DEMO FIXTURE — Example University Pages"))
    if source is None:
        source = Source(
            name="DEMO FIXTURE — Example University Pages",
            base_url="https://example.invalid/demo-fixture",
            source_type="other",
            authority_tier=4,
            owner_or_publisher="Synthetic demo data (not a real publisher)",
            allowed_use_policy="manual_reference",
            license_notes="Synthetic fixture created by the project; not licensed third-party data.",
            enabled=True,
            metadata_json={"demo_fixture": True},
        )
        session.add(source)
        session.flush()
    doc = session.scalar(select(SourceDocument).where(SourceDocument.source_id == source.id))
    if doc is None:
        doc = SourceDocument(
            source_id=source.id,
            canonical_url="https://example.invalid/demo-fixture/admissions",
            title="DEMO FIXTURE admissions page (synthetic)",
            content_excerpt="Synthetic demo content. Not an official publication.",
            fetch_status="fetched",
        )
        session.add(doc)
        session.flush()
    return doc


def make_fact(
    session: Session,
    doc: SourceDocument,
    entity_type: str,
    entity_id,
    fact_key: str,
    value: dict,
    status: str,
    *,
    applicability: str = "",
) -> FactRecord:
    """Create fact_record + v1 fact_version + evidence. Idempotent per entity/fact/applicability."""
    rec = session.scalar(
        select(FactRecord).where(
            FactRecord.entity_type == entity_type,
            FactRecord.entity_id == entity_id,
            FactRecord.fact_key == fact_key,
            FactRecord.applicability_key == applicability,
        )
    )
    if rec is not None:
        return rec
    rec = FactRecord(
        entity_type=entity_type, entity_id=entity_id, fact_key=fact_key,
        applicability_key=applicability, current_status=status,
    )
    session.add(rec)
    session.flush()
    ver = FactVersion(
        fact_record_id=rec.id, version_number=1, value_json=value,
        normalized_value_json=value, status=status, extraction_method="manual",
    )
    session.add(ver)
    session.flush()
    rec.current_version_id = ver.id
    session.add(
        FactEvidence(
            fact_version_id=ver.id, source_document_id=doc.id,
            evidence_excerpt="Synthetic demo fixture — not an official source.",
            supports_or_conflicts="supports",
        )
    )
    session.flush()
    return rec


# name, country, city, recognition  -> demo universities
DEMO_UNIVERSITIES = [
    ("Demo Technical University of Berlin", "DE", "berlin"),
    ("Demo Munich Institute of Technology", "DE", "munich"),
    ("Demo University of Amsterdam", "NL", "amsterdam"),
    ("Demo Delft Institute of Technology", "NL", "delft"),
    ("Demo Dublin Business School", "IE", "dublin"),
    ("Demo London School of Computing", "GB", "london"),
]

# university slug, program name, field key, months, tuition EUR/yr (None = unknown),
# deadline, extra prerequisites
DEMO_PROGRAMS = [
    ("demo-technical-university-of-berlin", "MSc Artificial Intelligence", "artificial_intelligence", 24, None, True),
    ("demo-technical-university-of-berlin", "MSc Data Science", "data_science", 18, 15000, True),
    ("demo-munich-institute-of-technology", "MSc Robotics", "robotics", 24, 12000, True),
    ("demo-university-of-amsterdam", "MSc Computer Science", "computer_science", 12, 18500, False),
    ("demo-university-of-amsterdam", "MSc Business Analytics", "business_analytics", 12, 17000, False),
    ("demo-delft-institute-of-technology", "MSc Data Science", "data_science", 24, 16000, True),
    ("demo-dublin-business-school", "MSc Business Analytics", "business_analytics", 12, 14500, False),
    ("demo-london-school-of-computing", "MSc Artificial Intelligence", "artificial_intelligence", 12, 22000, True),
    ("demo-london-school-of-computing", "MSc Computer Science", "computer_science", 12, 21000, False),
]


def seed_demo_catalogue(session: Session) -> None:
    doc = _get_demo_source(session)
    field_by_key = {f.key: f for f in session.scalars(select(Field))}

    unis: dict[str, University] = {}
    campuses: dict[str, Campus] = {}
    for name, country, city_slug in DEMO_UNIVERSITIES:
        uslug = slugify(name)
        u = session.scalar(select(University).where(University.slug == uslug))
        if u is None:
            u = University(
                canonical_name=name, slug=uslug, country_code=country,
                institution_type="public", recognition_status="unknown",
                external_identifiers={"demo_fixture": True},
            )
            session.add(u)
            session.flush()
        unis[uslug] = u
        city = session.scalar(select(City).where(City.country_code == country, City.slug == city_slug))
        campus = None
        if city is not None:
            campus = session.scalar(select(Campus).where(
                Campus.university_id == u.id, Campus.city_id == city.id))
            if campus is None:
                campus = Campus(university_id=u.id, name=f"{u.canonical_name} Main Campus",
                                city_id=city.id)
                session.add(campus)
                session.flush()
        campuses[uslug] = campus

    for uni_slug, name, field_key, months, tuition_eur, needs_prereqs in DEMO_PROGRAMS:
        prog = session.scalar(
            select(Program).where(
                Program.university_id == unis[uni_slug].id,
                Program.slug == slugify(name),
                Program.degree_level == "masters",
            )
        )
        if prog is None:
            country = unis[uni_slug].country_code
            prog = Program(
                university_id=unis[uni_slug].id,
                campus_id=campuses[uni_slug].id if campuses.get(uni_slug) else None,
                country_code=country,
                canonical_name=name,
                slug=slugify(name),
                degree_level="masters",
                field_id=field_by_key[field_key].id,
                description="Synthetic demo program fixture. Not an official program listing.",
                official_program_url="https://example.invalid/demo-fixture/program",
                delivery_language="en",
                study_mode="full_time",
                duration_min_months=months,
                duration_max_months=months,
                publication_status="published",
            )
            session.add(prog)
            session.flush()

            intake = ProgramIntake(
                program_id=prog.id, intake_year=2027, intake_term="fall",
                application_open_date=date(2026, 9, 1), application_deadline=date(2027, 1, 15),
                start_date=date(2027, 9, 1), is_open_for_applications=True, status="candidate",
            )
            session.add(intake)
            session.flush()

            # requirements — all linked to demo evidence; statuses are candidate/unverified
            en_fact = make_fact(session, doc, "program", prog.id, "english_ielts_overall",
                                {"value": 6.5, "unit": "band"}, "unverified")
            grade_fact = make_fact(session, doc, "program", prog.id, "min_gpa",
                                   {"value": 3.0, "scale": "4.0"}, "unverified")
            session.add(AdmissionRequirement(
                program_id=prog.id, requirement_type="language_test",
                requirement_key="english_ielts_overall", operator="gte",
                expected_value={"value": 6.5, "unit": "band", "test": "ielts"},
                is_mandatory=True, group_key="english_language", group_operator="AND",
                applicability_notes="Demo fixture requirement.",
                source_fact_id=en_fact.id,
            ))
            session.add(AdmissionRequirement(
                program_id=prog.id, requirement_type="grade", requirement_key="min_gpa",
                operator="gte", expected_value={"value": 3.0, "scale": "4.0"},
                is_mandatory=True, group_key="academics", group_operator="AND",
                source_fact_id=grade_fact.id,
            ))
            if needs_prereqs:
                for pk, plabel in [("calculus", "Calculus"), ("programming", "Programming")]:
                    f = make_fact(session, doc, "program", prog.id, f"prereq_{pk}",
                                  {"subject": pk, "min_credits": 6}, "candidate")
                    session.add(AdmissionRequirement(
                        program_id=prog.id, requirement_type="prerequisite_course",
                        requirement_key=f"prereq_{pk}", operator="completed_course",
                        expected_value={"subject": plabel, "min_credits": 6},
                        is_mandatory=True, group_key="prerequisites", group_operator="AND",
                        source_fact_id=f.id,
                    ))

            # fees — tuition NULL + status 'unavailable' exercises "missing is not free"
            if tuition_eur is None:
                fee_fact = make_fact(session, doc, "program", prog.id, "tuition_annual",
                                     {"amount": None, "status": "unavailable"}, "unavailable")
                session.add(ProgramFee(
                    program_id=prog.id, program_intake_id=intake.id, fee_type="tuition",
                    amount=None, currency=None, period="academic_year", academic_year="2027-2028",
                    student_category="international", is_mandatory=True,
                    status="unavailable", fact_id=fee_fact.id,
                ))
            else:
                fee_fact = make_fact(session, doc, "program", prog.id, "tuition_annual",
                                     {"amount": str(tuition_eur), "currency": "EUR",
                                      "period": "academic_year"}, "estimated")
                session.add(ProgramFee(
                    program_id=prog.id, program_intake_id=intake.id, fee_type="tuition",
                    amount=Decimal(tuition_eur), currency="EUR", period="academic_year",
                    academic_year="2027-2028", student_category="international",
                    is_mandatory=True, status="estimated", fact_id=fee_fact.id,
                ))
            mgmt_fact = make_fact(session, doc, "program", prog.id, "student_union_fee",
                                  {"amount": "300", "currency": "EUR", "period": "semester"},
                                  "estimated")
            session.add(ProgramFee(
                program_id=prog.id, program_intake_id=intake.id, fee_type="mandatory_fee",
                amount=Decimal("300"), currency="EUR", period="semester",
                academic_year="2027-2028", is_mandatory=True, status="estimated",
                fact_id=mgmt_fact.id,
            ))
        elif prog.campus_id is None and campuses.get(uni_slug) is not None:
            # backfill: programs seeded before campuses existed
            prog.campus_id = campuses[uni_slug].id


def seed_funding(session: Session) -> None:
    doc = _get_demo_source(session)
    if session.scalar(select(Scholarship).where(Scholarship.name == "Demo Merit Scholarship")) is None:
        schol = Scholarship(
            name="Demo Merit Scholarship", provider_name="Demo Foundation (synthetic)",
            official_url="https://example.invalid/demo-fixture/merit-scholarship",
            country_code="DE", award_type="merit", amount_min=Decimal("5000"),
            amount_max=Decimal("10000"), currency="EUR", coverage_type="partial",
            renewable=True, deadline=date(2027, 3, 1), status="candidate",
        )
        session.add(schol)
        session.flush()
        fact = make_fact(session, doc, "scholarship", schol.id, "award_amount",
                         {"min": "5000", "max": "10000", "currency": "EUR"}, "candidate")
        schol.fact_id = fact.id
        session.add(ScholarshipEligibilityRule(
            scholarship_id=schol.id, rule_key="min_gpa", operator="gte",
            expected_value={"value": 3.3, "scale": "4.0"}, is_mandatory=True,
            source_fact_id=fact.id,
        ))
        session.add(ScholarshipEligibilityRule(
            scholarship_id=schol.id, rule_key="nationality", operator="in",
            expected_value={"values": ["IN", "other"]}, is_mandatory=True,
        ))
        for prog in session.scalars(select(Program).where(Program.country_code == "DE")):
            session.add(ScholarshipProgramLink(
                scholarship_id=schol.id, program_id=prog.id, link_type="university_wide"
            ))
    if session.scalar(select(FundingOpportunity).where(FundingOpportunity.name == "Demo National Fellowship")) is None:
        opp = FundingOpportunity(
            name="Demo National Fellowship", provider_name="Demo Education Board (synthetic)",
            opportunity_type="fellowship",
            official_url="https://example.invalid/demo-fixture/fellowship",
            eligible_countries=["DE", "NL", "IE"], eligible_nationalities=["IN"],
            study_levels=["masters"], field_eligibility=["data_science", "artificial_intelligence"],
            award_summary="Synthetic demo fellowship fixture.",
            opening_date=date(2026, 11, 1), deadline=date(2027, 4, 30), status="candidate",
        )
        session.add(opp)


def seed_destinations(session: Session) -> None:
    doc = _get_demo_source(session)
    for code, name, slug in CITIES:
        city = session.scalar(select(City).where(City.country_code == code, City.slug == slug))
        if city is None:
            continue
        for cat, lo, mid, hi in [
            ("housing", 600, 900, 1400), ("food", 200, 300, 450), ("transport", 50, 80, 120)
        ]:
            exists = session.scalar(
                select(LivingCostFact).where(
                    LivingCostFact.city_id == city.id, LivingCostFact.cost_category == cat
                )
            )
            if exists is None:
                fact = make_fact(session, doc, "city", city.id, f"living_cost_{cat}",
                                 {"min": str(lo), "typical": str(mid), "max": str(hi)}, "estimated")
                session.add(LivingCostFact(
                    city_id=city.id, cost_category=cat, amount_min=Decimal(lo),
                    amount_typical=Decimal(mid), amount_max=Decimal(hi), currency="EUR",
                    period="month", effective_year=2026, fact_id=fact.id,
                ))
    rules = [
        ("DE", "student_visa", "German student visa information (official)",
         "https://www.make-it-in-germany.com/en/visa-residence/types/studying"),
        ("DE", "post_study_work", "German post-study work residence options (official)",
         "https://www.make-it-in-germany.com/en/visa-residence/types/working"),
        ("GB", "student_visa", "UK student visa: money you need (official)",
         "https://www.gov.uk/student-visa/money"),
        ("GB", "post_study_work", "UK Graduate visa overview (official)",
         "https://www.gov.uk/graduate-visa"),
    ]
    for code, rtype, title, url in rules:
        exists = session.scalar(select(OfficialRuleResource).where(
            OfficialRuleResource.country_code == code,
            OfficialRuleResource.rule_type == rtype,
            OfficialRuleResource.official_url == url,
        ))
        if exists is None:
            session.add(OfficialRuleResource(
                country_code=code, rule_type=rtype, title=title, official_url=url,
                summary="Official resource link. Check the current rules on the official page; "
                        "no value from this page is asserted here.",
            ))
    # subject-level outcome evidence — explicitly scoped, never presented as program outcomes
    for field_key, scope, val, unit, note in [
        ("data_science", "subject", 78, "percent",
         "Synthetic demo fixture at subject level; not a program placement rate."),
        ("artificial_intelligence", "country", 82, "percent",
         "Synthetic demo fixture at country level; not a program placement rate."),
    ]:
        field = session.scalar(select(Field).where(Field.key == field_key))
        exists = session.scalar(select(ProgramOutcomeEvidence).where(
            ProgramOutcomeEvidence.field_id == field.id, ProgramOutcomeEvidence.metric_key == "employment_rate"
        ))
        if exists is None:
            fact = make_fact(session, doc, "outcome", field.id, "employment_rate",
                             {"value": str(val), "unit": unit}, "estimated")
            session.add(ProgramOutcomeEvidence(
                field_id=field.id, country_code="DE", metric_key="employment_rate",
                metric_value=Decimal(val), metric_unit=unit, cohort_year=2025,
                sample_size=None, population_scope=scope, methodology_note=note, fact_id=fact.id,
            ))


def seed_ruleset(session: Session) -> None:
    if session.scalar(select(RecommendationRuleset).where(RecommendationRuleset.version == "eligibility-v1")) is None:
        session.add(RecommendationRuleset(
            version="eligibility-v1",
            description="Initial deterministic eligibility rules and starting fit weights.",
            eligibility_config={
                "operators": ["gte", "gt", "lte", "lt", "eq", "in", "contains",
                              "completed_course", "any_of", "all_of", "manual_review"],
                "mandatory_unknown_blocks_eligible": True,
                "grade_scale_note": "Grade values are evaluated against the scale they were entered in.",
            },
            scoring_config={
                "weights": SCORING_WEIGHTS,
                "tiers": {"ambitious": 3, "target": 5, "safer_fit": 3},
            },
            is_active=True,
            activated_at=None,
        ))


# Fixed dated reference FX rates (units of each currency per 1 EUR). Development fixture;
# conversions built on these are labelled estimated and carry the rate date.
FX_REFERENCE_PER_EUR = {
    "EUR": Decimal("1.0"), "USD": Decimal("1.09"), "GBP": Decimal("0.83"),
    "INR": Decimal("90.5"), "AUD": Decimal("1.65"), "CAD": Decimal("1.48"),
}
FX_RATE_DATE = date(2026, 10, 1)


def seed_fx_rates(session: Session) -> None:
    for base, base_val in FX_REFERENCE_PER_EUR.items():
        for quote, quote_val in FX_REFERENCE_PER_EUR.items():
            if base == quote:
                continue
            exists = session.scalar(select(FxRate).where(
                FxRate.base_currency == base, FxRate.quote_currency == quote,
                FxRate.rate_date == FX_RATE_DATE))
            if exists is None:
                session.add(FxRate(
                    base_currency=base, quote_currency=quote,
                    rate=(quote_val / base_val).quantize(Decimal("0.00000001")),
                    rate_date=FX_RATE_DATE, source="seed_reference",
                ))


def run_seed(session: Session) -> dict[str, int]:
    roles = seed_roles(session)
    seed_demo_users(session, roles)
    seed_reference(session)
    seed_demo_catalogue(session)
    seed_funding(session)
    seed_destinations(session)
    seed_ruleset(session)
    seed_fx_rates(session)
    session.commit()
    counts = {
        "countries": session.query(Country).count(),
        "fields": session.query(Field).count(),
        "universities": session.query(University).count(),
        "programs": session.query(Program).count(),
        "fees": session.query(ProgramFee).count(),
        "requirements": session.query(AdmissionRequirement).count(),
        "scholarships": session.query(Scholarship).count(),
        "living_cost_facts": session.query(LivingCostFact).count(),
        "rulesets": session.query(RecommendationRuleset).count(),
        "fact_records": session.query(FactRecord).count(),
    }
    return counts


if __name__ == "__main__":
    from app.db.session import SessionLocal

    with SessionLocal() as s:
        print("Seed complete:", run_seed(s))

