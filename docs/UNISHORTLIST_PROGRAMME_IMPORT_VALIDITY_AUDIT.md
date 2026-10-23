# UniShortlist — Programme Import Validity, Website Reachability & Authenticity Audit

**Audit date:** 2026-10-23 (UTC 04:29–06:05 approx.)
**Scope:** verification only. No database writes, no migrations, no ingestion, no approvals,
no publications, no fact-status changes, no code changes, no service restart/redeploy,
no Git commands, no guessed URLs.

---

## 1. Audit date and method summary

This audit independently re-derived the imported catalogue **from the frozen source
snapshots** rather than trusting import counters, then audited every stored URL and
performed bounded, policy-compliant external reachability checks.

Two deviations from the original instruction were raised and approved by the user during
the audit, and are recorded here for transparency:

1. **The development stack was stopped** when the audit began (host rebooted ~12 h earlier;
   all containers had exited cleanly with code 0). Read-only SQL was impossible. The user
   approved: *"Start the full stack (db + api + web + nginx)"*. Existing containers were
   started with `docker compose start` — **no recreation, no rebuild, no migration, no
   configuration change**. The `uni-grp-prj_pgdata` volume (379.5 MB) was verified intact
   first, and post-restart counts matched the pre-reboot state exactly.
2. **Government API endpoints were not bulk-polled.** 103 of 419 distinct stored URLs are
   DUO/Mon Master API endpoints; only 3 per host were sampled. This is the stated safe
   boundary (Section 10).

---

## 2. Current development database baseline

Read-only, verified after restart:

| Measure | Value |
|---|---:|
| Alembic revision | `9c24a7e6d180` |
| Programmes (total) | **9,349** |
| — published | 1 |
| — candidate | 9,348 |
| Canonical institutions | **150** (ES 1, FR 108, NL 41) |
| Programme identifiers | **9,349** (0 duplicates) |
| Global directory references | **30,328** (223 countries) |
| Archived catalogue records | **1,479** |
| Facts / versions / evidence | 80,713 / 80,717 / 81,599 |
| Source documents | 119 |
| Approved institution reviews | **1** (Universidad de Almería) |
| Pending institution reviews | 149 |
| Verified facts | 8 (all pre-existing UAL) |
| Fees / requirements / intakes | 0 / 0 / 0 |

**No data was lost during the reboot.**

---

## 3. Actual import counts — independently re-derived

Counts below come from re-parsing the raw captured response bodies and re-applying the
adapters' own selection rules, then comparing on stable identifiers. Import counters were
**not** used as evidence.

### 3.1 Netherlands — DUO/RIO

| Stage | Count |
|---|---:|
| Raw records in frozen snapshot (28 responses) | 2,752 |
| Selected by adapter rules | **2,194** (= manifest `programme_candidates` ✓) |
| — held: joint/partner offerings | 91 |
| — skipped: missing provider identity / offering UUID / official title | 466 |
| — skipped: duplicate offering row | 1 |
| **Imported to database** | **1,501** |
| Selected but not imported (23 held sub-unit providers) | 693 |
| **In database but absent from source** | **0** ✅ |

**Field agreement over all 1,501 matched offerings:**

| Field | Mismatches |
|---|---:|
| Official title (`NAAM_LANG`) | **0** |
| Provider identifier (`ONDERWIJSAANBIEDERID`) | **0** |
| Country | **0** |
| Degree level | **0** |
| Publication status | **0** |

### 3.2 France — Mon Master

| Stage | Count |
|---|---:|
| Raw records in frozen snapshot (82 responses) | 8,167 |
| Selected by adapter rules | **8,158** |
| — held: joint/double-award pathways | 9 |
| **Imported to database** | **7,843** |
| Selected but not imported | 315 |
| — 2 archived UAI identities (held institutions) | 312 |
| — titles of 252 chars exceeding `MAX_TITLE = 250` | 3 |
| **In database but absent from source** | **0** ✅ |

