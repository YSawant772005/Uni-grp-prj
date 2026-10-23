"""Conservative URL roles for source evidence and program review."""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit


def classify_program_url(url: str | None, *, verified: bool = False,
                         demo_fixture: bool = False) -> str:
    """Classify what a URL can support; syntax alone never verifies a course page."""
    if not url:
        return "unavailable"
    if demo_fixture:
        return "demo_fixture"
    try:
        parts = urlsplit(url)
        host, path = (parts.hostname or "").lower(), parts.path.rstrip("/").lower()
    except ValueError:
        return "unverified_candidate"
    if host in {"ror.org", "www.ror.org"}:
        return "identifier_resolver"
    if any(host == domain or host.endswith("." + domain) for domain in
           ("datos.gob.es", "data.gouv.fr", "data.enseignementsup-recherche.gouv.fr", "onderwijsdata.duo.nl")):
        return "dataset_record"
    if host in {"ual.es", "www.ual.es"} and path in {
            "/estudios", "/estudios/es", "/estudios/masteres", "/en/estudios/masteres"}:
        return "general_catalogue"
    if host == "campus.ual.es" and path.startswith("/ual/api/"):
        return "source_api"
    if (host == "opintopolku.fi" and "/toteutus/" in path
            or host == "cricos.education.gov.au" and path == "/course/coursedetails.aspx"
            and parse_qs(parts.query).get("CourseCode")):
        return "verified_government_program_record" if verified else "government_program_record"
    if not path or path in {"/programs", "/programmes", "/courses", "/catalogue", "/catalog", "/masters"}:
        return "general_catalogue"
    if verified:
        return "verified_program_page"
    return "unverified_candidate"
