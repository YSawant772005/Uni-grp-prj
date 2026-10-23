"""New normalized slugs do not change old identities, routes or city filters."""
import pytest
from sqlalchemy import select

from app.db.base import slugify
from app.ingestion import persist
from app.ingestion.registry import get_spec
from app.ingestion.types import CandidateProgram, SourceDoc
from app.models import City, Program


@pytest.mark.parametrize("name,expected", [
    ("Máster en Comunicación Social", "master-en-comunicacion-social"),
    ("Économie, ingénierie & sociétés", "economie-ingenierie-societes"),
    ("Über Größen in München", "uber-grossen-in-munchen"),
    ("Cœur, œuvre et Æther", "coeur-oeuvre-et-aether"),
    ("Łódź / Tromsø", "lodz-tromso"),
    ("Cafe\u0301", "cafe"), ("Ｆｕｌｌ １２", "full-12"),
    ("--- A  & B!!!", "a-b"), ("中文 🎓", "item"), ("\u0301", "item"), ("", "item"),
])
def test_unicode_normalization(name, expected):
    assert slugify(name) == expected


def test_truncation_and_empty_fallback_respect_length():
    assert slugify("ab cd", 3) == "ab"
    assert slugify("🎓", 2) == "it"
    with pytest.raises(ValueError):
        slugify("a", 0)


def test_distinct_offering_ids_get_distinct_slugs_without_changing_existing_ids(db, client):
    existing = db.scalar(select(Program))
    university = existing.university_id
    from app.models import University
    university = db.get(University, university)
    source = persist.ensure_source(db, get_spec("ual_masters"))
    document = persist.store_document(db, source, SourceDoc(url="https://example.test/fixture", content=b"fixture"), persist.Counters())
    first, _ = persist.upsert_program(db, university,
        CandidateProgram(external_key="slug:1", title="Máster en Comunicación Social"), {}, source=source, source_document=document)
    second, _ = persist.upsert_program(db, university,
        CandidateProgram(external_key="slug:2", title="Master en Comunicacion Social"), {}, source=source, source_document=document)
    assert first.id != second.id
    assert first.slug == "master-en-comunicacion-social"
    assert second.slug == "master-en-comunicacion-social-2"
    first.slug = "m-ster-en-comunicaci-n-social"
    first.publication_status = "published"
    db.commit()
    again, _ = persist.upsert_program(db, university,
        CandidateProgram(external_key="slug:1", title="Máster en Comunicación Social"), {}, source=source, source_document=document)
    assert again.id == first.id and again.slug == "m-ster-en-comunicaci-n-social"
    assert client.get(f"/api/v1/programs/{first.id}").json()["slug"] == first.slug
    assert client.get(f"/api/v1/programs/{first.slug}").status_code == 404  # API routes use UUIDs


def test_new_university_slug_collisions_include_pending_session_rows(db):
    from app.models import University
    country = db.scalar(select(University.country_code))
    first = University(canonical_name="École", slug="ecole", country_code=country)
    db.add(first)
    assert persist._unique_slug(db, University, "Ecole") == "ecole-2"


def test_existing_city_slug_and_filter_remain_compatible(db, client):
    city = City(country_code="DE", name="München", slug="m-nchen", admin_region="Bavaria")
    db.add(city)
    db.commit()
    again = persist.ensure_city(db, "DE", "München", "Bavaria")
    assert again.id == city.id and again.slug == "m-nchen"
    assert client.get("/api/v1/programs?city=m-nchen").status_code == 200


@pytest.mark.parametrize('with_cache', [False, True])
def test_non_latin_city_slug_collisions_do_not_merge_distinct_places(db, with_cache):
    persist.ensure_country(db, 'JP', 'Japan')
    cache = {} if with_cache else None
    first = persist.ensure_city(db, 'JP', '東京', cache=cache)
    second = persist.ensure_city(db, 'JP', '京都', cache=cache)
    assert first.id != second.id
    assert (first.slug, second.slug) == ('item', 'item-2')
    assert persist.ensure_city(db, 'JP', '東京', cache=cache).id == first.id