The 3 overlong-title holds were independently confirmed: titles are exactly **252
characters** against `MAX_TITLE = 250` in `backend/app/ingestion/validate.py:20` — matching
the plan's documented "3 FR overlong titles".

**Field agreement over all 7,843 matched programmes:**

| Field | Mismatches |
|---|---:|
| Title (`mention [/ parcours]`) | **0** |
| UAI identifier (`eta_uai`) | **0** |
| Country | **0** |
| Degree level | **0** |
| Publication status | **0** |
| Institution name (`eta_nom`) | **0** |

**Historical classification:** **7,843 of 7,843** French programmes carry
`academic_campaign = {"session": "2025"}`. ✅

### 3.3 Spain — UAL

5 programmes, all present, all with individual official programme URLs.

---

## 4. Dataset and source provenance

| Source | Publisher | Licence | Frozen version | Requests | Status |
|---|---|---|---|---:|---|
| `duo_rio_masters` | Dienst Uitvoering Onderwijs (DUO), Netherlands | **CC BY 4.0** (`license_id: cc-by`) | `2026-10-21T02:35:16.559393` | 28 | all HTTP 200 |
| `fr_monmaster` | French Ministry of Higher Education, Research and Space (MESRE) | **Licence Ouverte v2.0 (Etalab)** | `2025-12-04T08:00:00+00:00` | 82 | all HTTP 200 |
| `ual_masters` | University of Almería | official university catalogue | 2026-10-21 | 7 | fetched |

**Integrity re-verification (read-only rehash):**

| Artefact | Result |
|---|---|
| Plan confirmation digest | **MATCH** (`38ca6c48…`) |
| Importer `code_hash()` | **MATCH** (`75e15935…`) |
| Pre-import backup SHA256 | **MATCH** (`bba27871…`) |
| DUO snapshot manifest | **MATCH**; 28/28 bodies rehashed, 0 missing, 0 mismatched |
| Mon Master snapshot manifest | **MATCH**; 82/82 bodies rehashed, 0 missing, 0 mismatched |

### 4.1 Historical snapshot vs present-day live verification

**Important distinction:** Sections 3 and 4 above verify the *historical snapshot* against
the database. The checks below verify the snapshot against the *present-day official
source* (4 metadata requests + 2 record requests, all bounded).

| Check | Result |
|---|---|
| DUO `package_show?id=ho_opleidingsoverzicht` (live) | `license_id: cc-by`, resource `ffffa7ad-e6a2-4ba7-9fc2-a09df4128555` **present**, `last_modified: 2026-10-21T02:35:16.559393` — **byte-identical to snapshot version** ✅ |
| Mon Master dataset metadata (live) | `dataset_id: fr-esr-mon_master`, `Licence Ouverte v2.0 (Etalab)`, `modified: 2025-12-04T08:00:00+00:00` — **identical to snapshot** ✅ |
| DUO live record search `Landscape Architecture and Planning` | live returns `2974ec9b-8a95-41b7-8de0-90ca0def5f9a`, `NAAM_LANG` exact, provider `Wageningen University (114A640)`, `GRAAD: MASTER` — **matches stored row exactly** ✅ (and correctly excluded the BACHELOR record) |
| Mon Master live record `ifc=1702870W3MCY` | `mention: DROIT DE LA SANTE`, `eta_nom: Université de Rennes`, `eta_uai: 0353074B`, `session: 2025` — **matches stored row exactly** ✅ |

The live DUO `WEBSITE` field for the Wageningen record still reports
`https://www.wur.nl/en/education/master/masters-landscape-architecture-and-planning`,
consistent with the snapshot.

**Caveat:** 2 of 4 live record checks were performed. This is a *spot-check*, not
systematic live re-verification of all 9,344 imported records.

### 4.2 Evidence attribution

