"""Official University of Almería master's catalogue JSON feed.

The dataset listing declares CC BY and describes active study offerings. This
adapter emits candidates only; source identity must still pass the normal review
queue when no authoritative institution identifier is present in the feed.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Iterator
from urllib.parse import urljoin, urlsplit

from app.ingestion.adapters.base import RunContext, SourceAdapter
from app.ingestion.adapters.webpage import _robots_allows
from app.ingestion.http import FetchError
from app.ingestion.normalize import program_title_matches
from app.ingestion.types import AdapterBatch, CandidateFact, CandidateField, CandidateInstitution, CandidateProgram, ProgramDocument, SourceDoc, SourceNotPermitted

API = "https://campus.ual.es/ual/api/estudios/planes/titulaciones/MOF/es"
PUBLISHER_ID = "u04800001"
CATALOGUE = "https://www.ual.es/estudios/masteres"
MAX_PROGRAM_PAGES = 5


class _Description(HTMLParser):
    """Literal paragraphs in UAL's presentation column, not the surrounding CMS."""
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.stack, self.paragraphs, self.parts = [], [], []
        self.scope = self.paragraph = None
        self.feed(markup)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            return
        self.stack.append((tag, attrs))
        classes = set((attrs.get('class') or '').split())
        if tag == 'div' and {'col-sm-12', 'col-md-8', 'col-lg-8'} <= classes:
            self.scope = len(self.stack)
        if tag == 'p' and self.scope and not self._blocked():
            self.paragraph, self.parts = len(self.stack), []

    def _blocked(self):
        return any(tag in {'script', 'style', 'nav', 'footer', 'header', 'aside', 'menu'}
            or 'hidden' in attrs or attrs.get('aria-hidden') == 'true'
            or attrs.get('role') in {'navigation', 'alert'}
            or set((attrs.get('class') or '').split()) & {'avisos', 'alert', 'breadcrumb', 'cookie-banner'}
            or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', attrs.get('style', ''), re.I)
            for tag, attrs in self.stack)

    def handle_data(self, data):
        if self.paragraph and not self._blocked():
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'p' and self.paragraph:
            text = ' '.join(''.join(self.parts).split())
            if len(text) >= 60 and not any(token in text for token in ('{{', '{%', '}}')):
                self.paragraphs.append(text)
            self.paragraph = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
        if self.scope and len(self.stack) < self.scope:
            self.scope = self.paragraph = None

    def excerpt(self):
        # Reference passage for human summarisation, never a published description.
        return ' '.join(' '.join(self.paragraphs).split()[:80])[:800].strip()


class _Page(HTMLParser):
    """Read literal links/titles/plan bindings; never execute Angular templates."""

    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.links, self.titles, self.scripts, self.plan_bindings = [], [], [], {}
        self.heading, self.parts, self.script = None, [], False
        self.feed(markup)
        self.close()
        for script in self.scripts:
            for match in re.finditer(r"\bvar\s+parameters\s*=\s*\[\s*(['\"])([0-9]+)\1\s*\]", script):
                self.plan_bindings[match[2]] = match[0]
            # UAL publishes a literal description inside a script append().
            # Parse that literal metadata, without evaluating the script.
            for fragment in re.findall(r'<meta\b[^>]*>', script, flags=re.I):
                metadata = _Page(fragment)
                self.titles.extend(metadata.titles)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href'):
            self.links.append((attrs['href'], self.get_starttag_text()))
        if tag == 'meta' and (attrs.get('name') == 'description' or attrs.get('property') == 'og:title'):
            self.titles.append((attrs.get('content') or '', 'meta description/title'))
        if tag in ('h1', 'h2', 'title'):
            self.heading, self.parts = tag, []
        if tag == 'script':
            self.script = True
        if attrs.get('data-plan'):
            self.plan_bindings[attrs['data-plan']] = self.get_starttag_text()

    def handle_data(self, data):
        if self.script:
            self.scripts.append(data)
        elif self.heading:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == self.heading:
            self.titles.append((' '.join(self.parts), self.heading))
            self.heading = None
        if tag == 'script':
            self.script = False


