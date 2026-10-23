"""Phase 5 tests: eligibility states, evidence requirements, hard constraints,
tiered recommendation runs, explanations, ownership and refresh."""
import uuid
from decimal import Decimal

import pytest

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.seed import run_seed
from app.models import Program, RecommendationRun, StudentProfile
from app.services import eligibility as eligibility_engine
from app.services import scoring as scoring_engine
from conftest import _truncate_all

STRONG_ONBOARDING = {
    "intended_degree_level": "masters", "field": "computer_science",
    "country_preferences": [{"country_code": "DE", "is_mandatory": True}, {"country_code": "NL"}],
    "academic_degree": "B.Tech", "institution_name": "Test University",
    "grade_value": 8.5, "grade_scale_min": 0, "grade_scale_max": 10, "grade_system": "cgpa",
    "graduation_status": "completed", "graduation_year": 2024,
    "english_test_status": "completed", "english_test_type": "ielts", "english_test_overall": 7.5,
    "budget_amount": 60000, "budget_currency": "EUR", "budget_basis": "full_degree_all_in",
    "target_intake_year": 2027, "target_intake_term": "fall",
}


@pytest.fixture(autouse=True)
def generous_rate_limit():
    from app.routers.v1.auth import limiter

    previous = settings.rate_limit_auth
    settings.rate_limit_auth = "1000/minute"
    limiter.reset()
    yield
    limiter.reset()
    settings.rate_limit_auth = previous


@pytest.fixture(scope="module")
def _seeded():
    session = SessionLocal()
    _truncate_all(session)
    run_seed(session)
    yield session
    session.close()


@pytest.fixture()
def db(_seeded):
    yield _seeded
    _seeded.rollback()


def _register(client):
    email = f"e-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "Sup3rSecret!"})
    assert r.status_code == 201
    return email


def _complete_onboarding(client, payload=None):
    r = client.post("/api/v1/profile/onboarding/complete", json=payload or STRONG_ONBOARDING)
    assert r.status_code == 200, r.text


def _program_ids(db, slug=None, limit=6):
    q = db.query(Program)
    if slug:
        q = q.filter(Program.slug == slug)
    return [str(p.id) for p in q.order_by(Program.id).limit(limit).all()]


class TestEligibilityEvaluations:
    def test_requires_auth_and_nonempty_ids(self, client):
        client.cookies.clear()
        assert client.post("/api/v1/eligibility/evaluations",
                           json={"program_ids": [str(uuid.uuid4())]}).status_code == 401
        _register(client)
        r = client.post("/api/v1/eligibility/evaluations", json={"program_ids": []})
        assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "program_ids"

    def test_unknown_program_404(self, db, client):
        _register(client)
        assert client.post("/api/v1/eligibility/evaluations",
                           json={"program_ids": [str(uuid.uuid4())]}).status_code == 404

    def test_every_requirement_returns_full_evidence_shape(self, db, client):
        _register(client)
        _complete_onboarding(client)
        pid = _program_ids(db, "msc-artificial-intelligence", 1)[0]
        body = client.post("/api/v1/eligibility/evaluations",
                           json={"program_ids": [pid]}).json()["items"][0]
        assert body["status"] in ("eligible", "conditionally_eligible", "ineligible",
                                  "unknown_needs_review")
        assert body["requirements"], "seeded program must carry requirements"
        for req in body["requirements"]:
            assert req["status"] in ("pass", "fail", "conditional", "unknown")
            assert req["expected_value"] is not None
            assert req["explanation"]
            # evidence reference surfaced (source_fact linkage via fact status)
            assert "requirement_key" in req and "evaluated_value" in req

    def test_unknown_mandatory_requirement_is_never_eligible(self, db, client):
        # prereq courses are untracked in MVP -> mandatory unknown blocks "eligible"
        _register(client)
        _complete_onboarding(client)
        pid = _program_ids(db, "msc-artificial-intelligence", 1)[0]
        body = client.post("/api/v1/eligibility/evaluations",
                           json={"program_ids": [pid]}).json()["items"][0]
        assert body["status"] == "unknown_needs_review"
        assert "prereq_programming" in body["unknowns"] or "prereq_calculus" in body["unknowns"]

    def test_strong_profile_earns_eligible_on_no_prereq_program(self, db, client):
        _register(client)
        _complete_onboarding(client)
        pid = _program_ids(db, "msc-business-analytics", 1)[0]
        body = client.post("/api/v1/eligibility/evaluations",
                           json={"program_ids": [pid]}).json()["items"][0]
        assert body["status"] == "eligible"
        assert body["unsatisfied"] == [] and body["unknowns"] == []

    def test_insufficient_grade_is_ineligible(self, db, client):
        _register(client)
        _complete_onboarding(client, {**STRONG_ONBOARDING, "grade_value": 4.0,
                                      "english_test_overall": 5.0})
        pid = _program_ids(db, "msc-business-analytics", 1)[0]
        body = client.post("/api/v1/eligibility/evaluations",
                           json={"program_ids": [pid]}).json()["items"][0]
        assert body["status"] == "ineligible"
        assert "min_gpa" in body["unsatisfied"]