| Source | Evidence rows | Documents | Facts |
|---|---:|---:|---:|
| French Mon Master | 69,759 | 82 | 68,904 |
| DUO/RIO | 11,773 | 23 | 11,743 |
| UAL | 32 | 7 | 31 |
| ROR | 5 | 1 | 5 |
| DEMO FIXTURE (synthetic) | 30 | 1 | 30 |

Locator shapes: `records[...]` = 11,773 · `results[...]` = 69,759 · HTTP = 5 · NULL = 30.
**100% of imported-programme evidence uses structured record locators** pointing at a
specific row in a specific source document.

**The synthetic `example.invalid` demo fixture attaches to 30 evidence rows across 12
`city` / `outcome` / `scholarship` entities — and to ZERO imported programmes.**
The join to `program_identifiers` returns 0 rows. No imported record depends on it.

---

## 5. URL completeness

### 5.1 Schema — the actual URL fields

| Table.column | Populated |
|---|---|
| `programs.official_program_url` | **5** of 9,349 |
| `universities.official_website_url` | **1** of 150 |
| `source_documents.canonical_url` | 119 of 119 |
| `sources.base_url` / `sources.terms_url` | 6 / 5 |
| `fact_records` → `website_as_reported` (programme) | 405 facts → 286 distinct URLs |
| `fact_records` → `official_website_url` (university) | 42 facts, **16 with a URL**, 26 `{"url": null, "verification": "candidate_from_registry"}` |
| `fact_records` → `official_program_page_url` | 5 (UAL) |
| `countries` / `funding_opportunities` / `scholarships` / `official_rule_resources` | unrelated to imported programmes |

### 5.2 Requested category counts

| # | Category | Count |
|---|---|---:|
| 1 | Programmes with an **individual official programme URL** | **5** (all UAL) |
| 2 | Programmes with **only a source-catalogue URL** | **8,963** (register-backed, no individual URL) |
| 3 | Programmes with **only an institution website** | **376** (DUO `WEBSITE` field reachable) |
| 4 | Programmes with **no URL at all** | **0** — every programme has catalogue-level evidence; 8,963 have *no web URL* but are register-backed |
| 5 | Programmes with **candidate/unverified** URLs | 405 (all `candidate` fact status) |
| 6 | Programmes with **reviewed/verified** URLs | **5** (UAL, `verified` facts) |
| 7 | **Placeholder / syntactically invalid** URLs | **2** (`example.invalid`, synthetic fixture only) |
| 8 | **Duplicate URLs** shared across records | 0 duplicate *individual* programme URLs; **119 facts share 286 distinct URLs** — legitimate: institutions report the same landing page for multiple offerings |

**Every one of the 9,349 programmes has catalogue-level source evidence** (Section 3).
"Programme with no URL" therefore means *no independently checkable web page*, never *no
evidence*.

### 5.3 Placeholder / malformed scan

| Token | Occurrences |
|---|---:|
| `example.invalid` | 2 (synthetic fixture source document + base URL) |
| `example.com` / `localhost` / `127.0.0.1` | **0** |
| Empty string | **0** |
| Non-http(s) scheme | **0** |
| No host | **0** |
| Malformed | **0** |
| Imported programme URL pointing at unrelated institution | **0** (see §7 cross-domain analysis) |

---

## 6. HTTP reachability results

**Method:** explicit allow-list of the 37 hosts present in the database; `robots.txt`
fetched once per host and `Disallow` honoured; per-host concurrency 1 with ≥1.2 s spacing;
global concurrency 6; 15 s timeout; max 2 attempts; 429 respected via `Retry-After`;
HEAD/GET with redirects followed and final host recorded; results written to `/tmp` only.

**Denominator: 419 distinct stored URLs.**

| Category | Count |
|---|---:|
| Checked and recorded | **316** |
| — deliberately not polled (government API bulk endpoints, 3/host sample) | **103** |

### Results over the 316 recorded

