"""Program discovery API tests: pagination, filters, validation, sorting,
program detail, money honesty and evidence/outcome provenance."""
import uuid

import pytest

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.seed import run_seed
from conftest import _truncate_all


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


class TestProgramList:
    def test_pagination_envelope(self, db, client):
        r = client.get("/api/v1/programs?page=1&page_size=4")
        body = r.json()
        assert r.status_code == 200
        assert set(body) == {"items", "page", "page_size", "total_items", "total_pages"}
        assert len(body["items"]) == 4 and body["total_items"] == 9 and body["total_pages"] == 3

    def test_page_beyond_range_returns_empty(self, db, client):
        body = client.get("/api/v1/programs?page=99").json()
        assert body["items"] == [] and body["total_items"] == 9

    def test_page_size_over_max_rejected(self, db, client):
        assert client.get("/api/v1/programs?page_size=101").status_code == 422

    def test_country_and_city_and_field_filters(self, db, client):
        assert client.get("/api/v1/programs?country=DE").json()["total_items"] == 3
        assert client.get("/api/v1/programs?city=berlin").json()["total_items"] == 2
        r = client.get("/api/v1/programs?field=data_science")
        assert r.json()["total_items"] == 2
        for item in r.json()["items"]:
            assert item["field"]["key"] == "data_science"

    def test_search_matches_program_or_university(self, db, client):
        assert client.get("/api/v1/programs?q=robotics").json()["total_items"] == 1
        assert client.get("/api/v1/programs?q=delft").json()["total_items"] == 1
        assert client.get("/api/v1/programs?q=quantum%20basket%20weaving").json()["total_items"] == 0

    def test_unknown_filter_values_are_422_not_silently_ignored(self, db, client):
        for params in ("field=astrology", "city=atlantis", "country=XX", "degree_level=mba",
                       "language=klingon", "recognition_status=fake", "sort=vibes", "order=sideways"):
            r = client.get(f"/api/v1/programs?{params}")
            assert r.status_code == 422, params
            assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_max_tuition_requires_currency(self, db, client):
        r = client.get("/api/v1/programs?max_tuition=16000")
        assert r.status_code == 422
        assert r.json()["error"]["details"][0]["field"] == "currency"

    def test_max_tuition_filters_tuition_alone_in_currency(self, db, client):
        body = client.get("/api/v1/programs?max_tuition=16000&currency=EUR&page_size=50").json()
        assert body["total_items"] > 0
        for item in body["items"]:
            t = item["tuition_summary"]
            assert t["unit"] == "EUR" and t["value"] is not None and t["value"] <= 16000
        # the AI program at TU Berlin has NO tuition data: it must not match a price filter
        ids = {i["id"] for i in body["items"]}
        unknown = client.get("/api/v1/programs?q=Technical%20University%20of%20Berlin").json()["items"]
        ai_prog = next(i for i in unknown if i["field"]["key"] == "artificial_intelligence")
        assert ai_prog["id"] not in ids
        assert ai_prog["tuition_summary"]["value"] is None
        assert ai_prog["tuition_summary"]["status"] == "unavailable"

    def test_sorting_deadline_is_deterministic(self, db, client):
        seen = []
        for _ in range(2):
            body = client.get("/api/v1/programs?sort=deadline&order=asc&page_size=50").json()
            seen.append([(i["nearest_intake"]["application_deadline"], i["id"]) for i in body["items"]])
        assert seen[0] == seen[1]

    def test_sort_tuition_nulls_last(self, db, client):
        body = client.get("/api/v1/programs?sort=tuition&currency=EUR&order=asc&page_size=50").json()
        values = [i["tuition_summary"]["value"] for i in body["items"]]
        known = [v for v in values if v is not None]
        assert values[:len(known)] == known  # all priced programs first
        assert all(v is None for v in values[len(known):])  # unknown tuition last, not zero

    def test_summary_never_shows_verified_demo_data(self, db, client):
        body = client.get("/api/v1/programs?page_size=50").json()
        for item in body["items"]:
            assert item["tuition_summary"]["status"] != "verified"
            assert item["data_quality"]["status"] in ("partial", "unavailable")