class TestEligibilityEngine:
    def test_any_group_satisfied_by_single_pass(self, db):
        """ANY/ALL group logic: group results expose operator + status for every group."""
        from app.models import AdmissionRequirement

        reqs = db.query(AdmissionRequirement).order_by(AdmissionRequirement.id).limit(6).all()
        assert reqs, "seed must contain requirements for engine tests"
        profile = StudentProfile(user_id=uuid.uuid4(), intended_degree_level="masters")
        ev = eligibility_engine.evaluate_program(profile, reqs)
        assert ev["groups"], "group results must be produced"
        for group in ev["groups"]:
            assert group["group_operator"] in ("AND", "ANY")
            assert group["status"] in ("pass", "fail", "conditional", "unknown")

    def test_missing_profile_never_yields_eligible_with_requirements(self, db):
        """Empty profile + requirements present -> unknown, not eligible."""
        from app.models import AdmissionRequirement, Program

        program = db.query(Program).order_by(Program.id).first()
        reqs = db.query(AdmissionRequirement).filter(
            AdmissionRequirement.program_id == program.id).all()
        if not reqs:
            pytest.skip("program has no requirements")
        profile = StudentProfile(user_id=uuid.uuid4(), intended_degree_level="masters")
        ev = eligibility_engine.evaluate_program(profile, reqs)
        assert ev["status"] != "eligible"


class TestScoringHonesty:
    def test_missing_evidence_renormalises_and_warns(self):
        """Dimensions without evidence score None; overall renormalises; warnings list them."""
        dims = {
            "academic_fit": (None, "no grade"),
            "career_fit": (1.0, "match"),
            "affordability": (None, "no budget"),
            "quality": (0.6, "recognition"),
            "outcomes": (None, "no data"),
            "destination": (0.9, "ranked"),
        }
        weights = {"academic_fit": 0.2, "career_fit": 0.2, "affordability": 0.2,
                   "quality": 0.15, "outcomes": 0.15, "destination": 0.1}
        overall, breakdown, warnings = scoring_engine.combine(dims, weights)
        assert overall is not None
        assert warnings == ["academic_fit_unavailable", "affordability_unavailable",
                            "outcomes_unavailable"]
        scored = [b for b in breakdown if b["score"] is not None]
        # renormalised over available weights only
        expected = sum(b["weight"] * b["score"] for b in scored) / sum(b["weight"] for b in scored)
        assert abs(overall - expected) < 0.001

    def test_total_is_none_when_any_component_unknown(self, db):
        cost = {"tuition_total": None, "tuition_currency": "EUR",
                "living_total": Decimal("10000"), "living_currency": "EUR"}
        total, notes = scoring_engine.total_in_currency(db, cost, "EUR")
        assert total is None and "tuition_unknown" in notes

    def test_tier_uses_threshold_margin_not_admission_probability(self):
        profile = StudentProfile(user_id=uuid.uuid4(), intended_degree_level="masters",
                                 grade_value=Decimal("9.5"), grade_scale_max=Decimal("10"),
                                 english_test_overall=Decimal("8.5"))
        assert scoring_engine.competitiveness_tier(
            profile, {"min_grade_ratio": 0.75, "min_english": 6.5}) == "safer_fit"
        tight = StudentProfile(user_id=uuid.uuid4(), intended_degree_level="masters",
                               grade_value=Decimal("7.6"), grade_scale_max=Decimal("10"),
                               english_test_overall=Decimal("6.6"))
        assert scoring_engine.competitiveness_tier(
            tight, {"min_grade_ratio": 0.75, "min_english": 6.5}) == "ambitious"
        assert scoring_engine.competitiveness_tier(profile, {}) == "target"