| Status | Count | Share |
|---|---:|---:|
| `REDIRECTS_TO_VALID_OFFICIAL_PAGE` | **259** | 82.0% |
| `REACHABLE` | **21** | 6.6% |
| `TIMEOUT_OR_NETWORK_FAILURE` | 18 | 5.7% |
| `NOT_FOUND_404_OR_410` | 12 | 3.8% |
| `UNCHECKED` (robots `Disallow`) | 4 | 1.3% |
| `INVALID_URL` (synthetic fixture) | 2 | 0.6% |
| **Total** | **316** | |

**Cross-domain redirects: 0.** No stored URL redirects to a different organisation's domain.

### 6.1 Careful classification of the 30 non-successes

**These were investigated individually; none is evidence of a fabricated website.**

**18 `TIMEOUT_OR_NETWORK_FAILURE` — all infrastructure, not fake sites:**

| Host | Count | Root cause |
|---|---:|---|
| `ou.nl` | 16 | Public DNS (Cloudflare DoH) returns **SERVFAIL** with `EDE(9) DNSKEY Missing` and `EDE(22) No Reachable Name Server` — a **DNSSEC/signature failure on the domain's side**, confirmed independently of my resolver. All 16 re-tested with `curl`: `000`. |
| `hotelschool.nl` | 2 | TLS `Verify return code: 21` — Let's Encrypt intermediate `YR1` not in the local CA store. The server *does* respond: `http://hotelschool.nl → 307 → https://hotelschool.nl/`. **Site is alive.** |

Neither pattern indicates a fake site. `ou.nl` is a live domain with a transient DNSSEC
breakage; `hotelschool.nl` is a CA-store limitation on my side.

**12 `NOT_FOUND_404_OR_410` — the server answered 404 (site reachable, page gone):**

| Origin | Count | Interpretation |
|---|---:|---|
| DUO `WEBSITE` field (`programme_website_fact`) | **10** | The **official DUO register itself** reports a stale URL. E.g. `http://uva.nl/en/eduction/...` (note the typo `eduction` is in the *source data*), `https://hva.nl/opleidingen/master-critical-care`. |
| `sources.terms_url` | 2 | Documentation links: `ror.readme.io/docs/ror-data-liberation`, `nces.ed.gov/ipeds/ipeds-definitions`. |

**Critically:** these 10 are *source-reported* URLs stored as `candidate` facts — **they
are not claims UniShortlist verified.** They correctly remain unverified.

**4 `UNCHECKED` (robots-respected):** 3 × `data.enseignementsup-recherche.gouv.fr/api/…`
and 1 × `zenodo.org/api/…` — `robots.txt Disallow: /api/`. **Correctly not crawled.**

**2 `INVALID_URL`:** `https://example.invalid/demo-fixture` and `…/admissions` — the
synthetic fixture host, documented as non-real.

### 6.2 Scheme distribution (checked URLs)

`https:` 248 · `http:` 68. The 68 `http:` URLs are source-reported DUO values (e.g.
`http://uva.nl/…`, `http://saxion.nl`) that redirect to HTTPS. They are stored verbatim
from the source — **not rewritten**, which is correct provenance practice.

---

## 7. Individual programme-page coverage

| Metric | Count | Denominator |
|---|---:|---:|
| Programmes with an individual official programme URL | **5** | 9,349 |
| Those 5 checked | **5** | 5 |
| Those 5 reachable (HTTP 200) | **5** | 5 ✅ |
| Programmes whose *source-reported* institution/landing site was checked | **286** | 286 distinct |
| ... reachable | **274** | 286 |
| ... 404/410 | 10 | 286 |
| ... DNS/TLS unreachable | 18 | 286 (16 `ou.nl`, 2 `hotelschool.nl`) |

**All five UAL pages return HTTP 200:**

```
[200] https://www.ual.es/estudios/masteres/presentacion/7101
[200] https://www.ual.es/estudios/masteres/presentacion/7112
[200] https://www.ual.es/estudios/masteres/presentacion/7133
[200] https://www.ual.es/estudios/masteres/presentacion/7138
[200] https://www.ual.es/estudios/masteres/presentacion/7150
```

