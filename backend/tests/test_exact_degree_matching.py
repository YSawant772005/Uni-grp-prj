"""No database required: test award-title parsing and shortlist hard constraints."""
from types import SimpleNamespace

from app.services.degree_matching import exact_award_match, recognized_award
from app.services.recommendations import _hard_constraints


def test_award_classification_is_conservative():
    assert recognized_award("MSc Computer Science") == "Master of Science"
    assert recognized_award("M.Tech in Computer Engineering") == "Master of Technology"
    assert recognized_award("MBA in Finance") == "Master of Business Administration"
    assert recognized_award("Unknown program") is None
    assert not exact_award_match("Master of Technology", "MSc Computer Engineering")
    assert not exact_award_match("Master of Technology", "MBA Finance")


def test_strict_award_and_specialization_filter():
    profile = SimpleNamespace(
        intended_degree_level="masters", desired_degree_title="Master of Technology",
        field_id="computer_engineering", country_preferences=[],
    )
    programs = [
        SimpleNamespace(canonical_name="MSc Computer Engineering", degree_level="masters",
                        field_id="computer_engineering", country_code="GB"),
        SimpleNamespace(canonical_name="MTech Computer Science", degree_level="masters",
                        field_id="computer_science", country_code="GB"),
        SimpleNamespace(canonical_name="MTech Computer Engineering", degree_level="masters",
                        field_id="computer_engineering", country_code="GB"),
        SimpleNamespace(canonical_name="MTech Computer Engineering", degree_level="bachelors",
                        field_id="computer_engineering", country_code="GB"),
    ]
    allowed, excluded = _hard_constraints(None, profile, programs, {})
    assert allowed == [programs[2]]
    assert "different_degree_title_or_unverified_award" in excluded[0][1]
    assert "different_specialization_or_unverified_field" in excluded[1][1]
    assert "different_degree_level" in excluded[2][1]