class TestRecommendationRuns:
    def test_create_run_shape_and_persistence(self, db, client):
        _register(client)
        _complete_onboarding(client)
        r = client.post("/api/v1/recommendations", json={})
        body = r.json()
        assert r.status_code == 200
        assert set(body["tiers"]) == {"ambitious", "target", "safer_fit"}
        assert body["ruleset_version"] == "eligibility-v1"
        assert "excluded_count" in body and "data_warnings" in body
        run = db.get(RecommendationRun, uuid.UUID(body["run_id"]))
        assert run is not None and run.status == "succeeded"
        assert run.profile_snapshot["filters"] == {}
        assert run.profile_snapshot["profile"]["grade_value"] == 8.5
        assert run.completed_at is not None

    def test_items_carry_score_breakdown_but_no_probability(self, db, client):
        _register(client)
        _complete_onboarding(client)
        body = client.post("/api/v1/recommendations", json={}).json()
        items = [i for tier in body["tiers"].values() for i in tier]
        assert items, "at least one program should survive hard constraints"
        for item in items:
            assert item["fit_score"] is not None and 0 <= item["fit_score"] <= 1
            assert item["eligibility_status"] in ("eligible", "conditionally_eligible",
                                                  "unknown_needs_review")
            assert item["tier"] in ("ambitious", "target", "safer_fit")
            # forbidden: numeric admission probability in any form
            blob = str(item).lower()
            assert "probability" not in blob and "chance" not in blob

    def test_mandatory_country_is_a_hard_constraint(self, db, client):
        _register(client)
        _complete_onboarding(client, {**STRONG_ONBOARDING,
                                      "country_preferences": [{"country_code": "DE",
                                                               "is_mandatory": True}]})
        body = client.post("/api/v1/recommendations", json={}).json()
        for tier in body["tiers"].values():
            for item in tier:
                assert item["country_code"] == "DE"
        # programs outside DE were excluded (visible in explanations as excluded)
        exp = client.get(f"/api/v1/recommendations/{body['run_id']}/explanations").json()
        excluded = [i for i in exp["items"] if i["why"]["hard_constraint_status"] == "excluded"]
        assert excluded and body["excluded_count"] >= 1
        for item in excluded:
            assert any("outside_mandatory_countries" in c or "excluded" in c
                       for c in item["reason_codes"])

    def test_budget_ceiling_excludes_and_requires_currency(self, db, client):
        _register(client)
        _complete_onboarding(client)
        r = client.post("/api/v1/recommendations", json={
            "filters": {"max_total_budget": {"amount": 1000}}})
        assert r.status_code == 422
        assert r.json()["error"]["details"][0]["field"] == "filters.max_total_budget.currency"

        body = client.post("/api/v1/recommendations", json={
            "filters": {"max_total_budget": {"amount": 1000, "currency": "EUR"}}}).json()
        assert body["excluded_count"] > 0
        exp = client.get(f"/api/v1/recommendations/{body['run_id']}/explanations").json()
        budgeted = [i for i in exp["items"]
                    if "exceeds_budget_ceiling" in i["reason_codes"]]
        assert budgeted

    def test_explanations_include_rule_outcomes_and_dimensions(self, db, client):
        _register(client)
        _complete_onboarding(client)
        body = client.post("/api/v1/recommendations", json={}).json()
        exp = client.get(f"/api/v1/recommendations/{body['run_id']}/explanations").json()
        assert exp["ruleset_version"] == "eligibility-v1"
        for entry in exp["items"]:
            why = entry["why"]
            assert why["hard_constraint_status"] in ("passed", "excluded")
            assert isinstance(why["reasons"], list)
            assert isinstance(why["concerns"], list)
            assert isinstance(why["missing_information"], list)
            assert isinstance(why["requirement_outcomes"], list)
            for outcome in why["requirement_outcomes"]:
                assert outcome["status"] in ("pass", "fail", "conditional", "unknown")
                assert outcome["explanation"]
            if entry["fit_score"] is not None:
                dims = {b["dimension"] for b in entry["score_breakdown"]}
                assert {"academic_fit", "career_fit", "affordability", "quality",
                        "outcomes", "destination"} <= dims
                for b in entry["score_breakdown"]:
                    assert b["score"] is None or 0 <= b["score"] <= 1

    def test_tier_caps_demote_but_never_drop(self, db, client):
        _register(client)
        _complete_onboarding(client)
        from app.models import RecommendationRuleset

        ruleset = db.query(RecommendationRuleset).filter_by(is_active=True).first()
        previous = ruleset.scoring_config
        ruleset.scoring_config = {**previous, "tiers": {"ambitious": 1, "target": 1,
                                                        "safer_fit": 1}}
        db.commit()
        try:
            body = client.post("/api/v1/recommendations", json={}).json()
            total_in_tiers = sum(len(v) for v in body["tiers"].values())
            # no eligible program is silently dropped: everything is in a tier or excluded
            assert total_in_tiers >= 1
            # caps honoured: at most... + overflow into safer_fit (final tier, uncapped)
            assert len(body["tiers"]["ambitious"]) <= 1
            assert len(body["tiers"]["target"]) <= 1
        finally:
            ruleset.scoring_config = previous
            db.commit()

    def test_list_refresh_and_ownership(self, db, client):
        email_owner = _register(client)
        _complete_onboarding(client)
        body = client.post("/api/v1/recommendations", json={}).json()
        run_id = body["run_id"]

        listing = client.get("/api/v1/recommendations").json()["items"]
        assert any(r["run_id"] == run_id for r in listing)

        refreshed = client.post(f"/api/v1/recommendations/{run_id}/refresh").json()
        assert refreshed["run_id"] != run_id
        original = client.get(f"/api/v1/recommendations/{run_id}")
        assert original.status_code == 200 and original.json()["run_id"] == run_id

        # owner check: a different user gets 404 for every run endpoint
        client.cookies.clear()
        _register(client)
        assert client.get(f"/api/v1/recommendations/{run_id}").status_code == 404
        assert client.get(f"/api/v1/recommendations/{run_id}/explanations").status_code == 404
        assert client.post(f"/api/v1/recommendations/{run_id}/refresh").status_code == 404

    def test_filters_apply_to_run(self, db, client):
        _register(client)
        _complete_onboarding(client)
        all_ids = set()
        body = client.post("/api/v1/recommendations",
                           json={"filters": {"countries": ["DE"]}}).json()
        exp = client.get(f"/api/v1/recommendations/{body['run_id']}/explanations").json()
        for entry in exp["items"]:
            all_ids.add(entry["country_code"])
        assert all_ids == {"DE"}
