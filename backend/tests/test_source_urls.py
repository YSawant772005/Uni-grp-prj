from app.services.source_urls import classify_program_url


def test_generic_ual_catalogue_is_not_classified_as_program_page():
    assert classify_program_url("https://www.ual.es/estudios") == "general_catalogue"


def test_ual_source_api_is_not_classified_as_program_page():
    assert classify_program_url(
        "https://campus.ual.es/ual/api/estudios/planes/titulaciones/MOF/es"
    ) == "source_api"


def test_dataset_and_identifier_urls_keep_their_distinct_roles():
    assert classify_program_url("https://datos.gob.es/es/catalogo/example") == "dataset_record"
    assert classify_program_url("https://ror.org/03yrm5c26") == "identifier_resolver"


def test_candidate_url_requires_explicit_evidence_to_be_verified():
    url = "https://www.example.edu/graduate/program/biology"
    assert classify_program_url(url) == "unverified_candidate"
    assert classify_program_url(url, verified=True) == "verified_program_page"
    assert classify_program_url(url, demo_fixture=True) == "demo_fixture"