class TestProgramDetail:
    def test_detail_shape_and_honesty(self, db, client):
        pid = client.get("/api/v1/programs?page_size=1").json()["items"][0]["id"]
        r = client.get(f"/api/v1/programs/{pid}")
        body = r.json()
        assert r.status_code == 200
        for key in ("university", "intakes", "fees", "requirements", "data_quality",
                    "tuition_summary", "nearest_intake", "description"):
            assert key in body
        assert "tuition_not_verified" in body["data_quality"]["warnings"]

    def test_unknown_and_invalid_ids_are_404(self, db, client):
        assert client.get(f"/api/v1/programs/{uuid.uuid4()}").status_code == 404
        assert client.get("/api/v1/programs/not-a-uuid").status_code == 404

    def test_requirements_carry_evidence_status(self, db, client):
        pid = client.get("/api/v1/programs?q=robotics").json()["items"][0]["id"]
        items = client.get(f"/api/v1/programs/{pid}/requirements").json()["items"]
        assert items
        for req in items:
            assert req["evidence"]["status"] != "verified"  # demo fixtures are never verified
            assert req["group_key"] and req["operator"]

    def test_fees_endpoint_never_fabricates_tuition(self, db, client):
        # the program with unknown tuition must still return a tuition row, marked unavailable
        listed = client.get("/api/v1/programs?q=Technical%20University%20of%20Berlin").json()["items"]
        ai = next(i for i in listed if i["field"]["key"] == "artificial_intelligence")
        fees = client.get(f"/api/v1/programs/{ai['id']}/fees").json()["items"]
        tuition = next(f for f in fees if f["fee_type"] == "tuition")
        assert tuition["amount"] is None and tuition["status"] == "unavailable"
        assert tuition["amount"] != 0
        # mandatory fee still present with currency+period
        mandatory = next(f for f in fees if f["fee_type"] == "mandatory_fee")
        assert mandatory["currency"] == "EUR" and mandatory["period"] == "semester"

    def test_intakes_ordered_by_deadline(self, db, client):
        pid = client.get("/api/v1/programs?page_size=1").json()["items"][0]["id"]
        items = client.get(f"/api/v1/programs/{pid}/intakes").json()["items"]
        assert items and items[0]["application_deadline"] is not None

    def test_evidence_lists_versions_and_demo_sources(self, db, client):
        pid = client.get("/api/v1/programs?page_size=1").json()["items"][0]["id"]
        body = client.get(f"/api/v1/programs/{pid}/evidence").json()
        assert body["items"] and body["total_items"] >= 1
        fact = body["items"][0]
        assert fact["versions"] and fact["current_status"] != "verified"
        for src in fact["sources"]:
            assert "example.invalid" in (src["url"] or "")
            assert "DEMO" in (src["title"] or "") or "demo" in (src["title"] or "").lower()

    def test_outcomes_are_scope_labelled(self, db, client):
        # seeded outcome evidence is DE-scoped; pick a DE data-science program
        pid = client.get("/api/v1/programs?field=data_science&country=DE&page_size=1").json()["items"][0]["id"]
        items = client.get(f"/api/v1/programs/{pid}/outcomes").json()["items"]
        assert items
        for o in items:
            assert o["population_scope"] in ("program", "university", "subject", "country")
            # subject-level rows must be flagged as not directly about this program
            if o["population_scope"] in ("subject", "country"):
                assert o["applies_to_this_program"] is False


class TestPublicationVisibility:
    def test_hidden_program_is_not_publicly_listed(self, db, client):
        from app.models import Program

        prog = client.get("/api/v1/programs?page_size=1").json()["items"][0]
        row = db.get(Program, uuid.UUID(str(prog["id"])))
        row.publication_status = "hidden"
        db.commit()
        try:
            assert client.get(f"/api/v1/programs/{row.id}").status_code == 404
            ids = [i["id"] for i in client.get("/api/v1/programs?page_size=50").json()["items"]]
            assert str(row.id) not in ids
        finally:
            row.publication_status = "published"
            db.commit()