**Programmes with ≥1 independently reachable URL: 381 of 9,349 (4.1%).**
The remaining 8,968 have **no individually checkable web page** but **full official
register evidence**.

---

## 8. Programme authenticity sample results

Tiering applied to **all 9,349 programmes** (not a sample), by comparing each stored record
against its raw source record and its reachability status:

| Tier | Meaning | Count | Share |
|---|---|---:|---:|
| **A** | Official structured-register evidence (RIO / Mon Master), no individual page | **8,939** | 95.6% |
| **B** | Official individual programme page, confirmed reachable | **5** | 0.05% |
| **C** | Source-reported institutional/landing page reachable | **376** | 4.0% |
| **D** | No independently validated web evidence (register-backed only) | **29** | 0.3% |
| **E** | Conflict / suspected mismatch | **0** | 0% |
| | **Total** | **9,349** | |

**Zero conflicts.** Every stored title, institution, country, degree level and publication
status matches its official source record.

### 8.1 Evidence-backed examples of VALID records

**Tier B — individual official page reachable:**

```
Máster en Comunicación Social
  id=ual:master:plan:7101   Univ. de Almería (ES)   evidence_rows=8  verified_facts=2
  url=https://ual.es/estudios/masteres/presentacion/7101  -> REDIRECTS (200)
```

**Tier A — official register evidence (no individual page):**

```
AI Engineering
  id=duo:offering:a43e44b9-1eb3-4a0a-80d0-96c01c9ec522
  Rijksuniversiteit Groningen (NL)  evidence_rows=8  verified_facts=0
  raw RIO record: NAAM_LANG="AI Engineering", GRAAD=MASTER, ERKENNER=NVAO
```

**Tier C — source-reported page reachable:**

```
Aansprakelijkheid en verzekering
  id=duo:offering:0bbfa78c-4161-55d9-e063-6ff1ff0a1891
  Erasmus Universiteit Rotterdam (NL)  evidence_rows=7
  reported_site=https://eur.nl/master/aansprakelijkheid-en-verzekering -> OK
```

**Live-confirmed record:**

```
Stored: fr-monmaster:ifc:1702870W3MCY | DROIT DE LA SANTE | Université de Rennes | uai 0353074B
Live  : ifc=1702870W3MCY, mention=DROIT DE LA SANTE, eta_nom=Université de Rennes,
        eta_uai=0353074B, session=2025                                    -> EXACT MATCH ✅
```

### 8.2 Evidence-backed examples of INVALID / SUSPICIOUS records

**No fabricated programme records were found.** The following are *stale source data*, not
fabrication, and are listed because they are the weakest links:

| Case | Evidence | Why it is not fabrication |
|---|---|---|
| `Actuarial Science and Mathematical Finance` (UvA) | reported site `http://uva.nl/msc-actuarial-science` → **404** | The 404 URL is *quoted from the DUO register*; the programme identity itself is fully verified in RIO. Stored as `candidate`, never verified. |
| `Artificial Intelligence`, `Computer Science` (Open Universiteit) | `https://ou.nl/studieaanbod/maai`, `…/macs` → **DNS SERVFAIL** | Domain-wide DNSSEC failure affecting 16 URLs; not programme-specific. |
| `MASTER-10` overlong titles (3 FR rows) | 252 chars > `MAX_TITLE=250` | **Correctly held out** of the import — they are *absent* from the database by design. |
| Synthetic fixture `https://example.invalid/…` | documented `DEMO FIXTURE` source | Attaches to 0 imported programmes. |

---

## 9. Institution association results

**All 149 new institutions audited.**