def _permitted_url(url, plan=None):
    parts = urlsplit(url)
    path = parts.path.rstrip('/')
    paths = {urlsplit(CATALOGUE).path} if plan is None else {
        f'/estudios/masteres/presentacion/{plan}', f'/en/estudios/masteres/presentacion/{plan}'}
    return (parts.scheme == 'https' and parts.hostname in {'www.ual.es', 'ual.es'}
            and not parts.username and not parts.password and parts.port in (None, 443)
            and path in paths and not parts.fragment
            and parts.query in ('', 'idioma=es_ES', 'idioma=en_GB'))


def _fetch_page(ctx, url, plan=None):
    # Redirects are inspected BEFORE following: each destination needs permission.
    for _ in range(4):
        if not _permitted_url(url, plan):
            raise ValueError('redirect or link is not the expected official UAL page')
        if not _robots_allows(ctx, url, follow_redirects=False):
            raise SourceNotPermitted('robots.txt disallows the official UAL page')
        result = ctx.fetcher.get(url, follow_redirects=False)
        if result.status in (301, 302, 303, 307, 308):
            url = urljoin(url, result.headers.get('location', ''))
            continue
        if result.status != 200 or len(result.content) > 2_000_000:
            raise ValueError('programme page is not a bounded HTTP 200 document')
        content_type = result.headers.get('content-type', '').split(';')[0].lower()
        if content_type and content_type not in ('text/html', 'application/xhtml+xml'):
            raise ValueError('programme page did not return HTML')
        return url, result, _Page(result.text())
    raise ValueError('too many UAL page redirects')


def _page_documents(ctx, programs):
    """At most one catalogue and five pages, with bounded redirects/retries."""
    if ctx.offline:
        return ['UAL programme pages were not checked in offline mode.']
    warnings = []
    try:
        catalogue_url, result, catalogue = _fetch_page(ctx, CATALOGUE)
    except (FetchError, SourceNotPermitted, ValueError) as exc:
        return [f'UAL programme-page discovery unavailable: {exc}']
    catalogue_doc = SourceAdapter.document_from_http(catalogue_url, result,
        title='UAL official Master’s catalogue links', document_type='html')
    for program in programs[:MAX_PROGRAM_PAGES]:
        code = program.external_key.rsplit(':', 1)[-1]
        try:
            link = next(((urljoin(catalogue_url, re.sub(r'\{\{\s*[tr]\.cod_plan\s*\}\}', code, href)), raw)
                         for href, raw in catalogue.links
                         if _permitted_url(urljoin(catalogue_url, re.sub(r'\{\{\s*[tr]\.cod_plan\s*\}\}', code, href)), code)), None)
            if not link:
                raise ValueError('no literal catalogue link or published cod_plan link template')
            url, result, page = _fetch_page(ctx, link[0], code)
            if set(page.plan_bindings) != {code}:
                raise ValueError('page plan binding is missing or disagrees with the catalogue plan')
            title = next(((title.strip(), locator) for title, locator in page.titles
                          if '{{' not in title and '{%' not in title and len(title) <= 400
                          and program_title_matches(program.title, title)), None)
            if not title:
                raise ValueError('no matching literal programme title; templates are not title evidence')
            observed, locator = title
            binding = page.plan_bindings[code]
            description = _Description(result.text()).excerpt()
            doc = SourceAdapter.document_from_http(url, result, title=observed[:300],
                document_type='html', content_excerpt=f'{observed}\n{binding}' + (f'\n{description}' if description else ''))
            program.documents.extend([
                ProgramDocument(catalogue_doc, [CandidateFact('official_program_page_discovery',
                    {'url': url, 'plan_code': code, 'catalogue_url': catalogue_url, 'link': link[1]},
                    excerpt=link[1], locator='a[href]')]),
                ProgramDocument(doc, [CandidateFact('official_program_page_url',
                    {'url': url, 'plan_code': code, 'source_program_key': program.external_key,
                     'page_title': observed, 'plan_binding': binding}, excerpt=f'{observed}\n{binding}',
                    locator=f'{locator}; script parameters / data-plan={code}')]),
            ])
            if description:
                # The dataset's licence is not asserted for HTML prose. Keep a
                # short reference excerpt; a reviewer must write the public summary.
                value = {'url': url, 'plan_code': code, 'source_program_key': program.external_key,
                         'page_title': observed, 'plan_binding': binding, 'source_excerpt': description,
                         'reuse_basis': 'reference_excerpt_for_review'}
                program.documents[-1].facts.append(CandidateFact('program_description',
                    {**value, 'summary': None}, normalized=value,
                    excerpt=f'{observed}\n{binding}\n{description}',
                    locator='div.col-sm-12.col-md-8.col-lg-8 > p; literal presentation text'))
        except (FetchError, SourceNotPermitted, ValueError) as exc:
            warnings.append(f'UAL plan {code} programme page unavailable: {exc}')
    if len(programs) > MAX_PROGRAM_PAGES:
        warnings.append(f'UAL programme-page checks capped at {MAX_PROGRAM_PAGES}; remaining links need a separate bounded run.')
    return warnings


