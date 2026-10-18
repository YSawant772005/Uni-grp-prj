"""Phase 6b: cost estimates, scholarships/funding, loans/ROI, destinations/outcomes
(§5.7/§5.8) — money honesty, schedule math, owner-only access, disclaimers."""
import uuid
from decimal import Decimal

import pytest

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.seed import run_seed
from app.models import CostScenario, LoanScenario, Program, RoiScenario
from conftest import _truncate_all

ONBOARDING = {
    "intended_degree_level": "masters", "field": "data_science",
    "country_preferences": [{"country_code": "DE", "is_mandatory": True}],
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
    assert "_test" in settings.database_url, "tests require a *_test database"
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
    email = f"fin-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "Sup3rSecret!"})
    assert r.status_code == 201
    return email


def _programs(db, slug=None):
    q = db.query(Program)
    if slug:
        q = q.filter(Program.slug == slug)
    return q.order_by(Program.id).all()


class TestCostEstimates:
    def test_public_calculate_needs_no_auth(self, db, client):
        client.cookies.clear()
        pid = str(_programs(db)[0].id)
        r = client.post("/api/v1/cost-estimates", json={"program_id": pid, "scenario": "base"})
        assert r.status_code == 200

    def test_totals_reconcile_and_unknown_components_never_zero(self, db, client):
        client.cookies.clear()
        pid = str(_programs(db)[0].id)
        body = client.post("/api/v1/cost-estimates",
                           json={"program_id": pid, "scenario": "base"}).json()
        known = [i for i in body["items"] if i["amount"] is not None]
        unknown = [i for i in body["items"] if i["amount"] is None]
        assert known and unknown, "seeded estimate mixes known and unavailable components"
        assert body["total"] == pytest.approx(sum(float(i["amount"]) for i in known))
        for item in unknown:
            assert item["amount"] is None and item["status"] == "unavailable"
            assert "zero" in item["note"]  # explicitly excluded, not counted as zero
        assert any(w.startswith("components_unavailable:") for w in body["data_warnings"])
        for item in known:
            assert item["currency"] and item["period"] and item["status"] != "unavailable"

    def test_scenarios_ordered_low_base_high(self, db, client):
        client.cookies.clear()
        pid = str(_programs(db)[0].id)
        r = client.get(f"/api/v1/programs/{pid}/cost-estimates")
        totals = {s: r.json()["scenarios"][s]["total"] for s in ("low", "base", "high")}
        assert totals["low"] < totals["base"] < totals["high"]

    def test_converts_with_rate_date_and_source(self, db, client):
        client.cookies.clear()
        pid = str(_programs(db)[0].id)
        body = client.post("/api/v1/cost-estimates",
                           json={"program_id": pid, "currency": "USD"}).json()
        converted = [i for i in body["items"] if i.get("converted_from")]
        assert converted, "EUR fees must convert to the requested USD target"
        for item in converted:
            assert item["currency"] == "USD" and item["status"] == "estimated"
            assert item["rate"]["value"] and item["rate"]["date"] and item["rate"]["source"]
            assert item["converted_from"] == "EUR"

    def test_validation_and_404(self, db, client):
        client.cookies.clear()
        pid = str(_programs(db)[0].id)
        assert client.post("/api/v1/cost-estimates",
                           json={"program_id": pid, "scenario": "moon"}).status_code == 422
        assert client.post("/api/v1/cost-estimates",
                           json={"program_id": str(uuid.uuid4())}).status_code == 404
        assert client.get(f"/api/v1/programs/{uuid.uuid4()}/cost-estimates").status_code == 404

    def test_save_requires_auth_and_persists_items(self, db, client):
        client.cookies.clear()
        pid = str(_programs(db)[0].id)
        assert client.post("/api/v1/cost-estimates",
                           json={"program_id": pid, "save": True}).status_code == 401

        _register(client)
        r = client.post("/api/v1/cost-estimates",
                        json={"program_id": pid, "save": True, "name": "my plan"})
        assert r.status_code == 200 and r.json()["scenario_id"]
        scenario = db.get(CostScenario, uuid.UUID(str(r.json()["scenario_id"])))
        assert scenario is not None and scenario.name == "my plan"
        assert scenario.total_amount is not None
        assert all(i.currency and i.period and i.status for i in scenario.items), \
            "persisted items keep currency/period/status (null period falls back to 'other')"
        assert any(i.status == "unavailable" for i in scenario.items)


class TestScholarshipsAndFunding:
    def test_scholarship_search_and_detail(self, db, client):
        client.cookies.clear()
        listing = client.get("/api/v1/scholarships").json()
        assert listing["total_items"] >= 1
        item = listing["items"][0]
        assert item["amount"]["currency"] == "EUR"
        assert item["amount"]["min"] is not None and item["amount"]["max"] is not None
        assert item["status"] != "verified"  # demo fixture is never verified
        detail = client.get(f"/api/v1/scholarships/{item['id']}").json()
        assert detail["eligibility_rules"] and detail["linked_program_ids"]
        assert client.get(f"/api/v1/scholarships/{uuid.uuid4()}").status_code == 404
        # filter narrows results
        assert client.get("/api/v1/scholarships?country=NL").json()["total_items"] == 0

    def test_matches_require_auth_and_include_disclaimer(self, db, client):
        client.cookies.clear()
        assert client.post("/api/v1/scholarships/matches").status_code == 401
        _register(client)  # no onboarding: profile auto-created empty
        body = client.post("/api/v1/scholarships/matches").json()
        assert body["items"], "demo scholarship must be evaluated"
        assert "not an eligibility guarantee" in body["note"]
        for match in body["items"]:
            assert match["match_status"] in ("matching", "needs_review", "not_matching")
            for outcome in match["outcomes"]:
                assert outcome["status"] in ("pass", "fail", "conditional", "unknown")
                assert outcome["explanation"]

    def test_funding_search_detail_and_filters(self, db, client):
        client.cookies.clear()
        listing = client.get("/api/v1/funding-opportunities").json()
        assert listing["total_items"] >= 1
        item = listing["items"][0]
        assert item["opportunity_type"] == "fellowship"
        assert item["study_levels"] and item["official_url"].startswith("http")
        assert client.get(f"/api/v1/funding-opportunities/{item['id']}").status_code == 200
        assert client.get(f"/api/v1/funding-opportunities/{uuid.uuid4()}").status_code == 404
        filtered = client.get("/api/v1/funding-opportunities?opportunity_type=grant").json()
        assert filtered["total_items"] == 0


class TestLoanScenarios:
    def _payload(self, **over):
        payload = {"name": "edu loan", "principal_amount": 20000, "currency": "EUR",
                   "annual_interest_rate": 8.5, "tenure_months": 120,
                   "moratorium_months": 12, "interest_during_moratorium": "capitalize",
                   "repayment_method": "equal_emi"}
        payload.update(over)
        return payload

    def test_schedule_and_totals_reconcile(self, db, client):
        _register(client)
        body = client.post("/api/v1/loan-scenarios", json=self._payload()).json()
        results = body["results"]
        schedule = results["schedule"]
        assert len(schedule) == 120 - 12  # moratorium months do not accrue payments
        assert schedule[-1]["closing_balance"] == 0
        principal_sum = sum(Decimal(str(r["principal"])) for r in schedule)
        interest_sum = sum(Decimal(str(r["interest"])) for r in schedule)
        # capitalize: MI is inside the amortised principal, total = schedule only
        assert principal_sum == Decimal(str(results["principal_after_moratorium"]))
        assert interest_sum + Decimal(str(results["moratorium_interest"])) \
            == Decimal(str(results["total_interest"]))
        assert results["total_payable"] > Decimal("20000")
        assert "Not a loan offer" in body["disclaimer"]
        assert body["assumptions"] and body["interest_method"]

    def test_moratorium_modes_differ_correctly(self, db, client):
        _register(client)
        cap = client.post("/api/v1/loan-scenarios", json=self._payload(
            interest_during_moratorium="capitalize")).json()
        simple = client.post("/api/v1/loan-scenarios", json=self._payload(
            interest_during_moratorium="simple_interest")).json()
        none = client.post("/api/v1/loan-scenarios", json=self._payload(
            moratorium_months=0, interest_during_moratorium="none")).json()
        # capitalize funds a larger principal -> higher EMI; shorter tenure -> higher EMI
        assert cap["results"]["emi"] > simple["results"]["emi"] > none["results"]["emi"]
        assert cap["results"]["moratorium_interest"] \
            == simple["results"]["moratorium_interest"] > 0
        assert none["results"]["moratorium_interest"] == 0
        # every mode amortises to zero
        for body in (cap, simple, none):
            assert body["results"]["schedule"][-1]["closing_balance"] == 0

    def test_zero_interest(self, db, client):
        _register(client)
        body = client.post("/api/v1/loan-scenarios", json=self._payload(
            annual_interest_rate=0, moratorium_months=0,
            interest_during_moratorium="none", tenure_months=12,
            principal_amount=12000)).json()
        assert body["results"]["emi"] == 1000
        assert body["results"]["total_interest"] == 0

    def test_validation(self, db, client):
        _register(client)
        bad = [
            {"annual_interest_rate": 150},
            {"tenure_months": 12, "moratorium_months": 24},
            {"repayment_method": "bullet"},
            {"principal_amount": -5},
            {"currency": "EURO"},
        ]
        for override in bad:
            r = client.post("/api/v1/loan-scenarios", json=self._payload(**override))
            assert r.status_code == 422, (override, r.text)

    def test_list_get_owner_delete(self, db, client):
        _register(client)
        lid = client.post("/api/v1/loan-scenarios",
                          json=self._payload()).json()["id"]
        assert any(s["id"] == lid for s in client.get("/api/v1/loan-scenarios").json()["items"])
        # stored scenario recomputes the same schedule on read
        stored = client.get(f"/api/v1/loan-scenarios/{lid}").json()
        assert stored["results"]["schedule"][-1]["closing_balance"] == 0

        client.cookies.clear()
        _register(client)  # a different student
        assert client.get(f"/api/v1/loan-scenarios/{lid}").status_code == 404
        assert client.request("DELETE", f"/api/v1/loan-scenarios/{lid}").status_code == 404
        # and their own loan stays listable
        own = client.post("/api/v1/loan-scenarios", json=self._payload()).json()["id"]
        assert own != lid

    def test_requires_auth(self, db, client):
        client.cookies.clear()
        r = client.post("/api/v1/loan-scenarios", json=self._payload())
        assert r.status_code == 401


class TestRoiScenarios:
    def _payload(self, **over):
        payload = {"name": "payback", "currency": "EUR", "education_cost": 40000,
                   "expected_annual_income": 55000, "annual_expenses": 18000,
                   "employment_delay_months": 3, "discount_rate": 5,
                   "assumptions": {"income_source": "user estimate"}}
        payload.update(over)
        return payload

    def test_payback_estimated_with_disclosures(self, db, client):
        _register(client)
        body = client.post("/api/v1/roi-scenarios", json=self._payload()).json()
        results = body["results"]
        assert results["payback_status"] == "estimated"
        # 40000 / ((55000-18000)/12) = 12.97 -> rounded 13 + 3 delay
        assert results["payback_months"] == 16
        assert results["monthly_surplus"] > 0
        assert results["discounted_net_present_value"] is not None
        assert body["scope"] == "user_scenario"
        assert body["input_provenance"] == "user_entered_assumptions"
        assert "not a promise" in body["disclaimer"].lower()

    def test_no_positive_surplus_reports_instead_of_number(self, db, client):
        _register(client)
        body = client.post("/api/v1/roi-scenarios", json=self._payload(
            expected_annual_income=10000, annual_expenses=12000)).json()
        assert body["results"]["payback_months"] is None
        assert body["results"]["payback_status"] == "no_positive_surplus"
        assert body["results"]["warnings"]

    def test_missing_inputs_report_unknown(self, db, client):
        _register(client)
        body = client.post("/api/v1/roi-scenarios", json=self._payload(
            education_cost=None, expected_annual_income=None)).json()
        assert body["results"]["payback_months"] is None
        assert body["results"]["payback_status"] == "unknown"

    def test_persistence_and_ownership(self, db, client):
        _register(client)
        rid = client.post("/api/v1/roi-scenarios", json=self._payload()).json()["id"]
        assert any(s["id"] == rid for s in client.get("/api/v1/roi-scenarios").json()["items"])
        assert client.get(f"/api/v1/roi-scenarios/{rid}").json()["results"]["payback_months"] == 16

        client.cookies.clear()
        _register(client)
        assert client.get(f"/api/v1/roi-scenarios/{rid}").status_code == 404
        assert client.request("DELETE", f"/api/v1/roi-scenarios/{rid}").status_code == 404

    def test_requires_auth(self, db, client):
        client.cookies.clear()
        assert client.post("/api/v1/roi-scenarios",
                           json=self._payload()).status_code == 401


class TestDestinationsAndOutcomes:
    def test_country_list_and_detail(self, db, client):
        client.cookies.clear()
        countries = client.get("/api/v1/destinations/countries").json()["items"]
        assert len(countries) >= 7
        assert all(c["code"] and c["name"] for c in countries)
        # at least the programme countries carry universities
        assert any(c["university_count"] >= 1 for c in countries)
        detail = client.get("/api/v1/destinations/countries/DE").json()
        assert detail["cities"] and detail["official_study_url"]
        rules = detail["official_rules"]
        assert rules, "seeded visa/work rules for Germany"
        for rule in rules:
            assert rule["official_url"].startswith("http")
            assert rule["freshness_note"] and "checked" in rule["freshness_note"]
            assert "last_checked_at" in rule and "effective_from" in rule
        assert client.get("/api/v1/destinations/countries/ZZ").status_code == 404

    def test_city_living_costs_preserve_ranges(self, db, client):
        client.cookies.clear()
        city_id = client.get("/api/v1/destinations/countries/DE/cities").json()["items"][0]["id"]
        city = client.get(f"/api/v1/destinations/cities/{city_id}").json()
        assert city["living_costs"] and city["living_cost_year"]
        for cost in city["living_costs"]:
            assert cost["min"] <= cost["typical"] <= cost["max"]
            assert cost["currency"] and cost["period"] == "month"
            assert cost["status"] == "estimated"
        assert client.get(f"/api/v1/destinations/cities/{uuid.uuid4()}").status_code == 404

    def test_rules_index_with_filters(self, db, client):
        client.cookies.clear()
        listing = client.get("/api/v1/destinations/rules").json()
        assert listing["total_items"] >= 4
        assert listing["items"][0]["country_code"] and listing["items"][0]["rule_type"]
        narrowed = client.get("/api/v1/destinations/rules?country=DE").json()
        assert 0 < narrowed["total_items"] <= listing["total_items"]
        assert all(i["country_code"] == "DE" for i in narrowed["items"])

    def test_outcomes_are_scoped_and_never_unlabelled(self, db, client):
        client.cookies.clear()
        listing = client.get("/api/v1/outcomes?field=data_science").json()
        assert listing["total_items"] >= 1
        assert "population_scope" in listing["scope_note"]
        for row in listing["items"]:
            assert row["population_scope"] in ("program", "institution", "subject",
                                               "country", "other")
            assert row["metric_key"] and row["metric_unit"]
            assert row["status"] == "estimated"
            assert row["population_scope"] != "program" or row["program_id"]
        # pagination fields present
        assert listing["page"] == 1 and listing["total_pages"] >= 1
        empty = client.get(f"/api/v1/outcomes?program_id={uuid.uuid4()}").json()
        assert empty["total_items"] == 0 and empty["items"] == []