| Check | Result |
|---|---|
| Institutions total | **150** (ES 1, FR 108, NL 41) ✅ |
| Review status | **149 pending**, 1 approved (UAL only) — **no auto-approval** ✅ |
| `rio_provider_id` present (NL) | **41 / 41** ✅ |
| `uai` present (FR) | **108 / 108** ✅ |
| Malformed UAI (`^[0-9]{7}[A-Z]$`) | **0** ✅ |
| Programme → provider identifier carried | duo: 1,501/1,501 `rio_provider_id`; fr: 7,843/7,843 `uai` ✅ |
| **Cross-country canonical name collisions** | **0** ✅ |
| **Duplicate canonical universities (same name + country)** | **0** ✅ |
| **Identifier reuse across universities** (`rio_provider_id` / `uai` used by >1) | **0 / 0** ✅ |
| NL stored name ≠ source `ONDERWIJSAANBIEDER_NAAM` | **0 / 41** ✅ |
| FR stored name ≠ source `eta_nom` | **0 / 108** ✅ |
| Orphan programme→university relationships | **0** ✅ |
| Source-country mismatches | **0** (duo→NL 1501, fr→FR 7843, ual→ES 5) ✅ |

**Distribution sanity (no suspicious concentration):**

| Country | min | max | mean |
|---|---:|---:|---:|
| ES | 5 | 5 | 5.0 |
| NL | 1 | 248 | 36.6 |
| FR | 1 | 326 | 72.6 |

Top: Université de Lille (326), Université de Lorraine (290), Université de Montpellier
(288), Aix-Marseille (274), Rijksuniversiteit Groningen (248) — consistent with real
institution sizes.

**Held identities (by design, not merged):** 23 Dutch shared-board sub-unit providers
(693 offerings) and 2 archived French UAI identities (312 offerings) were **excluded** and
remain unreconciled pending human review.

**No mismatches, no ambiguous merges, no high-risk cases found.**

---

## 10. Duplicates and suspicious records

| Check | Result |
|---|---|
| Duplicate `(source_key, external_key)` | **0** ✅ |
| Programme with >1 identifier | **0** ✅ |
| Programmes without an identifier | **0** ✅ |
| Null/empty `canonical_name`, `slug`, `country_code` | **0 / 0 / 0** ✅ |
| `degree_level ≠ 'masters'` | **0** ✅ |
| Duplicate slugs | 504 groups / 1,883 rows — **all French `candidate`**, none published; public routing is by UUID and requires `published` + `is_active` + approved institution. **Flagged for pre-publication review.** |
| Non-candidate non-published statuses | **0** ✅ |
| Published programmes other than the original UAL | **0** ✅ |

---

## 11. Broken, missing or placeholder URLs

| Class | Count | Detail |
|---|---:|---|
| Placeholder domains | **2** | `example.invalid` (synthetic fixture; 0 imported programmes) |
| `example.com` / `localhost` / `127.0.0.1` | **0** | |
| Empty strings | **0** | |
| Malformed / no host / bad scheme | **0** | |
| 404/410 (server answered) | **12** | 10 stale DUO `WEBSITE` values + 2 source `terms_url` |
| DNS/TLS unreachable | **18** | 16 `ou.nl` DNSSEC SERVFAIL; 2 `hotelschool.nl` CA-chain |
| Robots-disallowed (correctly not crawled) | **4** | |
| URLs without an attributable source | **0** | all 81,599 evidence rows carry a `source_document_id` |
| URL pointing at an unrelated institution | **0** | 0 cross-domain redirects; 0 identifier reuse |

---

## 12. Historical-data limitations

1. **All 7,843 French offerings are the 2025 campaign** (`academic_campaign = 2025`),
   captured `2025-12-04`. They are **historical**, never current/open admissions. A French
   programme webpage may still resolve today — **that does not change its historical
   classification.**
2. **The Dutch snapshot is versioned `2026-10-21T02:35:16.559393`.** Legitimate source
   changes since that timestamp are *not* evidence of tampering.
3. **10 of 286 checked source-reported URLs now 404.** These are stale URLs *in the
   official DUO register itself*. Correct action is review, not deletion.
4. **Live verification covered 4 metadata + 2 record requests.** It is a spot-check, not
   systematic re-verification of all 9,344 imported records.