class UalMastersAdapter(SourceAdapter):
    source_key = "ual_masters"

    def iter_batches(self, ctx: RunContext) -> Iterator[AdapterBatch]:
        result = ctx.fetcher.get(API)
        payload = json.loads(result.text())
        rows = payload.get("planes")
        if not isinstance(rows, list):
            raise ValueError("UAL masters response is missing the 'planes' list.")

        programs = []
        fields = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get("cod_plan") or "").strip()
            title = str(row.get("nom_plan") or "").strip()
            # Inter-university and double-master entries need distinct multi-award
            # or consortium modelling, so keep them out of this single-institution pilot.
            if (not code or not title or row.get("interuni_sn") != "N"
                    or row.get("l_doble_sn") == "S"):
                continue
            locator = f"planes[cod_plan={code}]"
            area_code = str(row.get("cod_rama") or "").strip()
            area_name = str(row.get("nom_rama") or "").strip()
            field_key = f"ual_rama_{area_code}" if area_code.isdigit() and area_name else None
            if field_key:
                fields[field_key] = CandidateField(field_key, area_name,
                    "UAL source academic branch; no equivalence to another taxonomy is inferred.")
            facts = [CandidateFact(
                fact_key="program_title_as_reported",
                value={"title": title}, normalized={"title": title},
                excerpt=title, locator=locator), CandidateFact(
                fact_key="discipline_area",
                value={"name": str(row.get("nom_rama") or "").strip()},
                normalized={"name": str(row.get("nom_rama") or "").strip()},
                excerpt=f"{code}: {title}; {row.get('nom_rama')}",
                locator=locator, extraction_method="parser")]
            mode = str(row.get("d_tip_ensenanza") or "").strip()
            if mode:
                facts.append(CandidateFact(
                    fact_key="delivery_mode_as_reported", value={"label": mode, "source_code": row.get("c_tip_ensenanza")},
                    normalized={"label": mode}, excerpt=f"{code}: {mode}",
                    locator=locator, extraction_method="parser"))
            facts.append(CandidateFact("source_catalogue_flags", {
                "display_flag_as_reported": row.get("pintar_sn"),
                "joint_flag_as_reported": row.get("interuni_sn"),
                "double_award_flag_as_reported": row.get("l_doble_sn")},
                excerpt=f"{code}: pintar_sn={row.get('pintar_sn')}; interuni_sn={row.get('interuni_sn')}; l_doble_sn={row.get('l_doble_sn')}", locator=locator))
            programs.append(CandidateProgram(
                external_key=f"ual:master:plan:{code}", title=title,
                degree_level="masters", discipline_name=str(row.get("nom_rama") or "").strip() or None,
                discipline_key=field_key,
                # This API returns the source row but not a stable course landing
                # page. A catalogue-wide URL must not be presented as a program URL.
                official_url=None,
                study_mode={"VIR": "online", "SEM": "blended", "HIB": "blended"}.get(row.get("c_tip_ensenanza")),
                facts=facts))
            if ctx.max_records is not None and len(programs) >= ctx.max_records:
                break

        institution = CandidateInstitution(
            external_key=f"ual:publisher:{PUBLISHER_ID}",
            name="Universidad de Almería", country_code="ES", country_name="Spain",
            city="Almería", website="https://www.ual.es",
            identifiers={"ual_dataset_publisher": PUBLISHER_ID},
            programs=programs)
        document = SourceDoc(
            url=API, canonical_url=API, title="Másteres Oficiales — Universidad de Almería",
            document_type="json", content=result.content, http_status=result.status,
            etag=result.etag, last_modified=result.last_modified,
            retrieval_attempt_count=getattr(result, "attempts", 1))
        warnings = _page_documents(ctx, programs) if programs else []
        yield AdapterBatch(document=document, institutions=[institution], fields=list(fields.values()), warnings=warnings)
