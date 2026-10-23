"""Schema integrity tests: FKs, uniqueness, nullability, CHECK/enum constraints,
money honesty, fact history, and seed-data honesty rules."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import (
    Comparison,
    FactRecord,
    FactReviewEvent,
    FactVersion,
    Program,
    ProgramFee,
    ProgramIntake,
    SavedProgram,
    Source,
    StudentProfile,
    University,
    User,
)


def _first_program(db) -> Program:
    return db.query(Program).first()


def _first_user(db) -> User:
    return db.query(User).filter(User.email == "student@example.com").one()


class TestForeignKeys:
    def test_program_requires_existing_university(self, db):
        db.add(
            Program(
                university_id=uuid.uuid4(), country_code="DE",
                canonical_name="Ghost", slug="ghost", degree_level="masters",
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_unknown_fee_status_rejected_by_db_check(self, db):
        program = _first_program(db)
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "INSERT INTO program_fees (id, program_id, fee_type, status, created_at, updated_at) "
                    "VALUES (:id, :pid, 'tuition', 'definitely_verified', now(), now())"
                ),
                {"id": str(uuid.uuid4()), "pid": str(program.id)},
            )
        db.rollback()


class TestUniqueness:
    def test_similar_program_titles_are_not_database_identity(self, db):
        program = _first_program(db)
        second = Program(
            university_id=program.university_id, country_code=program.country_code,
            canonical_name=program.canonical_name, slug=program.slug,
            degree_level=program.degree_level,
            official_program_url="https://different.example.edu/program",
        )
        db.add(second)
        db.flush()
        assert second.id != program.id

    def test_user_email_unique(self, db, make_user):
        make_user(email="dup@test.local")
        with pytest.raises(IntegrityError):
            make_user(email="dup@test.local")
        db.rollback()

    def test_saved_program_idempotent(self, db):
        user = _first_user(db)
        program = _first_program(db)
        db.add(SavedProgram(user_id=user.id, program_id=program.id))
        db.flush()
        db.add(SavedProgram(user_id=user.id, program_id=program.id))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_fact_logical_identity_and_applicability(self, db):
        program = _first_program(db)
        for applicability in ("", "2027-fall"):
            db.add(
                FactRecord(
                    entity_type="program", entity_id=program.id,
                    fact_key="acceptance_rate", applicability_key=applicability,
                    current_status="candidate",
                )
            )
        db.flush()
        db.add(
            FactRecord(
                entity_type="program", entity_id=program.id,
                fact_key="acceptance_rate", applicability_key="",
                current_status="candidate",
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


class TestMoneyAndScaleRules:
    def test_amount_requires_currency_and_period(self, db):
        program = _first_program(db)
        db.add(
            ProgramFee(
                program_id=program.id, fee_type="tuition", amount=1000,
                currency=None, period=None, status="estimated",
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_missing_amount_stays_null_not_zero(self, db):
        program = _first_program(db)
        fee = ProgramFee(
            program_id=program.id, fee_type="tuition", amount=None,
            currency=None, period="academic_year", status="unavailable",
        )
        db.add(fee)
        db.flush()
        assert fee.amount is None and fee.status == "unavailable"
        db.rollback()

    def test_negative_amount_rejected(self, db):
        program = _first_program(db)
        db.add(
            ProgramFee(
                program_id=program.id, fee_type="tuition", amount=-1,
                currency="EUR", period="academic_year", status="estimated",
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_profile_budget_requires_currency_and_basis(self, db, make_profile):
        with pytest.raises(IntegrityError):
            make_profile(budget_amount=100000)
        db.rollback()

    def test_grade_must_fit_declared_scale(self, db, make_profile):
        with pytest.raises(IntegrityError):
            make_profile(
                grade_value=95, grade_scale_min=0, grade_scale_max=10, grade_system="percentage"
            )
        db.rollback()


class TestIntakeRules:
    def test_deadline_before_open_date_rejected(self, db):
        program = _first_program(db)
        db.add(
            ProgramIntake(
                program_id=program.id, intake_year=2030, intake_term="spring",
                application_open_date="2029-05-01", application_deadline="2029-01-01",
                status="candidate",
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


class TestFactHistory:
    def test_version_number_unique_per_fact(self, db):
        program = _first_program(db)
        rec = FactRecord(
            entity_type="program", entity_id=program.id, fact_key="test_fact",
            applicability_key="", current_status="candidate",
        )
        db.add(rec)
        db.flush()
        db.add(FactVersion(fact_record_id=rec.id, version_number=1, status="candidate"))
        db.flush()
        db.add(FactVersion(fact_record_id=rec.id, version_number=1, status="candidate"))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_reject_requires_reason(self, db):
        user = _first_user(db)
        program = _first_program(db)
        rec = FactRecord(
            entity_type="program", entity_id=program.id, fact_key="reject_test",
            applicability_key="", current_status="candidate",
        )
        db.add(rec)
        db.flush()
        db.add(
            FactReviewEvent(
                fact_record_id=rec.id, reviewer_user_id=user.id,
                action="reject", reason=None,
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_current_version_must_exist(self, db):
        program = _first_program(db)
        db.add(
            FactRecord(
                entity_type="program", entity_id=program.id, fact_key="circular_test",
                applicability_key="", current_status="candidate",
                current_version_id=uuid.uuid4(),
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


class TestSeedHonesty:
    def test_no_seeded_fact_is_marked_verified(self, db):
        statuses = {s for (s,) in db.query(FactRecord.current_status).distinct()}
        assert "verified" not in statuses

    def test_demo_universities_are_flagged_as_fixtures(self, db):
        unis = db.query(University).all()
        assert unis and all(u.external_identifiers and u.external_identifiers.get("demo_fixture") for u in unis)

    def test_demo_sources_are_demo_labelled(self, db):
        sources = db.query(Source).all()
        assert sources and all(s.name.startswith("DEMO FIXTURE") for s in sources)

    def test_every_seed_fee_with_amount_is_non_verified(self, db):
        fees = db.query(ProgramFee).filter(ProgramFee.amount.is_not(None)).all()
        assert fees and all(f.status in ("estimated", "unverified", "stale") for f in fees)

    def test_active_ruleset_exists(self, db):
        row = db.execute(
            text("SELECT count(*) FROM recommendation_rulesets WHERE is_active = true AND version = 'eligibility-v1'")
        ).scalar()
        assert row == 1

    def test_one_program_has_unknown_tuition(self, db):
        count = db.query(ProgramFee).filter(ProgramFee.fee_type == "tuition", ProgramFee.amount.is_(None)).count()
        assert count >= 1, "seed must exercise the missing-tuition-is-not-free case"


class TestOwnershipModel:
    def test_comparisons_are_user_scoped(self, db, make_user):
        a, b = make_user(), make_user()
        comp = Comparison(user_id=a.id, title="My list")
        db.add(comp)
        db.flush()
        assert comp.user_id == a.id and comp.user_id != b.id

    def test_scholarship_links_reference_real_programs(self, db):
        links = db.execute(text("SELECT scholarship_id, program_id FROM scholarship_program_links")).all()
        program_ids = {p.id for p in db.query(Program).all()}
        assert links and all(l[1] in program_ids for l in links)

    def test_profile_user_is_unique(self, db, make_profile):
        user, _ = make_profile()
        db.add(StudentProfile(user_id=user.id))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