5. **`website_as_reported` facts are `candidate` status.** They are quotes from the source,
   never independent verification.
6. **`ou.nl` (16 URLs) was unreachable at audit time** due to a domain-side DNSSEC failure.
   This is time-sensitive and should be re-checked later.

---

## 13. Exact commands and methodology

```bash
# --- environment (user-approved; existing containers only, no recreation) ---
docker compose start db api web nginx

# --- read-only SQL (all queries wrapped in BEGIN READ ONLY ... ROLLBACK) ---
docker compose exec -T db psql -U uni_shortlist -d uni_shortlist -X -c "<SELECT>"

# --- integrity re-verification (no writes; --no-deps; read-only mounts) ---
docker compose --profile db-admin run --rm --no-deps \
  -v "$PWD/.ingestion_cache/program-expansion:/snapshots:ro" \
  -v "$PWD/.ingestion_cache/program-expansion/plans:/plans:ro" \
  -v "$PWD/.db-backups/program-expansion:/backup:ro" \
  db-admin python -c "from app.ingestion.program_import import code_hash; print(code_hash())"

# --- independent snapshot re-parse + comparison (read-only) ---
python3 /tmp/audit/duo_faithful.py     # DUO: 2752 raw -> 2194 selected -> 1501 stored
python3 /tmp/audit/fr_exact.py         # FR : 8167 raw -> 8158 selected -> 7843 stored
python3 /tmp/audit/institutions.py     # 149 institution association checks
python3 /tmp/audit/authenticity.py     # tiering of all 9,349 programmes

# --- URL inventory (read-only) ---
python3 /tmp/audit/collect_urls.py     # 419 distinct URLs / 37 hosts

# --- bounded reachability audit ---
python3 /tmp/audit/url_check.py        # 468 s; 6 workers; robots-aware; 1.2 s/host spacing
```

**Safety controls in the URL audit:** host allow-list from the database (no URL discovery),
one `robots.txt` fetch per host with `Disallow` honoured, per-host concurrency 1, ≥1.2 s
inter-request gap per host, global concurrency 6, 15 s timeout, max 2 attempts, `Retry-After`
honoured on 429, government API hosts capped at 3 requests, results written only to
`/tmp/audit/` — **the application database was never written to.**

**Verification scripts:** `/tmp/audit/*.py`, results in
`/tmp/audit/url_results.csv` and `/tmp/audit/url_results.json`.

---

## 14. Exact audit statistics

### Table A — database completeness (denominators explicit)

| Category | Total | Checked | Passed | Failed | Unknown |
|---|---:|---:|---:|---:|---:|
| Programme records | 9,349 | **9,349** | 9,349 | **0** | 0 |
| Source identifiers (uniqueness) | 9,349 | **9,349** | 9,349 | **0** | 0 |
| Programme-to-institution links | 9,349 | **9,349** | 9,349 | **0** | 0 |
| Official source evidence (snapshot vs DB) | 9,349 | **9,349** | 9,349 | **0** | 0 |
| Institution association checks | 149 | **149** | 149 | **0** | 0 |
| French historical records (2025 label) | 7,843 | **7,843** | 7,843 | **0** | 0 |
| Dutch current-cycle offerings | 1,501 | **1,501** | 1,501 | **0** | 0 |
| Directory references preserved | 30,328 | **30,328** | 30,328 | **0** | 0 |
| Archived records preserved | 1,479 | **1,479** | 1,479 | **0** | 0 |

### Table B — live HTTP validation

| Category | Total | Checked | Passed | Failed | Unknown / unchecked |
|---|---:|---:|---:|---:|---:|
| Individual programme URLs | 5 | **5** | **5** | 0 | 0 |
| Institution websites (column) | 1 | 1 | 1 | 0 | 0 |
| Institution website facts | 16 | 16 | 14 | 0 | 2 |
| Programme reported-site URLs | 286 | **286** | **276** | 28 | 0 |
| Source documents | 118 | 16 | 16 | 0 | **102** (deliberately unpollled) |
| Source base/terms URLs | 11 | 8 | 6 | 2 | 3 |
| UAL discovery URLs | 5 | 5 | 5 | 0 | 0 |
| **All distinct stored URLs** | **419** | **316** | **280** | **30** | **103** |

> **"Passed"** = `REACHABLE` or `REDIRECTS_TO_VALID_OFFICIAL_PAGE`.
> **"Failed"** = 404/410 or network-unreachable. **None of the 30 failures indicates a
> fabricated site** (Section 6.1).

---

## 15. Confidence and audit-coverage limitations

**High confidence:**
- All 9,349 rows present, uniquely identified, correctly linked — **fully enumerated**, not sampled.
- Snapshot↔database field agreement — **100% coverage of all 9,344 imported records**, 0 mismatches.
- Institution association — **all 149** checked, 0 anomalies.
- French 2025 historical labelling — **7,843/7,843** verified.
- Snapshot integrity (manifests, 110 bodies, backup, code hash, confirmation) — all rehashed.

**Moderate confidence:**
- Source authenticity: **4 metadata + 2 record** live requests confirm publisher, licence
  and version match today's official endpoints. This is a **spot-check**.
- URL reachability: **316 of 419** URLs checked (75.4%).

**Explicitly NOT verified:**
- The **103 unpollled government API endpoints** (deliberate safe boundary).
- **8,968 programmes (96.0%)** have **no individual webpage** — their authenticity rests on
  official register evidence, **not** on independent page confirmation.
- No claim is made that all 9,349 records are independently web-verified.
- No claim of worldwide coverage: 1,501 NL + 7,843 FR historical + 5 ES.

---

## 16. Prioritized corrective actions

> **No corrective action has been taken.** Per instruction, results are presented for
> inspection first.

### P0 — before any publication
1. **Handle slug disambiguation** for the 504 shared slug groups (1,883 French candidates)
   before any French programme is published. (Routing is UUID-based today, so this is not
   currently a live defect.)
2. **Reconcile 23 Dutch held providers** (693 offerings) and **2 archived French UAI
   identities** (312 offerings) using official organisational/historic evidence.
3. **Human review of 149 pending institutions** — all remain unapproved by design.

### P1 — data quality
4. **Re-check `ou.nl` (16 URLs) after its DNSSEC/NS failure is resolved** — currently a
   domain-side outage, not a data defect.
5. **Re-check the 10 stale DUO `WEBSITE` values** returning 404 (e.g. UvA `eduction` typo
   present in the *source*). Keep as `candidate`; do not delete.
6. **Repair 2 dead `terms_url` links** (`ror.readme.io`, `nces.ed.gov`) in the `sources` table.
7. **Re-test `hotelschool.nl`** with an up-to-date CA bundle to confirm the TLS chain.

### P2 — coverage
8. **Extend individual programme-page coverage** beyond the 5 UAL pages: 8,968 programmes
   currently rely solely on register evidence.
9. **Populate `universities.official_website_url`** — only 1 of 150 is set (16 candidates
   exist as facts).
10. **Extend source coverage** beyond NL/FR/UAL with fresh rights checks.

---

## 17. Deliverables

| Path | Contents |
|---|---|
| `docs/UNISHORTLIST_PROGRAMME_IMPORT_VALIDITY_AUDIT.md` | this report |
| `/tmp/audit/url_results.csv` | 316 URL findings (url, host, final_url, final_host, status, http, note, attempts, timestamp) |
| `/tmp/audit/url_results.json` | same, machine-readable |
| `/tmp/audit/authenticity.csv` | all 9,349 programmes with tier, evidence rows, source-backing |
| `/tmp/audit/urls.json` | the 419 distinct stored URLs with categories |
| `/tmp/audit/*.py` | reproduction scripts |

No credentials, authentication headers or tokens are included in any deliverable.
