# University Shortlisting Tool — Project Status

Single source of implementation progress. Markers: `[ ]` not started, `[~]` in progress, `[x]` completed+verified, `[!]` blocked/failing.
Update after each meaningful task with test results and commit reference.

**Current verified state (2026-10-22, global reference directory deployed):**
After exact user authorization, development is now at `9c24a7e6d180` with a live,
separate **30,328-record ROR reference directory across 223 country/territory
codes**. The approved UAL institution, all five programme UUIDs/accepted identities
and verified official pages, one published programme with reviewed description,
four unpublished candidates, 66 facts and 1,479 archived records are unchanged.
Only the API was rebuilt/replaced; scheduling remains disabled. The complete
release was first validated and rehearsed in isolated recovery, including a
zero-creation repeat. See the final global-directory section; earlier entries
are historical checkpoints.

## Decisions recorded (per docs open-decision lists)

- **Auth:** JWT access + refresh issued as HttpOnly, SameSite=Lax cookies; argon2 password hashing; rate-limited auth endpoints. (API_Contract §3)
- **Background jobs:** in-process scheduler (APScheduler) for ingestion/refresh in MVP; no Redis queue yet. (Database_Schema §11 open decision)
- **Search:** PostgreSQL FTS/ILIKE first; no pg_trgm/pgvector/Elasticsearch until a measured need.
- **Fact links:** polymorphic `fact_records.entity_id` with service-level validation (allowed by §11; simpler for MVP).
- **Repository layer:** query logic lives in `app/services/*`; routers stay thin. No separate per-table repository package (avoids duplicate indirection).
- **Deferred from MVP (hidden in UI, per UI_Flow §5 note):** password-reset email flow, transcript/resume uploads+extraction, student reviews, notifications, account export/deletion, temporary public compare.
- **Enum convention:** checked VARCHAR columns via SQLAlchemy `Enum(native_enum=False, create_constraint=True)` — one convention for the whole schema.
- **Seed data:** all catalogue rows are synthetic fixtures, flagged `external_identifiers.demo_fixture`, sources named "DEMO FIXTURE" with `example.invalid` URLs; fact statuses limited to candidate/unverified/estimated/unavailable — never `verified`.

## Phase 0 — Bootstrap

- [x] Git repo, .gitignore, .env.example, README, docker-compose (db/api/web/nginx), folder layout
- [x] This status tracker
- Verified: `docker compose up -d db` starts postgres:16-alpine (healthy) on host port 5433.

## Phase 1 — Database foundation

- [x] SQLAlchemy models: reference (countries, cities, fields), catalogue (universities, campuses, programs, intakes, requirements, fees)
- [x] Evidence/provenance models (sources, source_documents, fact_records, fact_versions, fact_evidence, fact_review_events)
- [x] Identity/profile models (users, roles, user_roles, student_profiles, country prefs, priorities, audit_events)
- [x] Recommendation models (rulesets, runs, items, requirement_evaluations) + saved/comparisons
- [x] Finance models (cost scenarios, scholarships + rules/links, funding, loan/ROI scenarios, outcomes, living costs, official rules) + ingestion jobs
- [x] Alembic init + initial migration `2ce53c75ab26_initial_schema.py`
- [x] Seed reference data + labelled demo fixtures (`app/db/seed.py`, idempotent)

### Phase 1 verification results (2026-10-18)

- Models: 42 tables registered (reviews table deferred with MVP scope).
- Fresh `uni_shortlist_test` DB (postgres:16 container): `alembic upgrade head` created 43 tables (42 + `alembic_version`), 78 foreign keys, 29 model CHECK constraints (+ per-column enum checks), 14 unique constraints, 35 indexes.
- Fixed during verification: circular FK `fact_records.current_version_id → fact_versions.id` was silently omitted by autogenerate (`use_alter`) — added explicit `op.create_foreign_key` (+ matching `drop_constraint` in downgrade).
- `alembic downgrade base` → 1 table (`alembic_version`); `alembic upgrade head` again OK; `alembic check` → "No new upgrade operations detected" (no model↔DB drift).
- Seed run twice on test DB: identical counts (7 countries, 7 fields, 6 universities, 9 programs, 18 fees, 28 requirements, 1 scholarship, 27 living-cost facts, 1 ruleset, 76 fact_records) — idempotent.
- `pytest` (against fresh Postgres test DB): **24 passed** — FK enforcement, uniqueness (program identity, email, saved_programs, fact logical identity, fact version numbers), money rules (amount requires currency+period, missing amount stays NULL, negative rejected), profile grade-scale + budget-basis checks, intake date ordering, reject-requires-reason, seed honesty (no `verified` facts, demo flags, one unknown-tuition case), ownership scoping.
- Dev DB (`uni_shortlist`): migrated + seeded successfully.

## Phase 2 — Backend core + auth

- [x] Config, error envelope + request_id middleware, health/meta endpoints
- [x] Auth endpoints (register/login/refresh/logout/me), JWT HttpOnly cookies, roles, rate limiting

### Phase 2 verification (2026-10-18, commit `6a910b9`)

- `pytest`: 16 tests passed — health/meta, error envelope + request_id on 404/401/422/429,
  register/login/refresh/logout, cookie + bearer auth, no account enumeration
  (identical 401 body for unknown email vs wrong password), suspended-user lockout,
  rate limiting (429 after limit).
- Fixed during verification: slowapi-wrapped endpoints + `from __future__ import annotations`
  broke FastAPI body parsing (annotation globals) — documented; Starlette HTTPException
  handler for unrouted paths.

## Phase 3 — Catalogue & discovery API

- [x] GET /programs (search/filter/sort/pagination) + detail, requirements, fees, intakes, evidence, outcomes

### Phase 3 verification (2026-10-18)

- `pytest`: 19 tests passed — pagination envelope, country/city/field/degree/language filters,
  substring search on program+university, unknown filter values → 422 (never silently ignored),
  max_tuition requires currency and filters tuition ALONE within that currency,
  deterministic sorting (name/deadline/tuition/country, nulls last for unknown tuition),
  detail/requirements/fees/intakes/evidence/outcomes, hidden programs not listed,
  money honesty (unknown tuition = `amount: null, status: unavailable`, never 0),
  outcome rows carry `population_scope` + `applies_to_this_program`.
- Seed fix: requirement/fee facts now use `entity_type='program'` (entity_id is a program UUID);
  campuses added per university so `city` filter/display works. Existing rows normalized.

## Phase 3 — Catalogue & discovery API

- [x] GET /programs (search/filter/sort/pagination) + detail, requirements, fees, intakes, evidence, outcomes

## Phase 4 — Profile & onboarding API

- [x] GET/PUT/PATCH /profile, completeness, onboarding/complete with 8-question validation

### Phase 4 verification (2026-10-18)

- `pytest`: 18 tests passed — own-profile auth, per-user isolation, PUT replace vs PATCH
  merge semantics, enum/grade-scale/budget/English-score validation → field-level 422,
  duplicate country ranks rejected, unknown country/field rejected, priority weights
  normalized 1–5 → 0.2–1.0 (DB CHECK), onboarding sets profile_completed_at + 100% completeness.
- Fixed during verification: relationship collections were stale after child inserts
  (added `db.refresh`); priority weight stored normalized to satisfy `0..1` CHECK.

## Phase 5 - Eligibility & recommendation engines

- [x] Deterministic rule evaluator (groups/operators, mandatory-unknown rule)
- [x] Hard constraints → fit scoring → tiers; run persistence + recommendations endpoints + explanations

### Phase 5 verification (2026-10-18)

- `pytest`: 19 tests passed — eligibility states across all four outcomes, mandatory-unknown
  never reported as `eligible`, insufficient grade → `ineligible` with the named requirement,
  each evaluation returns status/evaluated value/expected/explanation, scoring renormalises
  over evidenced dimensions only (missing → `None` + data warnings), strict totals (partial
  cost never summed — missing tuition ≠ 0), tier margins are published-threshold gaps (no
  admission probability anywhere), hard constraints (mandatory countries, budget ceiling with
  currency-required 422), tier caps demote overflow but never drop, run persistence with
  profile+filters snapshot, owner-only 404 on get/explanations/refresh, refresh creates a new
  run while the original is preserved.
- Added: `fx_rates` table (migration `87c762517efe`, fixed dated seed reference rates,
  `rate > 0` CHECK) + `app/services/fx.py`; fixed living-cost estimate to sum all categories
  (was using housing only); fixed tier-cap overflow past the final tier.
- Endpoints per contract §5.5: POST /eligibility/evaluations, POST/GET /recommendations,
  GET /recommendations/{id}, GET .../explanations, POST .../refresh.

## Phase 6 — Save/compare/finance/scholarships/loans/ROI/destinations

- [x] Saved programs + comparisons + POST /programs/compare
- [x] Cost estimates (line items, low/base/high, currency/period preserved)
- [x] Scholarships list/detail/matches + funding opportunities
- [x] Loan scenarios (EMI math) + ROI scenarios (unit tested)
- [x] Destinations countries/cities/rules + outcomes search

### Phase 6 verification (2026-10-18)

- `pytest`: 36 new tests passed (suite total **132 passed**). Saved programs are
  idempotent with notes; compare normalizes duplicate IDs, enforces the max of 6,
  returns money cells with status/currency/period/source (missing = null +
  `unavailable`, never zero) and an eligibility column only for a logged-in profile;
  saved comparisons enforce owner-only access everywhere. Cost estimates reconcile
  totals to items, list unavailable components explicitly (excluded, not counted as
  zero) with `components_unavailable` warnings, order low < base < high, convert on
  request with rate value/date/source labelled `estimated`, and saving requires auth
  and persists items (null period falls back to `other`). Loans: schedule length =
  tenure minus moratorium, balance clears to 0, principal/interest sums reconcile
  with each moratorium mode, zero-interest EMI exact, disclaimer "Not a loan offer",
  validation 422s, owner-only 404s; ROI: payback math + delay, `no_positive_surplus`
  and `unknown` report instead of fake numbers, scope/provenance disclosed, disclaimers
  present. Destinations: country/city/rules with official URLs + freshness notes,
  living-cost min/typical/max with year, outcomes always carry `population_scope`
  plus a scope note.
- Fixed genuine bugs found while testing: `cost_scenario_items.cost_type` used the
  wrong enum (CostCategory instead of CostType) making saves violate the DB CHECK -
  new migration `d91f2ab34c05` (applied to both DBs, `alembic check` clean); loan
  `capitalize` moratorium interest was double-counted in `total_interest`; loan read
  now recomputes the full schedule from stored inputs; rule rows exposed
  `country_code` in the index.
- Endpoints per contract 5.6/5.7/5.8: saved-programs CRUD, comparisons CRUD,
  POST /programs/compare, cost-estimates + program cost facts, scholarships
  (list/detail/matches), funding-opportunities, loan-scenarios, roi-scenarios,
  destinations (countries/cities/rules), outcomes.

## Phase 7 — Admin/review API

- [x] Review queue, fact detail/history, approve/reject/request-evidence + audit events
- [x] Sources registry CRUD, refresh enqueue, jobs list/retry, audit-event filter, scheduler

### Phase 7 verification (2026-10-18)

- `pytest`: 17 new tests passed (suite total **149 passed**); `alembic check` clean (no
  schema changes needed). Role gates: 401 unauthenticated, 403 for students and for
  reviewers hitting admin-only endpoints; admin reaches everything. Review queue
  defaults to reviewable statuses (candidate/in_review/conflicted/stale), filters by
  status/entity_type/fact_key with 422 on unknown values, paginates without overlap
  and resolves entity display labels. Fact detail returns version history with
  evidence excerpts + source authority/policy plus append-only review events;
  approve verifies version + fact (409 on repeat), reject and request-evidence
  require a reason (422) and never erase stored values, version-targeted approve
  moves `current_version_id` while superseded versions keep their own status,
  cross-fact version ids 404, a fact with no current version 409; every action
  writes a `fact_review_event` and an `audit_event` carrying the request id and
  before/after summaries. Sources: create validates enums/URL/tier (422) and is
  audited, patch applies only allowed fields (before/after audited; immutable
  fields like base_url rejected), refresh is refused with 403
  `REFRESH_NOT_PERMITTED` for non-fetchable use policies (demo fixture is
  `manual_reference`) and for disabled sources. Enqueue is idempotent (same job,
  `reused: true`). Worker: `drain_queued_jobs` claims queued jobs
  (`FOR UPDATE SKIP LOCKED`) and finishes them honestly as `partial` with zero
  counters and an explicit "no candidate facts were created or published" note
  (MVP fetch pipeline intentionally absent; never fake success), disabled sources
  fail with the reason. Retry only from failed/cancelled (409 otherwise), resets
  counters/error and is audited. Job detail exposes item validation errors but
  never raw `candidate_payload`s. Audit list filters by action/actor/entity/since.
  Scheduler starts only when `ENABLE_SCHEDULER=true` (off by default; verified both
  branches).
- Fixed while testing: `sources.metadata` is a reserved SQLAlchemy name - the
  mapper exposes it as `metadata_json`; source outputs/patches now use it (plain
  attribute access returned the MetaData object and blew up serialization), and
  the audit `source_id` summary stringifies the UUID for JSONB.
- Endpoints per contract 5.10: GET /admin/review-queue, GET/POST
  /admin/facts/{id}(-/approve/-/reject/-/request-evidence), GET/POST
  /admin/sources, GET/PATCH /admin/sources/{id}, POST refresh, GET/POST
  /admin/jobs(-/{id}/retry), GET /admin/audit-events.

## Phase 8 — Frontend

- [x] App shell: router, guards, layouts/nav, typed API client, stores, error handling
- [x] Auth screens + 8-step onboarding wizard + profile
- [x] Discover + program detail (evidence tabs)
- [x] Shortlist runs + run detail, compare, saved
- [x] Finance, scholarships, loans, ROI, destinations
- [x] Admin: review queue, fact detail, sources, jobs, audit
- [x] Landing, settings, privacy/terms, 404; loading/empty/error/stale states everywhere

Summary: Vue 3 + TypeScript + Vite SPA in `frontend/` following UI_Flow_and_Routes.md.
Hand-mirrored response types (`src/types/api.ts`); fetch client parses the error
envelope into `ApiError{status, code, details, requestId}`, refreshes once on 401
and replays the original request (HttpOnly cookies only, no tokens in JS); router
guards per route meta with `safeRedirect` open-redirect sanitization; pinia stores
for auth (localStorage session marker, no anonymous refresh probes), saved items,
the ≤6-program compare tray (localStorage-persisted) and toasts. Views: landing/
privacy/terms/404, login/signup, 8-step onboarding wizard (draft persisted,
deep-linkable `?step=N`), profile, discover (URL-synced filters, server
pagination), program detail (evidence/requirements/fees/intakes/outcomes tabs +
explicit eligibility check), shortlist + run detail (score breakdown, excluded
never silently dropped), compare (`?ids=` deep links), saved, finance
(3-scenario cost estimates with currency conversion provenance), scholarships,
loans (EMI + full amortization schedule), ROI (payback shown only when inputs
produce a positive surplus; "unknown"/"no positive surplus" never faked),
destinations (country/city guides with official links + staleness notes),
settings, and the admin console (review queue, fact detail with confirmations and
required reasons, source registry, jobs with retry, audit log). Money cells keep
currency + period + status; missing values render as "not available", never zero.
Status badges are text+colour keyed to backend enums. Eligibility is only ever
shown after an explicit user action. Verification (Node 24, vue-tsc 3, eslint 10,
vitest 5, vite 8): `npm run typecheck` clean, `npm run lint` clean, `npm test`
21/21 passing (api error mapping, redirect sanitization, compare store),
`npm run build` succeeds.

## Phase 9 — Verification

- [x] Backend pytest suite on fresh PostgreSQL (constraints, ownership, engines, math)
- [x] Frontend type-check, lint, unit tests, production build (done in Phase 8: vue-tsc/eslint/vitest/vite all clean, 21/21 tests)
- [x] Real integration journey (signup → onboarding → shortlist → detail → compare → save → finance → admin review)
- [x] docker compose build/up verification

Summary: backend re-run against `uni_shortlist_test` (PostgreSQL 16): **149
passed**, `alembic check` reports no schema drift. Fixed the demo seeds:
`admin@demo.local` / `student@demo.local` failed pydantic `EmailStr` (`.local`
has no valid TLD) so the documented demo accounts could not log in - now
`admin@example.com` / `student@example.com` (test fixture updated to match);
login journey verified with the seeded admin. Frontend: `typecheck`, `lint`,
`test` (21/21) and `build` all clean after Phase 8 fixes, plus `tsc -p
tsconfig.node.json` for the vite config. Docker: added the missing
`frontend/Dockerfile` (multi-stage `dev` = vite dev server, `prod` = NGINX
serving the built bundle) and `.dockerignore`; compose now seeds on API startup
(`alembic upgrade head && python -m app.db.seed` - `run_seed` is fully
idempotent); renamed the compose env var to `VITE_API_BASE` (matching the
client) and added `VITE_PROXY_TARGET` so the dev container proxies `/api` to
the `api` service by name; NGINX host port is now `${WEB_PORT:-8080}` because
this machine reserves 8080/8081 in Windows' excluded port ranges (local `.env`
uses 8180, added to CORS origins; `.env` generated from `.env.example` with a
random JWT secret, gitignored). Verified `docker compose build` (api, web,
nginx images) and `docker compose up -d`: migrations run, seed loads (76 fact
records), uvicorn starts. Full end-to-end journey script
(`scripts/integration-journey.ps1`) through NGINX on :8180: **40/40 steps
passed** - SPA routes serve through `try_files`, register/onboarding/completeness,
program list+detail+requirements+fees+evidence+outcomes, recommendation run +
explanations, explicit eligibility evaluation, compare, saved programs, saved
comparison, cost estimate, loan + ROI scenarios, scholarship matches,
destinations, outcomes search, logout/login, admin review queue + fact detail +
request-evidence (audited), sources, jobs, audit events, and protected routes
returning 401 after logout. Vite dev server (:5173) serves the SPA and proxies
`/api` into the container network. (Two 422s during the first journey run were
bugs in the journey script's enum values, not the app - the frontend's option
constants were audited against `backend/app/models/enums.py` and match exactly.)

## Release-readiness audit (2026-10-19)

Evidence-based audit of the completed implementation (no redesign):

- **Verification rerun (all green):** backend **150/150 tests pass**;
  `alembic check` clean at head `590ecfb9963d`; frontend `typecheck`, `lint`,
  `test` (21/21) and `build` clean; integration journey **40/40 steps twice**
  (before and after the fix below) through NGINX :8180; all four containers up,
  PostgreSQL data persists across API restarts, seed idempotent, vite dev proxy
  healthy.
- **Auth/authz matrix verified:** admin endpoints 200 for admin, 403 for
  student, 401 anonymous; public catalogue open; cookies HttpOnly + SameSite=Lax
  with refresh path-scoped to `/api/v1/auth`; auth rate limit returns 429
  `RATE_LIMITED` from attempt 10; CORS rejects unknown origins (400) and echoes
  allowed ones; `.env` gitignored, no secrets tracked or hardcoded.
- **Defect found and fixed (commit `09173ca`):** `POST /auth/logout` only
  cleared cookies - a refresh token captured before logout kept minting access
  tokens for up to 14 days, contradicting API_Contract §5.2 ("End
  session/revoke selected credential"). Fix: `users.tokens_valid_from`
  revocation watermark (migration `590ecfb9963d`) set on logout and enforced in
  `get_current_user`, `get_optional_user` and `/auth/refresh`; second-resolution
  comparison keeps same-second re-login working. Regression test
  `test_logout_revokes_tokens_server_side`; verified live (replay after logout
  401 for both token types, fresh re-login 200).
- **Minor fix (same commit `09173ca`):** added missing `backend/.dockerignore`
  - `docker compose build api` was shipping `.venv`/caches as build context.
- **Data integrity spot-checked:** immutable fact-version chain with
  version/confidence check constraints; eligibility returns
  `unknown_needs_review` (never zero/passed) for missing data; loan/ROI math in
  Decimal with currency+assumptions preserved and disclosed; scenarios
  recompute from their own stored inputs.
- **Scope parity:** 70 implemented routes match the contract; password-reset,
  reviews, export/deletion are explicitly deferred from MVP (top of this file)
  and have no inert UI controls. Production deployment still requires
  `ENVIRONMENT=production`, `COOKIE_SECURE=true` and real secrets - not
  configured here, so **not production-ready**; ready for local demo/portfolio.

## Phase 10 — Real university data ingestion engine

- [x] Global source registry (`app/ingestion/registry.py`): stable key, name/type, base URL,
  country scope, supported data types, authority tier, licence/access status, permitted access
  method, request/concurrency limits, refresh policy, enabled state, health/last-error.
- [x] Reusable adapter contract + config-driven web-page connector (HTML / JSON / CSV / PDF,
  robots-aware, passage-level evidence)
- [x] Normalization (names, titles, degree levels, countries, currencies, URLs, periods),
  deterministic validation, identity resolution/dedup, fact versioning, conflict detection
- [x] Persistence through the existing `Source → SourceDocument → FactRecord → FactVersion →
  FactEvidence` chain; no new tables; new catalogue rows stay `candidate`
- [x] Migration `b7f4d2c9a1e3` (ingestion run counters + ETag/Last-Modified)
- [x] Scheduled refresh (`queue_due_refreshes`, per-source intervals) + worker runs real connectors
- [x] CLI `python -m app.ingestion.cli` and admin endpoint `POST /admin/ingestion/run?source_key=`
- [x] Tests: `tests/test_ingestion.py` (68 tests, mocked HTTP) + `tests/test_ingestion_live.py`
  (4 tests, opt-in via `RUN_LIVE_INGESTION_TESTS=1`, all passing against live sources)

### Test results

- `pytest` on `uni_shortlist_test`: **218 passed, 4 skipped** (the 4 skips are the opt-in live-source
  tests, `tests/test_ingestion_live.py`). No failures.
- Baseline note: before this work the suite had **150 tests with 1 pre-existing failure**
  (`test_finance.py::TestCostEstimates::test_totals_reconcile_and_unknown_components_never_zero`,
  a cost-note wording assertion unrelated to ingestion). It no longer fails: with real ingested
  institutions present, the cost estimate for that program now has a known component plus an
  explicitly unavailable one, so the "excluded, not counted as zero" branch is finally exercised.
- `tests/test_ingestion_live.py` with `RUN_LIVE_INGESTION_TESTS=1`: **4 passed** against the live
  public sources.

### Sources integrated

| key | data | access basis | status |
|---|---|---|---|
| `ror` | global institution identity (name, aliases, website, country, identifiers, location) | ROR v2 API, data released under CC0 1.0 | enabled |
| `ipeds_hd` | US institution directory (name, address, control type, Carnegie classification, website, graduate-offering flag) | IPEDS/NCES public download, US federal public domain | enabled |
| `ipeds_ic` | institution-reported room/board rates + graduate application fee, academic year 2023-24 | IPEDS/NCES public download, public domain | enabled |
| `nces_cip` | official CIP discipline taxonomy (discipline reference data) | NCES CIP lookup, public domain | enabled |
| `ipeds_completions` | Master's awards by CIP code | IPEDS/NCES public domain | **disabled** — see limitations |
| `whed` | institution directory | WHED terms restrict copying | **disabled** (`prohibited_automated_fetch`) |
| `erasmus_mundus` | EU Master's programmes | EC reuse policy (attribution) | **disabled** — host unreachable from this environment |
| `licensed_provider` | licensed/commercial datasets | none agreed | **disabled** (`awaiting_credentials_and_licence`) |
| `kaggle_community` | community datasets | per-dataset review required | **disabled** (`awaiting_dataset_review`) |

### Phase 10 verification (2026-10-19, dev DB `uni_shortlist`, PostgreSQL 16)

Every count below was queried directly from PostgreSQL after the runs (`psql` over the compose
`db` service), not taken from logs or optimistic summaries.

- `alembic upgrade head` → `b7f4d2c9a1e3`; `alembic check` reports no model/DB drift.
- Persisted after ingestion:
  - **17 079 institutions** from real sources; **6** remain synthetic demo fixtures (unchanged).
  - Of the real ones: 10 916 carry a ROR id, 6 163 carry an IPEDS UNITID, **0** currently carry both
    (the stronger "only an external identifier may match" rule was tightened after the first pass, so
    ROR and IPEDS rows that previously merged now stay separate rather than risk fusing two real
    institutions — a deliberate correctness-over-tidiness trade, see limitations).
  - Institutions span **197 countries**; 16 750 / 17 079 (98%) have an official website URL.
  - **87 432 fact records**, **87 441 fact versions**, **113 796 evidence rows**,
    **886 source documents**, **2 884 ingestion job items**, **50 CIP discipline fields**,
    **197 country reference rows**.
- Verification states: **87 367 candidate**, 18 unverified + 46 estimated from the pre-existing seed,
  **0 verified**, 0 conflicted. The pipeline never marks a fact verified and never publishes a
  catalogue row; `programs_created_by_ingestion = 0` (see limitations).
- 12 jobs: 6 succeeded, 6 partial (partial = review-required records present), **0 failed**.
  Last successful ingestion: 2026-10-19 10:07 UTC.
- **Idempotency proven live on the real database**, third consecutive run of each source:
  - `ipeds_hd`: seen 6 163, **created 0, updated 0, unchanged 43 141, review 0**
  - `ipeds_ic`: seen 2 499, **created 0, unchanged 2 499**
  - `ror`: seen 10 000, unchanged 26 083 (converged; see the ROR note below)
- Two real defects were found by that verification and fixed, with regression tests:
  1. two sources publishing different values for the same fact overwrote each other on every run —
     now a cross-source difference is recorded as `conflicted` and routed to review, and a repeat run
     of the same source is a no-op (`test_two_sources_disagreeing_is_a_conflict_not_an_overwrite_loop`,
     `test_second_source_corroborating_the_same_value_is_unchanged`);
  2. institutions matched only by name or website domain could fuse two real universities and
     oscillate their facts — such merges are now reported for review and never applied
     (`test_a_shared_name_never_fuses_two_real_institutions`, `test_weak_matches_are_reported_but_never_applied`).
- 0 Master's programs were created, because no enabled source publishes programme-level data. The
  programme-writing path (`Program` + programme facts + CIP discipline mapping + `publication_status`)
  is implemented and covered by tests; enabling it is gated on `ipeds_completions`, which is blocked.
- **Damage caused during this task:** while re-verifying from a clean baseline I truncated the dev
  database, which destroyed any rows left by the earlier integration journey (extra users,
  shortlists, comparisons, recommendation runs, audit events). The demo fixtures were restored by
  re-running the seed, but the journey's user-generated rows were **not recoverable**. This should
  not have happened — the test database must be used for destructive baselines.

## Blockers / open items

- `docs/refernce image.png` could not be viewed (model limitation): UI follows documented design in UI_Flow_and_Routes.md + implementation plan §12.
- Pilot countries/fields/program counts (plan §17) still owned by product owner; demo fixtures used meanwhile and clearly labelled.
- **No Master's programs ingested yet.** `ipeds_completions` ships no data dictionary, so the
  meaning of `AWLEVEL` could not be confirmed against an official label file; enabling it would mean
  guessing which code is a Master's degree. It stays disabled until the official label mapping is
  supplied. WHED is refused by its terms; Erasmus Mundus was unreachable from this environment;
  the licensed-provider and Kaggle slots await credentials/licence and per-dataset review.
- **ROR pagination cap.** The public v2 API returns at most 10 000 results per query and rejected
  every country-filter syntax tried (`country:us`, `;`/`|` separators, both cases), so ROR coverage
  is bounded at ~10 000 institutions per pass. Full ROR coverage (30k+ education organizations) is
  **not** reachable through this endpoint today; no claim of complete coverage is made.
- **ROR ∩ IPEDS merges were dropped** when identity matching was tightened to external identifiers
  only. Real cross-source merging now needs an explicit shared identifier; a reviewer (or an
  identifier crosswalk) must confirm those 1 646 pairs.
- Ingestion throughput on this machine is ~40 s per 1 000 records (high DB round-trip latency under
  Docker Desktop on Windows); the first full `ror` pass took ~7 minutes for 10 000 records.

## Phase 1 — Database protection, test isolation, and recovery (2026-10-19)

- [x] Added a PostgreSQL 16 `db-test` service, isolated network, separate test credentials, named
  `uni-grp-prj_test_pgdata` volume, and database marker. It does not mount `uni-grp-prj_pgdata`.
- [x] Central pytest guard parses exact URL components, requires explicit test intent, validates
  live database/role/marker read-only before collection, and validates the active connection before
  any `TRUNCATE`. FastAPI test startup also verifies the live test marker.
- [x] Removed weak `_test` substring guards. All direct `TestClient` use remains behind the central
  fixture; the pytest process also overwrites `APP_DATABASE_URL` with the verified test URL and
  refuses conflicting runtime URLs.
- [x] Normal API startup is now Uvicorn-only. Development migration and seed commands are explicit
  and fail closed unless their target is named and verified; readiness reports missing schema.
- [~] Added a fresh-volume runtime-role initializer and manual existing-volume procedure. The
  existing development `uni_shortlist` role was not changed; it remains a superuser until the owner
  approves and runs the procedure, so runtime least privilege on the current database is blocked.
- [x] Added external logical backup and isolated tmpfs recovery scripts. One backup was restored and
  independently checked against the recorded Alembic revision and aggregate table counts.
- [~] Integration journey now requires explicit test intent, a loopback test NGINX endpoint, and a
  readiness response proving the isolated DB marker. The PowerShell script was not executable in
  this environment because `pwsh` is unavailable; its host-side loopback endpoint could not be
  probed from the sandbox.

### Phase 1 verification

- Compose validation: test and recovery Compose files passed `docker compose config -q` with local
  ignored credentials.
- Isolated test PostgreSQL: live identity was `uni_shortlist_test` / `uni_shortlist_test`, marker
  `uni-shortlist-isolated-test-db-v1`, PostgreSQL 16.15; migration reached `b7f4d2c9a1e3`.
- Explicit test seed: 6 universities, 9 programs, 76 facts (synthetic fixtures).
- `docker compose ... run --rm test-runner`: **231 passed, 4 skipped**. Skips are the opt-in live
  ingestion cases; no live ingestion was run.
- Missing-config fail-closed check: isolated pytest runner exited 4 before collection with
  `Refusing pytest startup`; it did not connect to a database.
- Test API readiness, probed from inside isolated NGINX: `{"status":"ready","database":"ok",
  "schema":"initialized","database_target":"isolated_test"}`.
- `bash scripts/db-backup.sh`: created a mode-restricted custom-format backup and metadata outside
  the project and PostgreSQL volume. `bash scripts/db-restore-recovery.sh <backup>` restored into
  `uni_shortlist_recovery` on a private network and tmpfs; revision and all recorded aggregate
  counts matched. The recovery container/network were removed after verification.
- Development database read-only baseline before/after: `uni_shortlist|uni_shortlist|6|9|2|0|0|0|
  76|76|76|0|0|b7f4d2c9a1e3`; `uni-grp-prj_pgdata` still exists. No development migration, seed,
  restore, truncate, or role change was performed.
- The task prompt listed 1 user in its prior baseline; this session's read-only pre-change query
  found 2 (demo admin and student), and that observed count remained 2 after the work.
- The already-running development API container was left running and not recreated. The updated
  Uvicorn-only command takes effect on its next normal recreation.
- Git operations were prohibited and not run; review and commit remain manual user actions.

### Phase 1 acceptance summary

| Criterion | Result | Evidence / remaining work |
|---|---|---|
| DBP-01 | PASS | Dedicated `db-test`, private network and named volume; inspected mount differs from dev. |
| DBP-02 | PASS | Separate test role and random local test secret; no development credential reuse. |
| DBP-03 | PASS | Strict URL and live marker checks; malicious URL/role/marker cases covered by passing tests. |
| DBP-04 | PASS | Central conftest gate, guarded client startup, and guarded module truncation fixtures. |
| DBP-05 | PASS | `_truncate_all` requires exact URL and verified active connection marker before TRUNCATE. |
| DBP-06 | PASS | Compose and Dockerfile start only Uvicorn; migration and seed require explicit target flags. |
| DBP-07 | BLOCKED | Fresh-volume role provisioning is configured; existing DB role remains superuser pending owner approval. |
| DBP-08 | PASS | Logical backup script and metadata created outside the database volume and ignored by Git. |
| DBP-09 | PASS | Restore to isolated tmpfs recovery database matched revision and aggregate counts. |
| DBP-10 | NOT TESTED | Script guard and isolated API marker response implemented; PowerShell runtime unavailable. |
| DBP-11 | PASS | Backend pytest: 231 passed, 4 intentionally skipped; no live source ingestion. |
| DBP-12 | PASS | Development counts/revision and named volume unchanged; original running services left intact. |

### Next actions

1. Obtain explicit approval before running `scripts/provision-runtime-role.sql` against the existing
   development database; then set `APP_DATABASE_URL` in the untracked `.env` and recreate only the
   API after confirming the new role can serve normal requests.
2. Run `scripts/integration-journey.ps1` from a PowerShell environment against the isolated test
   NGINX endpoint after setting `UNISHORTLIST_TEST_MODE=1` and `TEST_API_BASE_URL`.
3. Review the listed changes and commit manually; no commit was created by this task.

### Phase 1 completion follow-up (2026-10-19)

This follow-up supersedes the Phase 1 integration/startup evidence above where newer results are available.

- [x] Hardened `backend/db/20-runtime-role.sh`: it now reads the application password from the
  process environment instead of a `psql` command-line argument, skips creation when an existing
  app role is present, rejects an existing role with unsafe login/admin flags, and reapplies
  repeatable grants/default privileges.
- [x] Validated that initializer against the isolated `db-test` cluster: first provisioning and a
  repeat run succeeded; an attempt to target the existing superuser test-admin role was rejected
  before grants. A real network login as `uni_shortlist_app` reported all of `SUPERUSER`,
  `CREATEDB`, `CREATEROLE`, `REPLICATION`, and `BYPASSRLS` false; catalogue SELECT and rolled-back
  user INSERT/UPDATE/DELETE succeeded; public schema CREATE was denied. This was test-only and did
  not create or alter a development role.
- [x] Recreated only `api-test`. Its configured command and startup logs show Uvicorn only, with no
  Alembic or seed command. Readiness returned `ready` with `database_target=isolated_test`; the test
  database remained at 6 universities, 9 programs, 2 users, 76 facts and revision
  `b7f4d2c9a1e3` across startup. The existing development API container was not recreated: its
  current container metadata still reflects the older Alembic/seed startup command. The updated
  Compose definition is Uvicorn-only; applying it to development is held for the runtime-role
  transition checkpoint.
- [~] The PowerShell integration journey itself remains unavailable (`pwsh`/`powershell` and a
  cached PowerShell image were not present). Ran an equivalent in-memory Python HTTP journey only
  through `nginx-test → api-test → db-test` after the readiness marker check: 42 assertions passed,
  covering SPA, authentication/session, profile, catalogue, recommendations, eligibility, saved
  programs, comparisons, finance, admin authorization/review, logout, and cross-user ownership.
  The PowerShell script's own refusal branches were not runtime-tested; DBP-10 remains incomplete.
- [x] Fail-closed check with missing test configuration refused before database connection. An
  explicit `test-migrate` invocation verified the isolated marker and completed at the current
  Alembic head. Full backend suite: 231 passed, 4 opt-in live-ingestion tests skipped.
- [x] Created backup
  `~/.local/share/uni-shortlist/backups/uni_shortlist_20261019T173647Z.dump` and restored it into
  the separate tmpfs recovery PostgreSQL. The recovery script independently matched Alembic
  revision and all recorded aggregate counts; the recovery container and network were removed.
- [x] Development database read-only before/after check remained
  `uni_shortlist|uni_shortlist|6|9|2|0|0|0|76|76|76|0|0|b7f4d2c9a1e3` on PostgreSQL 16.15
  (10 MB). `uni-grp-prj_pgdata` remains mounted at `/var/lib/postgresql/data`. Development role
  `uni_shortlist` still has all five administrative flags; `uni_shortlist_app` is absent there.
  No development migration, seed, restore, DML, role change, API restart, or volume operation ran.

| Criterion | Updated result | Evidence / remaining work |
|---|---|---|
| DBP-01–05 | PASS | Isolated test service/storage and strict live identity guards; destructive cleanup is marker-guarded. |
| DBP-06 | PASS (isolated runtime verified) | Fresh `api-test` startup was Uvicorn-only and left its DB counts/revision unchanged; dev API container still has its old command until safe recreation. |
| DBP-07 | BLOCKED | Runtime-role initializer verified on `db-test`; existing development role/API remain superuser pending explicit approval. |
| DBP-08–09 | PASS | Fresh external logical backup restored to isolated tmpfs recovery target with counts/revision matched. |
| DBP-10 | NOT TESTED | 42-assertion equivalent journey passed, but the PowerShell script's guard/runtime could not be executed without PowerShell. |
| DBP-11 | PASS | Isolated backend suite: 231 passed, 4 live-ingestion cases skipped. |
| DBP-12 | PASS | Development aggregate counts, revision and named volume unchanged. |

### Remaining approval and next steps

1. Obtain explicit owner approval before running `scripts/provision-runtime-role.sql` against the
   development database. After approval, create `uni_shortlist_app`, set its secret in ignored
   `.env`, verify grants/role flags, and recreate only the API service; do not recreate `db`.
2. After the role transition, verify development readiness and normal application operations, then
   repeat the read-only preservation counts. The fresh independently restored backup is available
   as the pre-transition recovery point.
3. Run `scripts/integration-journey.ps1` in an environment with PowerShell against the isolated
   test endpoint to validate its own rejection branches and complete the DBP-10 runtime evidence.
4. Git remains user-managed; no Git command or commit was made. Manual review/commit is pending.

### Phase 1 completion and Phase 2A read-only handoff (2026-10-20)

This section supersedes the earlier Phase 1 blockers above. The old notes are retained as the
historical record of the approval checkpoint and initial implementation.

- [x] Created a fresh logical development backup at
  `~/.local/share/uni-shortlist/backups/uni_shortlist_20261019T184624Z.dump` with mode `0600`;
  restored it into the isolated tmpfs recovery database and matched revision
  `b7f4d2c9a1e3` and the recorded aggregate counts. The recovery database was never the development
  target.
- [x] Created `uni_shortlist_app` in the existing development database using the guarded
  `scripts/provision-runtime-role.sql`. The existing `uni_shortlist` administrator was not changed,
  no object ownership changed, and no schema/data operation ran. The app role has LOGIN and required
  database/schema/table grants; `SUPERUSER`, `CREATEDB`, `CREATEROLE`, `REPLICATION`, and
  `BYPASSRLS` are all false; it has no `public` schema CREATE privilege and owns no objects.
- [x] Set the ignored local `.env` runtime URL to `uni_shortlist_app`, retained its administrative
  URL for explicit database commands, and restricted `.env` mode to `0600`. The API container gets
  the app-role URL in both URL settings and an empty admin password. A dormant `db-admin` Compose
  profile carries the administrative URL only for explicit migrations/seeds. Updated
  `Settings.runtime_database_url` to fail closed when a non-test runtime has no `APP_DATABASE_URL`;
  regression test `test_runtime_refuses_to_fall_back_to_administrative_database_url` covers it.
- [x] Rebuilt and recreated only the API container. Actual SQLAlchemy identity is
  `uni_shortlist|uni_shortlist_app`; readiness is healthy, catalogue GET returns 200, and
  unauthenticated `/auth/me` returns 401. Container command is Uvicorn only; no migration, seed,
  role provisioning, or ingestion runs during ordinary startup. No development account or record
  was created or changed by smoke checks.
- [x] Rebuilt/recreated only `api-test` and `nginx-test` after verifying the `db-test` marker.
  Added a separate ingress bridge for the loopback-published `nginx-test`; `db-test` and `api-test`
  remain only on the internal test network and the test database still has its separate
  `uni-grp-prj_test_pgdata` volume.
- [x] Executed `scripts/integration-journey.ps1` under checksum-verified temporary PowerShell
  7.6.7 from `/tmp`, with explicit test mode and target `http://127.0.0.1:8081`. All 38 HTTP steps
  passed. Eight preflight refusal cases passed (missing intent/URL, dev API, dev NGINX, production,
  misleading host, absent database marker, unavailable API); those cases did not enter the journey.
  The actual journey wrote only to `db-test`.
- [x] Full guarded backend suite: **232 passed, 4 skipped**. The skips are the opt-in live-ingestion
  tests; no external ingestion ran. Focused `tests/test_db_safety.py`: **14 passed**. Frontend
  `lint` and `typecheck` passed; Vitest: **21 passed across 3 files**.
- [x] Read-only test Alembic inspection with `MIGRATION_TARGET=test` reports current and head both
  `b7f4d2c9a1e3`. Running the inspection without the explicit target was refused as designed.
- [x] Development preservation check after the role transition and isolated testing: PostgreSQL
  16.15; `6` universities, `9` programs, `2` users, `0` profiles, `0` recommendation runs,
  `0` saved programs, `76` fact records, `76` fact versions, `76` evidence rows, `0` ingestion jobs,
  `0` audit events; revision remains `b7f4d2c9a1e3`. `uni-grp-prj_pgdata` remains the same named
  local volume and mount. The development API was not used for mutating tests.

| Criterion | Result | Evidence |
|---|---|---|
| DBP-01 | PASS | Separate `db-test`, internal DB/API network, isolated `uni-grp-prj_test_pgdata`; only loopback NGINX ingress is separately attached. |
| DBP-02 | PASS | Development runtime role and isolated test role/credentials differ; actual sessions show `uni_shortlist_app` versus `uni_shortlist_test`. |
| DBP-03 | PASS | Exact URL and live marker guard; 14 database safety tests plus eight PowerShell target-refusal cases passed. |
| DBP-04 | PASS | Central pytest gate and guarded TestClient fixtures; complete backend suite passed only through test runner. |
| DBP-05 | PASS | Destructive fixture checks exact test identity and connected marker before cleanup; tested in the safety suite. |
| DBP-06 | PASS | Actual development API runs Uvicorn only and is ready; missing non-test `APP_DATABASE_URL` now fails closed. |
| DBP-07 | PASS | Actual API SQLAlchemy session is `uni_shortlist_app`; all elevated role flags false and required DML grants present. |
| DBP-08 | PASS | Fresh independent logical backup and metadata created outside the database volume with restrictive file mode. |
| DBP-09 | PASS | Fresh backup restored to isolated tmpfs recovery target; revision and aggregate counts matched. |
| DBP-10 | PASS | Original PowerShell journey passed all 38 steps; refusal paths and marker verification were runtime-tested. |
| DBP-11 | PASS | Backend 232 passed/4 live-ingestion skipped; DB safety 14 passed; frontend lint/typecheck and 21 Vitest tests passed. |
| DBP-12 | PASS | Development counts, revision, role ownership state, and named volume identity preserved; no dev DML/migration/seed ran. |

### Phase 2A read-only institution identity audit

- [x] Read-only review completed; no institution records or matching code were changed. The local
  development database still contains six synthetic university fixtures, not the 17,079 real
  institutions described in an earlier report from another environment.
- [x] Canonical identity currently lives in `universities.id`, `canonical_name`, `slug`,
  `country_code`, and JSONB `external_identifiers`. Exact matching uses configured identifier
  namespaces; same-country normalized-name and full website-host matches are suggestions only.
- [!] JSONB identifiers have no database-enforced unique `(namespace, value)` constraint. The
  in-memory resolver overwrites duplicate identifier keys while loading, accepts the first matching
  identifier on a candidate, and does not detect when multiple candidate identifiers point to
  different rows. This needs ambiguity detection before any cross-source linking.
- [!] ROR identifiers and IPEDS `UNITID` use separate namespaces; IPEDS HD does not supply a ROR
  or explicit ROR/IPEDS crosswalk. ROR/IPEDS rows therefore cannot link automatically through the
  current exact-ID resolver. Alias and location data are not part of identity lookup. `Campus` has
  no external identifier field, so parent/campus interpretation needs an explicit policy.
- [!] Weak identity suggestions are recorded in ingestion job item details, but the admin review
  queue is fact-oriented and no institution merge/approval operation exists. The source pipeline
  creates a separate candidate university for weak matches and does not attach facts to it in that
  batch; job details do not provide an identity merge action.
- [ ] Phase 2A implementation remains unstarted. Next: define source-scoped identifier records and
  uniqueness, detect conflicting/duplicate identifier claims, add an actionable identity review
  workflow, model parent/campus mappings, and test authoritative crosswalk linking before enabling
  any imports. Do not auto-merge from name, alias, host, or location alone.

Git review and commit remain manual; no Git command or commit was made.

### Phase 2 identity implementation and bounded source verification (2026-10-20)

This entry supersedes the earlier “Phase 2A implementation remains unstarted” handoff above.
The schema and application changes below are implemented and verified against the isolated
`db-test` database only. The development database has not been migrated, and the new reviewer
workflow is not deployed to the development API until its additive schema migration is approved.

- [x] Added source-attributed institution identifier claims, namespace/scope-aware lookup,
  database uniqueness for accepted authoritative claims, legacy JSONB backfill with duplicate
  claims retained as `conflicted`, and explicit outcomes for ambiguous/conflicting candidate IDs.
  Weak name/domain suggestions now enter an identity-review queue without creating a canonical
  institution.
- [x] Added institution identity review and append-only review-event tables, reviewer-protected
  approve/reject/defer API operations, immutable audit-event trigger, and a small admin review
  screen. Approval associates candidate identifiers with an existing non-demo university; it
  does not merge or delete university rows.
- [x] Added source-specific program identifiers and removed title/slug uniqueness as a program
  identity rule. WebPageAdapter can produce configured program candidates and program-scoped
  facts without attaching those facts to the institution. The configured page extractor remains
  a generic parser and no official Master's source is currently enabled.
- [x] Isolated migrations advanced from the previous schema to Alembic head
  `c7f1a906d2b3`; `MIGRATION_TARGET=test alembic check` reported no new upgrade operations.
  These migrations have not been applied to development.
- [x] Full guarded backend suite against `db-test`: **243 passed, 4 skipped**. All four skips are
  opt-in live-ingestion tests. A focused dry-run regression proves a dry run creates no durable
  job, source, candidate institution, fact, or evidence.
- [x] Rebuilt only `api-test` and `nginx-test`. The isolated readiness GET returned ready with
  `schema: initialized`; the identity-review queue returned 401 when requested without
  authentication. API startup logs show Uvicorn startup and no migration or seed command.
- [x] Bounded ROR API retrieval returned HTTP 200 and parsed five education institution
  candidates. The pipeline dry run reported five seen, 20 candidate facts, zero rejected/reviewed,
  and unchanged database counts. The isolated database already held five ROR institutions and 20
  associated fact records before the subsequent import command; provenance points to the ROR API.
  Two permitted import reruns reported 20 unchanged facts each, zero created/updated/rejected/
  reviewed records, and unchanged institution, accepted ROR identifier, fact, and evidence counts.
  The existing test rows therefore demonstrate idempotent reprocessing; this run did not create
  additional institutions. No ROR data was imported into development.
- [x] ROR's current documentation confirms its API and registry data are public and the dataset is
  CC0 1.0; the adapter used one page, a one-request-per-second limit, and a five-record cap.
  [ROR data licence](https://ror.readme.io/docs/data-dump),
  [ROR API access and rate limits](https://ror.readme.io/docs/rest-api).
- [!] Program-source access remains unresolved. ETH Zurich's [general copyright terms](https://ethz.ch/staffnet/en/footer/disclaimer-copyright.html)
  prohibit storing its webpages on other servers without prior written consent, so ETH pages are
  not an acceptable ingestion source absent permission. [Studyinfo](https://opintopolku.fi/konfo/en/)
  is an official Finnish programme catalogue maintained with provider-managed information, but no
  reuse licence for automated copying/redistribution has been verified. The [Erasmus Mundus
  catalogue](https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en) is now
  reachable (HTTP 200), its robots.txt does not disallow the catalogue path, and the Commission's
  [general legal notice](https://commission.europa.eu/legal-notice_en) applies CC BY 4.0 to EU-owned
  content unless an exception is stated. The catalogue describes 218 joint Master's projects and
  links their official programme sites and project overviews, but it does not itself identify a
  canonical coordinator institution in the extracted listing, and partner content may carry
  separate rights. The current Program model has one required university FK; importing joint
  consortium programmes without first modeling their participating institutions would misstate
  the relationship. Keep this connector disabled pending rights/attribution review and a safe
  consortium representation. No programme records were imported.
- [!] Current development verification remains unchanged: `uni_shortlist`, role
  `uni_shortlist_app` for the API, PostgreSQL 16.15, 6 universities, 9 programs, 2 users, 0 student
  profiles, 0 recommendation runs, 0 saved programs, 76 fact records, 76 versions, 76 evidence
  rows, 0 ingestion jobs, 0 audit events, Alembic revision `b7f4d2c9a1e3`, named volume
  `uni-grp-prj_pgdata`. The running development API was checked read-only and reports
  `uni_shortlist|uni_shortlist_app`; readiness returned HTTP 200.
- [x] Fresh independent development backup
  `uni_shortlist_20261019T204551Z.dump` and metadata were written outside the repository and
  PostgreSQL volume. The existing recovery workflow restored it into the isolated tmpfs recovery
  service and matched revision `b7f4d2c9a1e3`, 6 universities, 9 programs, and 76 facts.
- [!] Development migration approval is still required before Phase 2 identity tables/API are
  available in development. The tested migration chain is `6af8c2d94b10` (backfilled identifier
  claims and merged prior Alembic heads), `93cb147f6e20` (identifier scopes and review/audit
  tables), `a3d2f7c98e41` (drops the unsafe program title/slug unique constraint and creates
  program identifiers), `b4e981c72a63` (conflict classification and scope-aware unique indexes),
  and `c7f1a906d2b3` (append-only review event trigger). Before execution, the owner must approve
  this exact chain after reviewing the backup and test rehearsal. No existing university,
  program, user, fact, evidence, or ownership row is intentionally deleted or rewritten; identifier
  JSONB values are copied into durable rows, and duplicate claims are marked conflicted instead
  of arbitrarily selected. The source/title uniqueness rule change is a behavior-affecting DDL
  operation and is included in the approval request.

**Current milestone state:** Phase 2A/2B code and isolated schema are implemented and tested, but
not deployed to development; source-backed institution reprocessing is verified in test, and the
development catalogue still contains only its six synthetic institutions. Master's programme
ingestion, official programme-source reuse approval, broader ROR/IPEDS crosswalk review, and the
development migration approval remain open. Do not call Phase 2, Phase 3, or the overall real-data
system complete.

### Phase 2/3 live development continuation (2026-10-20)

- [x] Created a fresh logical backup at
  `/home/parthrane/.local/share/uni-shortlist/backups/uni_shortlist_20261020T000932Z.dump`
  and restored it to the isolated tmpfs recovery service. The recovery copy started at
  `b7f4d2c9a1e3` and matched the backup's aggregate counts.
- [x] Rehearsed revisions `6af8c2d94b10`, `93cb147f6e20`, `a3d2f7c98e41`,
  `b4e981c72a63`, and `c7f1a906d2b3` on the restored copy. Alembic reached one head,
  `c7f1a906d2b3`; `alembic check` found no model drift. University, program, user,
  fact-record, version, and evidence ID-set checksums matched before and after rehearsal;
  no orphaned university/program/evidence references were found.
- [x] Applied the rehearsed five-revision chain to the authorized local development DB.
  Current revision is `c7f1a906d2b3`. Existing universities (6), programs (9), users (2),
  facts/versions/evidence (76 each) were unchanged by the migration. A Compose invocation
  unexpectedly recreated the PostgreSQL container while starting the one-off migration
  service; the named `uni-grp-prj_pgdata` volume remained attached and its identity stayed
  unchanged. Read-only checks after migration verified the original row-ID checksums.
- [x] Rebuilt only the development API and web services. API readiness returned HTTP 200;
  startup remains Uvicorn only. A live SQLAlchemy connection reports `uni_shortlist_app`
  with SUPERUSER, CREATEDB, CREATEROLE, REPLICATION and BYPASSRLS all false. The new
  identity tables have required runtime DML grants. Anonymous access to the identity-review
  API returns HTTP 401.
- [x] Added an exact-name ROR query option and imported one bounded ROR match for the
  University of Almería. ROR returned HTTP 200; dry run and persistence each saw one
  candidate with four source-backed facts and no validation or identity errors.
- [x] Added the licensed UAL official Master's JSON adapter. The dataset catalogue declares
  CC BY and identifies the publisher and Master's JSON distribution; the source page says
  the dataset describes active study offerings. At retrieval, the API returned 64 rows.
  The initial single-institution pilot excludes inter-university and double-Master rows,
  leaving 35 candidates. The feed does not publish admission requirements, fees, duration
  or deadlines; those fields remain unknown. Attribution is Universidad de Almería and
  changes must be indicated.
- [x] UAL dry run returned one institution candidate, 35 programme candidates and one
  identity-review item, with no writes. The bounded persisted run created a source document,
  job and pending identity-review row only; it created no UAL institution or program rows.
  The job is `partial` because identity review is pending. Its source identity must be
  explicitly approved before a repeat run can attach those programs to a canonical university.
- [x] Independent final SQL checks report 12 universities (6 demo, 6 with accepted ROR
  identities), 9 programs (all existing demo programs), 2 users, 0 profiles, 0 recommendation
  runs, 0 saved programs, 100 facts, 100 versions, 100 evidence rows, 7 ingestion jobs
  (4 succeeded, 3 partial),
  0 audit events, 1 pending identity review, and zero checked orphan relationships. The
  existing program/user rows were preserved. No real Master's program has been persisted
  or exposed by the public catalogue yet.
- [x] Created a post-import backup at
  `/home/parthrane/.local/share/uni-shortlist/backups/uni_shortlist_20261020T002342Z.dump`
  and restored it to the isolated recovery service. Recovery verified revision
  `c7f1a906d2b3`, 12 universities, 9 programs, and 100 facts. This backup includes the
  bounded ROR records and the pending UAL review.
- [x] Final backup after the idempotency reruns:
  `/home/parthrane/.local/share/uni-shortlist/backups/uni_shortlist_20261020T002631Z.dump`.
  It was restored independently; recovery verified revision `c7f1a906d2b3`, 12 universities,
  9 programs, and 100 facts.
- [x] Corrected the ingestion CLI summary so any rejection or review-required record reports
  `partial`, matching the persisted job state. Full backend tests pass after this correction;
  the latest UAL rerun reports `partial`, one review item, and one unchanged source document.
- [x] Full backend suite on isolated PostgreSQL: 247 passed, 4 opt-in live-ingestion tests
  skipped. Frontend lint and typecheck passed; 21 frontend tests passed.
- [!] Remaining mandatory user review: inspect the pending UAL publisher identity against
  the linked UAL dataset and ROR evidence, then approve or reject it through the reviewer UI.
  Do not treat its 35 candidates as imported programs until that review and a safe subsequent
  persistence run complete. Program publication also remains subject to the project's
  approved review policy; no source record or candidate fact was automatically marked verified.
- [!] Phase 2 source expansion, ROR/IPEDS crosswalk review, consortium program modeling,
  additional country/program sources, program publication review, data-quality metrics,
  scheduled refresh recovery, and student-facing real-program flow remain incomplete.
  No live IPEDS bulk import or Erasmus import was performed. Keep the Erasmus connector
  disabled until third-party content rights and multi-institution representation are resolved.

**Current milestone state:** Phase 1 is preserved. The reviewed identity schema is deployed;
six real ROR institutions are present alongside six clearly marked demo institutions. One
official CC-BY programme feed is implemented and its 35 candidates are held for human
identity review. The public program catalogue still contains only the nine demo programs,
so Phase 2/3 and overall real-program completion remain incomplete.

### UAL identity approval and bounded Master's import (2026-10-20)

This checkpoint supersedes the earlier pending-identity and “no UAL program rows” snapshots
above. The historical entries describe the database before the authorized reviewer approved
the source-to-institution link.

- [x] Read-only development checks confirmed the UAL review for
  `ual:publisher:u04800001` is `approved`, resolved to University UUID
  `0c036720-deff-4111-98b6-637319eb8abb`, and has an `approve_link` event attributed to
  authenticated user `48a09873-d490-4d47-9027-4fd3abe92502` with `admin` and `reviewer`
  roles, timestamp, and reason. The canonical University of Almería row carries accepted
  ROR ID `003d3xx08`; no second Almería university exists. The UAL identifier claim row is
  attached to the same UUID but remains `pending_review` because it is a non-authoritative
  publisher namespace. Ingestion resolved the approved review link; it did not treat this
  publisher identifier as an authoritative ROR/IPEDS-style identifier.
- [x] Verified `ual_masters` is enabled with `public_dataset` policy, publisher
  Universidad de Almería, CC BY attribution/modification note and the datos.gob.es dataset
  listing. The stored official JSON source document returned HTTP 200 and is linked to the
  approved identity review and all imported program identifiers/evidence. Its candidate
  payload contains 35 program candidates.
- [x] Bounded dry run, using `python -m app.ingestion.cli run ual_masters --dry-run --limit 35`,
  fetched the official feed successfully; it saw one institution candidate and reported 70
  candidate fact creations in its counters, had zero rejects or review-required records,
  and rolled back without a durable job.
- [x] Created pre-import logical backup
  `/home/parthrane/.local/share/uni-shortlist/backups/uni_shortlist_20261020T101108Z.dump`
  with matching metadata before persistence.
- [x] Persisted the authorized bounded batch with
  `python -m app.ingestion.cli run ual_masters --limit 35` through the development API
  container's restricted `uni_shortlist_app` connection. The job succeeded: 1 source record
  seen, `records_created=70` (the pipeline's fact creation counter), 0 updated, 0 rejected,
  0 review-required. Independent SQL confirms 35 distinct UAL program rows/identifiers,
  all linked to the approved University UUID, with 70 candidate fact records, one version
  per fact and one evidence row per version, all pointing to the fetched source document.
  No UAL program is published and no fact is verified.
- [x] Repeated the identical bounded command. The job succeeded with 70 unchanged, 0 created,
  0 updated, 0 rejected and 0 review-required. Independent SQL finds zero duplicate UAL
  identifier groups; university, program, fact, version and evidence counts did not increase
  on rerun.
- [x] The same-title feed rows are distinct: plan `7070` is `Presencial`; plan `7151` is
  `Híbrida`. Both have separate accepted source program identifiers and remain separate
  candidate programs.
- [x] Final read-only development SQL: PostgreSQL 16.15, revision `c7f1a906d2b3`, 12
  universities (6 synthetic, 6 ROR-linked), 44 programs (9 published demo, 35 unpublished
  UAL candidates), 2 users, 0 student profiles, 170 fact records/versions/evidence, 9 total
  ingestion jobs, and 1 audit event. There is still only one University of Almería row.
  The `uni-grp-prj_pgdata` named volume remains present. The application SQL session is
  `uni_shortlist_app`, with all five elevated role attributes false.
- [x] Restarted only the API container after its TCP port accepted connections but HTTP
  health requests timed out. Readiness then returned `ready`, database `ok`, schema
  `initialized`. The public catalogue returned 9 entries; no UAL candidate was exposed.
- [x] Targeted isolated PostgreSQL tests:
  `pytest tests/test_ual_adapter.py tests/test_ingestion.py tests/test_programs.py
  tests/test_admin.py tests/test_db_safety.py -ra` — **136 passed**. The test runner used
  `TEST_DATABASE_URL` and `UNISHORTLIST_TEST_MODE=1` against `db-test`.
- [~] Next: an authorized admin/reviewer must inspect the 35 UAL program candidates and
  evidence in Program Publication Review, then decide which program identities satisfy the
  publication policy. No program was published by this import. The UAL feed provides no
  tuition, admission requirements, fees, duration or deadlines; these remain unavailable and
  must not be marked verified or inferred.

The import changed no university, user, demo-program, or existing fact/evidence rows. It
added 35 programs, 70 program fact records, 70 versions, 70 evidence rows, and two successful
UAL ingestion jobs (one initial persistence and one idempotency rerun). Phase 3/real catalogue
publication is still incomplete until the authorized publication decisions and student-facing
checks are performed.

### Real-data catalogue rendering compatibility (2026-10-20)

- [x] Corrected the frontend catalogue DTOs to match nullable API values: `field`, university
  `city`, duration bounds/value, `language`, `study_mode`, and detail `campus` may be null.
  The compare response also permits null duration and language.
- [x] Updated `ProgramCard.vue` and `ProgramDetailView.vue` to render explicit unavailable or
  unspecified labels for missing field, city, duration, language, intake, and deadline data.
  Tuition continues through the existing `MoneyCell`, which displays unknown amounts as
  “Not available”. Missing requirements and fees retain their existing unknown-state copy.
  Save, compare, program navigation, and cost-estimation controls are preserved.
- [x] Updated the comparison language row to show “Not specified” when the source does not
  supply a language.
- [x] Discovery consumes the existing `{ items, page, page_size, total_items, total_pages }`
  contract. URL query changes now synchronize back/forward filter state; a page change uses
  the filter watcher as its single request path. Search page reset occurs after its debounce,
  and the existing `useAsync` generation check keeps late responses from replacing newer data.
  Loading, error, empty, and populated states remain distinct.
- [x] Added rendered-component regression coverage using representative UAL-shaped records
  with null optional fields, plus discovery pagination/filter/sort/query changes, stale
  response ordering, loading/error/empty states, card actions, and detail unknown states.
  Publication review reason validation is also covered by backend and frontend tests; no
  existing publication decisions were changed.
- [x] Frontend production build (including `vue-tsc` typecheck), ESLint, and Vitest passed:
  **33 tests passed**. The isolated PostgreSQL backend suite passed: **251 passed, 4 skipped**
  (the existing opt-in live-ingestion tests).
- [x] Recreated only the development API, Vite, and NGINX containers with the verified
  application builds. Headless Chrome loaded `/discover` through NGINX and rendered 11 cards,
  including the two published UAL Master's programs; nullable-field fallbacks were visible
  and no browser runtime errors were observed. Both UAL program detail GETs returned HTTP 200.
- [x] Read-only before/after checks show the development database remained at PostgreSQL
  16.15, revision `c7f1a906d2b3`, 12 universities, 44 programs (11 published, 33 candidates),
  2 users, 170 fact records/versions/evidence rows, 9 ingestion jobs, and 3 audit events.
  The application database session remains `uni_shortlist_app`; the named development volume
  remains `uni-grp-prj_pgdata`. All backend test writes were confined to `db-test`.
- [x] Existing design, component hierarchy, responsive layout, API paths, and save/compare/
  finance flows were preserved. Future source adapters must keep optional fields nullable and
  must not infer unsupported program facts to satisfy these display fields.
- [~] The browser smoke check was anonymous, so it did not submit an authenticated Save action.
  The Save control rendered and the component/service code was unchanged; saved-program API
  behavior was covered by the isolated backend suite, but signed-in browser save behavior was
  not re-exercised in this verification.

### Admin identity and program publication review (2026-10-20)

- [x] Confirmed the existing dashboard links to `/admin/identity-reviews` and the frontend
  route plus API endpoints are role-gated. The identity review payload now exposes source
  publisher/use policy, source retrieval metadata and excerpt, suggested university URL and
  accepted identifiers, pending program-candidate summaries, current state, reason and
  append-only review history.
- [x] Added `/admin/program-publication` and reviewer/admin API queue/actions for publishing
  and unpublishing programs. Publication requires Master's classification, an official
  program URL, a non-demo institution, an accepted program source identifier, a successful
  source document from an allowed automated-use policy, and an accepted or explicitly
  reviewer-approved institution/source link. It records actor, reason, request ID and
  before/after state in the append-only audit log. Unpublishing hides the program and keeps
  the identity/evidence rows. Program publication does not change fact verification states.
- [x] Isolated admin tests verified source and identity prerequisites, public visibility
  changes, reason requirement, duplicate-action conflict, reviewer authorization, and audit
  events. Full isolated backend suite: 249 passed, 4 opt-in live-ingestion tests skipped.
- [x] After the final source/document consistency guard and pending-review payload assertions,
  the focused isolated identity/publication suite passed: 6 passed, 17 deselected. This
  targeted rerun follows the full-suite run above.
- [x] Frontend lint, typecheck/production build and unit suite passed (21 tests). Updated
  development API/web/NGINX containers only; readiness is HTTP 200, anonymous identity and
  publication-review requests return HTTP 401, and `/admin/program-publication` is served by
  the SPA. Startup logs show Uvicorn startup only.
- [x] Read-only development verification after deployment: PostgreSQL 16.15, schema
  `c7f1a906d2b3`, 12 universities (6 demo), 9 programs (9 currently published demo
  programs), 2 users, 100 facts/versions/evidence, 7 ingestion jobs and 1 pending identity
  review. Development volume remains `uni-grp-prj_pgdata`. Automated writes were confined
  to isolated `db-test`; the development database was not changed.
- [x] Historical state at this review snapshot: the UAL publisher identity was still pending
  and no UAL programs had been persisted. This snapshot was superseded by the subsequent
  reviewer approval and bounded import recorded in “UAL identity approval and bounded
  Master's import” above. Program publication remains pending individual review.

### Phase 2–4 source expansion and bounded ingestion checkpoint (2026-10-20)

- [x] Corrected ROR API query construction to combine the documented education-type query
  with country filters, validate country codes, and report the 10,000-result REST API ceiling.
  The official ROR documentation recommends its data dump for complete coverage; a dump
  importer remains future work. Bounded live ROR dry run returned five candidates without
  validation errors. ROR remains identity-only; no program claims are inferred from it.
- [x] Added the bounded `fr_monmaster` adapter for the official French MESRE Mon Master 2025
  catalogue. The dataset methodology identifies Licence Ouverte/Open Licence. Requests select
  catalogue identity and offer fields only, not applicant/outcome statistics. Safe evidence
  excerpts retain the selected fields; the full retrieved document remains hashed/source-linked.
  The dataset is a historical 2025 snapshot and does not provide individual official program
  URLs. Imports therefore remain unpublished candidates. Source:
  `https://data.enseignementsup-recherche.gouv.fr/explore/dataset/fr-esr-mon_master/`.
- [x] Persisted an explicit limit of 35 French catalogue offers through the shared source
  pipeline. This added two French UAI reporting-unit institutions and 35 candidate programs
  with 35 distinct accepted IFC source identifiers. The import added 210 fact records total:
  208 program-level facts and two source-backed institution-name facts. Each is versioned and
  evidenced by the retrieved official source document. No program was published and no fact
  was verified.
  The identical bounded rerun reported 35 programs unchanged, two institutions unchanged, zero
  new programs or facts, zero rejected candidates, and zero duplicate accepted source IDs.
- [x] Ran the official public-domain IPEDS HD2023 directory with `--limit 5` first as a dry
  run, then as a bounded import using the restricted `uni_shortlist_app` runtime connection.
  The dry run validated five institution candidates and 35 candidate facts. Persistence added
  five US reporting-unit institutions with five unique accepted UNITIDs and 35 evidence-backed
  fact records. The identical rerun reported five institutions and 35 facts unchanged, with no
  new identifiers or facts. No student or program record was changed. IPEDS source:
  `https://nces.ed.gov/ipeds/datacenter/data/HD2023.zip` (IPEDS/NCES public-domain data).
- [x] Expanded the ingestion CLI's “real institution” verification predicate to count UAI
  reporting-unit identities as well as ROR and IPEDS identities. It now reports registered
  connectors separately from source rows actually persisted in the database. A regression
  test checks that a UAI-identified source institution is counted while demo fixtures are not.
- [x] Independent read-only SQL after ingestion: PostgreSQL 16.15, Alembic revision
  `c7f1a906d2b3`; 19 universities (6 demo and 13 source-identified: 6 ROR, 5 IPEDS UNITID,
  2 UAI); 79 programs (11 published, 68 candidates); 2 users; 1 profile; 415 fact records,
  415 versions and 415 evidence rows; 13 ingestion jobs; 3 audit events. There are no orphaned
  program-to-university references and no duplicate accepted IPEDS UNITID claims. The five
  current IPEDS rows are in the US; the source-identified institutions span FR, ES, US, GR, BG,
  BI and GA (7 countries). French programs are in FR and UAL programs are in ES.
- [x] Program identity/provenance query confirms 35 UAL source IDs (2 published, 33 candidate)
  and 35 Mon Master IFC IDs (all candidate). Each French program points to the retrieved
  `fr_monmaster` source document; 208 program fact records have linked versions/evidence, and
  two additional facts describe the two UAI institution records. All 70 UAL program fact
  records have evidence. No duplicate accepted program identifier groups or orphan programs
  were found. The public API remains at 11 items; `country=FR` returns zero because all French
  candidate programs are unpublished. Unknown tuition, duration, deadlines, language and
  admissions data remain unknown.
- [x] Created backup
  `/home/parthrane/.local/share/uni-shortlist/backups/uni_shortlist_20261020T141152Z.dump`
  after the bounded IPEDS import. The existing recovery workflow restored it only into the
  isolated tmpfs recovery database and matched revision `c7f1a906d2b3`, 19 universities,
  79 programs and 415 facts. The development volume `uni-grp-prj_pgdata` remains present.
- [x] Verification: complete isolated backend suite **261 passed, 4 skipped** (four opt-in
  live-ingestion tests). Focused ingestion/identity tests **88 passed**, and a final focused
  adapter/CLI rerun **13 passed**. Frontend ESLint and typecheck passed; Vitest **33 passed**;
  production build passed. Development readiness returned `ready`; public program API returned
  11 published records and the French-country query returned zero. No test writes targeted
  development.
- [x] Completed the previously missing authenticated browser Save/Compare journey through
  headless Chrome at `nginx-test` (`127.0.0.1:8081`) backed by `api-test` and the isolated
  `db-test`. A temporary test student registered through the UI, saw nine seeded test catalogue
  cards, saved one, revisited the Saved page, compared two programs, and saved the comparison;
  all six assertions passed. These browser records were test fixtures in `db-test`, not real
  development programs. The prior anonymous browser-only note above is superseded for this
  workflow.
- [x] Corrected ingestion status reporting so rejected/reviewed items, source warnings, and
  rolled-back batches produce `partial` rather than `succeeded`. Added a regression that
  forces one batch to roll back, verifies the subsequent batch commits, and checks the durable
  job records the failure. The isolated full suite after this change passed **261 tests**, with
  the same four opt-in live-source skips. Rebuilt and recreated only the development API;
  readiness returned `ready`, its active SQL role is `uni_shortlist_app` with all elevated
  attributes false, and startup logs show Uvicorn only. Public catalogue remains at 11.
- [x] IPEDS job rows independently agree with persisted entities: first run recorded 5 seen/5
  created, rerun 5 seen/5 unchanged; each job checkpoint separately records 35 facts created
  or unchanged. This per-entity and per-fact breakdown is the basis for source reconciliation.
- [~] The first Mon Master persistence job predates the entity-counter correction: its stored
  top-level counters show 2 institution candidates seen and 210 fact records created. SQL and
  its source evidence reconcile this as 2 institutions, 35 programs and 210 total facts (208
  program plus 2 institution facts). The following run records the 37 unchanged entities; the
  historical row was preserved rather than rewritten. Overall historical job-stat consistency
  remains partial until legacy counter semantics are clearly surfaced in the job UI/API.
- [~] ROR retrieval is still bounded by the official API's 10,000-result query ceiling; a
  validated dump ingestion path and broad country-partition execution remain. IPEDS HD coverage
  is only the verified first five bounded rows; IPEDS IC was not imported. No authoritative
  ROR/IPEDS crosswalk was established, so those namespaces remain separate and no cross-source
  auto-link is performed. No live identity merge was made.
- [~] Program coverage now has two official catalogue sources across Spain and France, but the
  French dataset is a historical 2025 snapshot and has no individual program URLs. The UAL
  source excludes joint/double degrees; the French source notes that a shared INM may be
  co-accredited across establishments. The current program relationship model does not record
  consortium membership, so no coordinating institution or joint award is inferred. Source
  adaptation for additional current official program sources and joint-program modeling remain.
- [!] The Mon Master 35 imported programs cannot meet the current publication gate without
  individual official program URLs or other suitable source evidence. Keep all 35 unpublished
  pending an authorized review policy/source that supports those identities. Do not infer
  admission, fee or deadline facts from this catalogue. The 33 UAL candidates also remain
  pending individual program publication review; the two already approved UAL programs remain
  published.
- [!] A read-only grouping of Mon Master `master_mention_identifier` facts found mention ID
  `0900827Z` on nine imported offer rows associated with both Université Paris Cité and
  Université Sorbonne Paris Nord. The source methodology permits co-accreditation across
  establishments; the current one-university program relationship cannot establish whether
  these are a shared award or separate offers. All remain unpublished, and no consortium or
  coordinator relationship has been inferred. Resolve this through source-specific evidence
  and the future multi-institution review/model before publishing or merging any of these rows.

**Phase 2–4 checkpoint:** bounded ROR, IPEDS HD, UAL and Mon Master source paths are now
demonstrated, and the live database contains institution and program candidates with evidence.
Phase 2 remains partial because comprehensive ROR coverage and an authoritative ROR/IPEDS
crosswalk are absent. Phase 3 remains partial because most real programs are unpublished and
the French candidates lack individual source URLs and detailed admission/finance facts. Phase 4
remains partial because the French snapshot is historical, additional current official program
sources and consortium representation are not yet established. Do not report these phases as
fully complete.

### Phase 2–4 evidence quality and review context follow-up (2026-10-20)

- [x] The source review confirmed that UAL's catalogue response does not provide individual
  program landing-page URLs. Updated the adapter so future UAL candidates do not receive the
  generic `https://www.ual.es/estudios` catalogue URL as if it were a course page. It retains the
  original title as a source-backed candidate fact with its row locator. Existing persisted
  UAL rows were not rewritten: read-only SQL still finds that generic URL on all 35 rows. The
  program evidence service classifies a real program URL as verified only when the exact URL
  has a verified fact version and fetched, policy-eligible supporting evidence; otherwise the
  UI/API marks it unresolved. The two previously published UAL rows remain published by their
  existing decisions, but their detail response now omits the generic URL and reports
  `unverified`; any publication-state change requires separate reviewer authorization. No
  program was published or unpublished by this work.
- [x] Expanded fact-review and publication-review responses with readable values, institution
  identity/site context, source claims, document retrieval details, excerpts/locators, fact
  applicability and explicit missing-information warnings. The frontend exposes those fields
  while keeping raw fact JSON available for technical inspection. Program detail distinguishes
  a verified course page from an unverified candidate URL. No reviewer decision or historical
  audit record was changed.
- [x] Source-independent discipline-name matching now maps only a unique exact normalized
  label. Ambiguous labels remain unmapped instead of attaching to an arbitrary field. The
  batch pipeline refreshes the controlled-field index after staging taxonomy rows so same-batch
  unique labels can be resolved. Candidate fact intake year and term are validated against the
  existing schema enum/range and propagated to fact versions.
- [x] Read-only development SQL after the work: revision `c7f1a906d2b3`; 19 universities,
  79 programs (11 published, 68 candidates), 2 users, 1 profile, 415 facts, 415 versions,
  415 evidence records, 13 ingestion jobs and 3 audit events. The API readiness GET returned
  `ready`; its public catalogue GET returned 11 items. No development import, migration,
  publication action or database write was executed.
- [x] Current evidence coverage query: 11/19 university rows have a stored website URL (six
  demo rows have none; a stored URL is not by itself independent domain verification). The 35
  Mon Master programs have no stored program URL and no field mapping; their 35 accepted source
  identifiers reference one retrieved source document and 210 evidence rows. The 35 UAL
  programs have one repeated generic catalogue URL, no field mapping, and 70 evidence rows tied
  to their catalogue retrieval. No fact version currently carries applicable intake year or
  term. Across the 70 source-identified UAL/Mon Master programs, SQL found zero relational
  program-fee rows, zero admission-requirement rows and zero intake rows. These are coverage
  gaps, not proof that the programs are invalid.
- [x] Duplicate-title investigation: the two UAL rows titled “Máster en Investigación en
  Medicina y Ciencias de la Salud” have distinct source plan identifiers `ual:master:plan:7070`
  and `ual:master:plan:7151`. They remain separate offerings; title similarity alone was not
  used to merge them.
- [x] Verification: full isolated backend suite **264 passed, 4 skipped** (opt-in live-source
  tests); frontend typecheck, lint and production build passed; frontend Vitest **33 passed**.
  The test safety command verified the isolated test PostgreSQL identity before the backend
  suite. Rebuilt/recreated only the development `api`, `web` and `nginx` application containers;
  PostgreSQL and its volume were not recreated. Read-only runtime checks returned API readiness
  200, 11 public programs, an existing published UAL detail with `official_program_url: null`
  and status `unverified`, and HTTP 200 for both the Vite and NGINX pages. The rebuilt API
  command is Uvicorn only. Headless Chrome rendered 11 cards on `/discover`, including real
  University of Almería programs. An authenticated browser journey for the updated reviewer
  evidence panels was not run.
- [~] Source access and identity foundations remain in place, but official university sites
  have not been independently resolved for every institution. Current source data still lacks
  individual UAL/Mon Master course pages, intake applicability, and real-program field mappings.
  No new source retrieval or ingestion was performed in this follow-up.
- [~] IDM-11 remains partial: current rows carry institution, campus and reporting-unit
  scopes, and programs can point to a campus, but the schema does not represent multi-university
  awards, co-accreditation, explicit parent systems, or distinct awarding/delivery institutions.
  Adding those relations requires an additive migration rehearsal and separate approval before
  deployment to development.
- [~] ING-08 remains partial for legacy job-counter interpretation. SRC-03 remains partial
  because dataset row evidence exists but individual official course-page coverage is absent.
  FACT-01/03 have improved structured source facts and validated applicability support, but
  source coverage still lacks structured detailed program facts and all stored intake-year/term
  values. FACT-04/05 remain data-limited: current real sources do not supply supported tuition,
  fee or prerequisite detail in the imported records. EXT-09 remains partial: ambiguous exact
  field labels are now safely left unmapped, but no controlled field mapping is currently
  present for the imported real programs.
- [!] Phase 2, Phase 3 and Phase 4 remain **PARTIAL**. Do not treat the evidence-panel
  improvements or passing tests as completion of cross-source parent/consortium modeling,
  official individual program URL verification, structured tuition/requirement coverage,
  source expansion, or published real-program coverage. No development migration is proposed
  by this follow-up; any future relation-schema migration must be rehearsed in isolation and
  approved before development deployment.

### University-level review queue implementation checkpoint (2026-10-20)

- [x] Root cause confirmed: the existing Institution Identity Review is intentionally limited
  to ambiguous/conflicting source-to-canonical links. It is not a review queue for every newly
  discovered canonical institution. The Fact Review Queue contained 350 fact rows across 19
  universities; all 415 fact keys/applicability groups were unique, so repeated university
  labels were multiple distinct facts rather than duplicate fact identities. SQL found no
  same-normalized-name/country university duplicate groups. Five unrelated Alabama institutions
  share accepted `ipeds_fips=1`; FIPS is auxiliary and is not used as a canonical match.
- [x] Added a grouped, one-entry-per-canonical-university admin review API and frontend route.
  It presents identifiers and their source documents, website evidence state, grouped facts and
  provenance, associated program identities/page evidence, same-title warnings, campus rows,
  and append-only review history. Decisions are authenticated reviewer actions with a required
  substantive reason; existing source identity review and fact review remain separate.
- [x] Added migration `e5a17c9b4d20` after `c7f1a906d2b3`. It creates institution review and
  append-only event tables, inserts pending review state for non-demo universities, and
  reclassifies accepted auxiliary identifier claims as `pending_review` without deleting
  claims or changing university/program/fact identities. On the current development snapshot,
  that would insert 13 pending rows and reclassify 16 claims (5 each for IPEDS EIN/FIPS/OPEID,
  and 1 ROR FundRef claim). Existing publication status rows are not changed by the migration.
- [x] Added one shared student-visibility condition: published and active programs must belong
  to an explicitly approved institution, except explicitly tagged demo fixtures. Catalogue,
  detail, recommendations, eligibility, saved-program, compare and finance access use this
  condition; publication eligibility also requires institution review. No human identity,
  fact or publication decision was made by this implementation.
- [x] Program-scoped rows from the public `/outcomes` route and previously saved programs also
  use publication and institution approval filtering. Focused isolated regression tests confirm
  pending-institution outcomes and newly unpublished saved programs are omitted; aggregate
  outcomes without a program ID remain available.
- [x] Migration completed from `c7f1a906d2b3` to `e5a17c9b4d20` both on isolated `db-test`
  and, more importantly, on a fresh restored development snapshot in the isolated tmpfs recovery
  PostgreSQL. The recovery check found 13 pending institution reviews, 16 auxiliary claim
  reclassifications, zero review events, and zero orphan review references. Sorted UUID digests
  and counts for universities, programs, users, facts, versions and evidence matched the source
  snapshot exactly. The recovery container was stopped after verification.
- [x] Regression verification: the final complete backend suite passed **269 tests**, with **4
  opt-in live ingestion tests skipped**. Targeted institution-review/catalogue tests and the
  new idempotent pending-review ingestion test also passed. Frontend TypeScript check, ESLint,
  Vitest (**33 passed**) and production build passed in a disposable container. No development
  writes, migrations, publication actions or imports were run.
- [x] Development preservation query (read-only, after test work): database `uni_shortlist`,
  role `uni_shortlist_app`, PostgreSQL 16.15, revision `c7f1a906d2b3`; 19 universities, 79
  programs (11 published, 68 candidates), 2 users, 1 profile, 415 facts, 415 versions, 415
  evidence rows, 13 jobs and 3 audit events. The development API readiness GET returned 200
  and its current published catalogue returned 11. Existing runtime role remains non-superuser
  and migration-owner default grants cover future tables/sequences.
- [x] A fresh mode-600 logical backup was created with `scripts/db-backup.sh` and successfully
  restored through `scripts/db-restore-recovery.sh`; the recovered revision/count metadata
  matched before the migration rehearsal. The development database and named volume were not
  written by backup, restore, migration rehearsal or test commands.
- [x] Rebuilt only isolated `api-test` and `nginx-test`; read-only HTTP through `127.0.0.1:8081`
  returned readiness 200 with `database_target=isolated_test`, catalogue 200 with nine demo
  programs in the test database, and the admin SPA route returned the application shell. The
  admin institution-review API returned 401 when unauthenticated. No admin decision was sent.
- [~] At the time of this 2026-10-20 checkpoint, development deployment still awaited owner
  approval. That state was superseded by the authorized deployment and verification recorded
  below; no institution or program decisions were made during deployment.
- [~] Source-quality gaps remain: only 11/19 development universities have a stored website
  URL (a stored URL is not independently verified); the UAL/Mon Master programs lack verified
  individual official university course pages and structured requirements/fee/intake coverage.
  Same-title records remain separate when source keys differ. No program was merged or
  published by this work. IDM-11, program URL/evidence coverage, detailed fact coverage, source
  expansion and overall Phase 2–4 status remain partial.
- [~] An authenticated browser session against the new institution-review page was not
  available in this verification. API authorization and decision behavior were covered by the
  isolated backend tests; the frontend typecheck, lint, unit tests and build pass.


### Approved institution review migration deployment (2026-10-21)

- [x] Read-only preflight matched the approved target exactly: `uni_shortlist` on PostgreSQL
  16.15, current revision `c7f1a906d2b3`, runtime API session `uni_shortlist_app`, and the
  existing `uni-grp-prj_pgdata` volume. Baseline counts were 19 universities, 79 programs,
  2 users, 1 student profile, 415 fact records, 415 versions, 415 evidence rows, 13 ingestion
  jobs and 3 audit events. The app role has none of SUPERUSER, CREATEDB, CREATEROLE,
  REPLICATION or BYPASSRLS.
- [x] The mode-600 backup `/tmp/unishortlist-phase2-4-backup/uni_shortlist_20261020T181239Z.dump`
  and metadata were present. Metadata identified database `uni_shortlist`, migration role
  `uni_shortlist`, revision `c7f1a906d2b3`, and matching baseline counts; this backup had
  already completed the isolated recovery verification recorded above.
- [x] Applied additive revision `e5a17c9b4d20` with the guarded `db-admin` workflow. An initial
  command against the stale existing one-off image exited without advancing the revision; this
  was detected before relying on it. Rebuilding only the one-off `db-admin` image exposed the
  current migration source, and the guarded command reported the actual upgrade from
  `c7f1a906d2b3` to `e5a17c9b4d20`. No database service or volume was recreated.
- [x] Independent read-only post-migration verification returned revision `e5a17c9b4d20` and
  unchanged counts plus sorted-ID digests: universities 19 (`dc5be34af3315cc73a0e9833c28976a8`),
  programs 79 (`00ca92a9a305ebc5992a8ffb02950df7`), users 2
  (`3987532b3f9a4469291d2a6a571b2e91`), fact records 415
  (`1fcd799ee3c34fd9338cf40a768fb26a`), fact versions 415
  (`adfbbef6063620050e0d0beda8b8b76b`), and evidence 415
  (`f7588cfbe11b940d737a5f25aef599f7`). Profiles remained 1; jobs 13; audit events 3.
  No institution-review orphan references were found.
- [x] Exactly 13 distinct non-demo institutions have pending review rows; no review was approved.
  The 16 auxiliary claims remain present and are now `pending_review` (5 EIN, 5 FIPS,
  5 OPEID, 1 ROR FundRef). The existing source-identity review remains approved with its
  existing single audit event. No institution-review events were created.
- [x] Stored program publication states remain 68 candidates and 11 published. The student
  visibility gate exposes the 9 published demo programs while the 2 already-published UAL
  programs remain hidden because University of Almería institution review is pending. No
  program was approved, published, unpublished, or otherwise changed.
- [x] Rebuilt and recreated only `api`, `web` and `nginx` (`docker compose build api web nginx`,
  then `docker compose up -d --no-deps api web nginx`). The DB container remained running with
  the same named volume. API startup logs show application startup and Uvicorn only. Readiness
  returned HTTP 200; all three development catalogue paths (8000, 8080, 5173) returned HTTP 200
  and `total_items=9`. Headless Chrome rendered nine cards at `/discover`.
- [x] The unauthenticated live institution-review API returned HTTP 401. A read-only call to the
  live review service returned 13 queue entries and grouped detail; the University of Almería
  detail includes 6 identifier claims, 4 fact groups with 4 evidence rows, 35 source-identified
  program candidates, zero verified individual program pages, 36 warnings, and no human
  institution-review event. Reviewer authorization and grouped evidence serialization passed
  in the isolated backend tests. An authenticated browser session on the live development UI
  remains unverified because no admin session/credential was available to this execution.
- [x] Isolated full backend pytest run: **269 passed, 4 skipped** (opt-in live-source ingestion,
  disabled by default). Frontend typecheck, ESLint, Vitest (**33 passed**) and production build
  all passed. No seed, ingestion, publication, or institution decision was run; development
  writes were limited to the approved additive migration.
- [~] Next manual review action: authenticate as an authorized reviewer, inspect the 13 pending
  institution records (including the grouped University of Almería evidence), and make any
  identity decisions through the review UI only. The two UAL programs remain unavailable to
  students until a separate authorized institution approval; program publication decisions
  remain unchanged. Do not treat missing individual course URLs as verified evidence.

### Phase-by-phase continuation checkpoint (2026-10-21)

- [x] Phase 1 recheck: development remains `uni_shortlist` / PostgreSQL 16.15 at
  `e5a17c9b4d20`; the active application SQL role is `uni_shortlist_app` with no elevated
  role attributes. Development and test PostgreSQL remain on separate networks and named
  volumes; both services report healthy. Read-only development counts still match the deployed
  checkpoint: 19 universities, 79 programs, 2 users, 415 facts, 415 versions, 415 evidence
  rows, 13 ingestion jobs, 3 audit events and 13 pending institution reviews.
- [x] Phase 2 identity resolution correction: weak name/country and website-domain lookup
  indexes now retain all matching canonical UUIDs. Colliding names/domains or contradictory
  weak hints return an ambiguous suggestion instead of selecting an arbitrary university.
  Authoritative identifiers remain the only automatic match mechanism; this does not approve
  or merge any institution.
- [x] Isolated regression verification: rebuilt the stale `test-runner` image (the first
  attempted test used an older baked application image and was discarded as invalid evidence),
  verified the live `db-test` identity, then ran `tests/test_ingestion.py`: **82 passed**.
  The dedicated identity-resolution subset also passed. No development data was written.
- [~] Phase 2 remains partial: no authoritative live ROR/IPEDS crosswalk was established;
  explicit parent/campus/reporting-unit relationships are not modeled as a reviewed relational
  graph. These require a new additive schema design, isolated restore rehearsal, and separate
  approval before any development migration. Existing institution reviews remain pending;
  no reviewer decisions were made.
- [~] Phases 3–4 remain partial: UAL and Mon Master candidates retain source identifiers and
  row/document evidence, but current sources do not establish individual university course
  pages, full admission/tuition/deadline facts, or current multi-source coverage. Mon Master is
  a historical 2025 snapshot. ROR API retrieval is limited to 10,000 results; official ROR
  documentation directs complete-registry consumers to the CC0 Zenodo dump, and no dump
  ingestion path has yet been implemented or run. No new real-source ingestion or publication
  was performed in this checkpoint.
- [~] Phase 5–7 have not yet received a fresh full-system run in this continuation. Previous
  frontend, browser and end-to-end results remain documented in their dated checkpoints and are
  not represented as newly executed results here.

### Phase 3–7 verification follow-up (2026-10-21)

- [x] Full isolated backend regression after the resolver correction: **271 passed, 4 skipped**
  in 51.07 seconds. The four skipped cases are opt-in live ingestion tests; they were not run.
  The test runner first verified the isolated database marker. The isolated test database was
  not confused with or pointed at development.
- [x] Frontend verification: `vue-tsc` typecheck, ESLint, Vitest (**33 passed in 5 files**) and
  production Vite build all passed. No frontend source changes were needed in this checkpoint.
- [x] Runtime catalogue check: FastAPI `:8000`, NGINX `:8080`, and Vite `:5173` each returned
  HTTP 200 and the same nine public demo programs. A direct request for an already-published UAL
  program returned 404 while its institution remains pending; no program publication state was
  changed.
- [x] Headless Chrome loaded `/discover` from the live Vite service. The actual DOM contained
  nine `card stack-sm` program cards and the text “9 programs”; no browser stderr/runtime error
  was emitted. An initial selector-based count returned zero because it looked for an exact
  `<article>` markup pattern; inspecting the DOM showed the page rendered correctly. This was a
  verification selector issue, not an application regression.
- [x] Independent read-only SQL after testing: revision `e5a17c9b4d20`; universities 19,
  programs 79 (11 database-published, 68 candidates), users 2, profiles 1, facts/versions/
  evidence 415 each, jobs 13, audit events 3, pending institution reviews 13. There are zero
  orphan program-to-university references and zero duplicate accepted `(source_key,
  normalized_external_key)` program identities. Runtime role `uni_shortlist_app` remains free
  of SUPERUSER, CREATEDB, CREATEROLE, REPLICATION and BYPASSRLS. No development DML, import,
  migration, seed, or reviewer/publication action occurred.
- [~] Program identity investigation: the two UAL same-title programs use separate source
  plan codes `7070` and `7151`; they remain separate. SQL finds three Mon Master repeated-title
  groups among separate IFC offering keys. A shared `INM=0900827Z` appears across nine offers
  at two institutions; without a source-backed relation model, those remain separate candidates,
  not inferred consortium links or duplicates. No records were merged.
- [~] External read-only source research found a University-controlled UAL Master's URL directory
  and a UAL program page explicitly associated with plan 7070. The directory does not establish
  a plan-code mapping for 7151, so no URL was added or inferred. The UAL legal notice reserves
  intellectual-property rights in site content; automated page-content ingestion is not enabled
  by the CC-BY dataset policy alone. The individual URL remains a candidate for reviewer
  evidence, not a verified fact in PostgreSQL.
- [!] Phase 2 remains partial pending an additive, reviewed institution-relationship model for
  parent/campus/reporting-unit and multi-institution roles. Phase 3 remains partial: 35 UAL and
  35 historical Mon Master source identities exist, but no program has a currently verified
  individual university page in the stored evidence; the 35 UAL rows still have the old generic
  catalogue URL in the table, and Mon Master has no per-program URL. No structured source-backed
  fee/intake/admission coverage exists for these imported candidates. Phase 4 remains partial:
  only bounded ROR API ingestion is implemented; complete ROR dump support, verified crosswalks,
  and current independent official programme-source expansion remain outstanding.
- [~] Phase 5–7 checks in this continuation cover current catalogue visibility, readiness,
  frontend rendering, authorization-safe hidden detail, full isolated regression, and DB
  preservation. Authenticated reviewer/student end-to-end journeys were not rerun because no
  authenticated session was supplied to this execution; earlier dated journey evidence remains
  historical and is not represented as new evidence here.

### Phase-by-phase engineering continuation (2026-10-21)

- [x] Institution resolver safety: weak name/domain indexes now retain all canonical candidates;
  a name collision or contradictory weak hints return an ambiguous suggestion instead of picking
  an arbitrary university. Only authoritative identifiers remain eligible for automatic
  resolution. Regression tests cover both collision cases.
- [x] ROR relationship evidence: the ROR adapter now retains supported, well-formed relationship
  entries as a candidate fact with the source record locator. It does not create an institution
  link, infer a parent/campus relationship, or approve the candidate. A source-shaped regression
  test verifies this conservative behavior.
- [x] Final isolated backend regression after both changes: the guarded runner verified the
  isolated `db-test` identity, then pytest completed with **272 passed, 4 skipped** in 48.88s.
  The skips are the opt-in live ingestion tests; no external ingestion ran.
- [x] Read-only development recheck through the running API container: database `uni_shortlist`,
  role `uni_shortlist_app`, PostgreSQL 16.15, revision `e5a17c9b4d20`; 19 universities, 79
  programs (11 database-published / 68 candidates), 2 users, 1 profile, 415 fact records, 415
  versions, 415 evidence rows, 13 ingestion jobs, 3 audit events, and 13 pending institution
  reviews. There are no orphan program-to-university references. All five elevated PostgreSQL
  role flags are false. The SQL ran in an explicitly read-only transaction.
- [x] Development API GET checks: readiness returned HTTP 200 (`database=ok`, `schema=initialized`);
  the public catalogue returned HTTP 200 with 9 visible programs. No institution or program
  decision, import, seed, migration, or development DML was performed in this continuation.
- [~] Phase 2 remains partial: ROR-reported relationship evidence is now retained, but a durable
  reviewed parent/campus/reporting-unit/multi-institution relationship model and an authoritative
  ROR/IPEDS crosswalk are not established. The 13 institution reviews remain pending.
- [~] Phases 3–4 remain partial: no new program imports or publication decisions were made.
  Stored real programs still lack verified individual university course-page evidence and
  structured source-backed admission, tuition, deadline and intake coverage. A complete ROR dump
  ingestion path and verified independent current Master's source coverage remain outstanding.
  Phase 5–7 authenticated reviewer/student journeys were not freshly executed in this checkpoint.

### University programme coverage and review-action follow-up (2026-10-21)

- [x] Reproduced the review-action validation defect in isolated `db-test`: the backend used a
  narrow evidence/rationale vocabulary, while the Vue form only displayed generic request errors.
  The shared reason policy now accepts source-specific explanations such as “The official
  university website could not be verified.” and the form displays the backend's `reason` field
  error beside the input. Blank, generic and insufficient reasons remain rejected. Reject and
  request-evidence operations are separately covered; failed validation preserves review state.
- [x] Institution review detail now reports university type, recognition, readable location,
  publisher attribution for website/fact/program evidence, grouped program facts, source-row
  coverage, missing-program state, and explicit approval blockers. Approval is refused unless
  authoritative identity/name evidence, a verified website with evidence, and source-backed
  Master's offerings are available. This policy change is not deployed to development pending
  approval because it changes institution approval eligibility.
- [x] IPEDS root cause confirmed in `backend/app/ingestion/adapters/ipeds.py`: HD imports
  institutional directory metadata and graduate-offering flags; IC is institutional/financial
  data. Neither adapter emits named Master's programs. Read-only development counts show zero
  programs for Alabama A & M, Alabama State, and UAB; University of Almería has 35. Zero records
  therefore mean programme availability is not established, not that the institution offers no
  Master's courses.
- [~] Official AAMU graduate pages expose a structured program listing and per-program URLs
  ([graduate listing](https://www.aamu.edu/academics/graduate-studies/graduate-program-listing.html),
  [official JSON feed](https://www.aamu.edu/_resources/php/program-json-graduate.php?path=/academics/graduate-studies/)).
  The university's [Web Page Policy](https://www.aamu.edu/about/policies-procedures/_documents/5.3-web-page-policy.pdf)
  requires copyright compliance; no reuse permission for automated catalogue ingestion was
  established.
  No adapter was enabled, no AAMU program was persisted, and this source remains unimported pending
  a suitable reuse basis. Current coverage status in the application remains “availability not
  established” until permitted source evidence is durably recorded.
- [x] Verification: full guarded backend pytest **276 passed, 4 skipped** (opt-in live-source
  tests); frontend typecheck and ESLint passed; Vitest **36 passed**; production build passed.
  Headless Chrome on `nginx-test` logged in as a temporary isolated reviewer, rendered the actual
  institution detail and coverage blockers, submitted a needs-evidence decision with HTTP 200,
  and showed the refreshed review history. Independent `db-test` SQL found status `needs_evidence`
  with one attributable review event. No development decision was made.
- [x] Read-only development verification after implementation: `uni_shortlist`, runtime role
  `uni_shortlist_app`, revision `e5a17c9b4d20`; 19 universities, 79 programs (68 candidates / 11
  database-published), 2 users, 1 profile, 415 facts, 415 versions, 415 evidence rows, 13 jobs,
  3 audit events and 13 pending institution reviews. API readiness is HTTP 200; public catalogue
  returns 9 programs. No development migration, import, seed, publication or review decision was
  performed.
- [!] Deployment checkpoint: the reviewed API/frontend changes are tested in isolated services,
  but the development containers still run the prior image. Obtain explicit approval to deploy
  the new institution-approval eligibility policy, then recreate only API/frontend services and
  verify the pending queue and nine-program public catalogue. No schema migration is included.
- [~] Remaining data action: identify a permitted official named-program source for each
  institution-only directory record, especially AAMU; persist source-specific coverage states;
  then import bounded candidates and review them without automatic approval or publication.

### Final verification of institution programme-coverage policy (2026-10-21)

- [x] Tightened the review eligibility checks: program coverage now requires an accepted
  source-specific program identifier as well as a fetched program-row evidence record from a
  source whose recorded use policy permits this processing. Official-name and website evidence
  are likewise checked for source policy, excerpt and locator. An unaccepted program identity
  cannot make an institution approval-eligible.
- [x] Focused admin review tests passed: **32 passed**, covering approve eligibility, reject,
  request stronger evidence, defer, audit attribution, refresh, and authorization. The full
  guarded backend suite passed: **278 passed, 4 skipped**. The four skips are opt-in live-source
  ingestion checks. An initial
  full run exposed one existing finance-note assertion that passed when isolated and did not
  recur on the full rerun; final full-suite result is the successful rerun. Frontend typecheck,
  ESLint, Vitest (**36 passed**) and production build passed.
- [x] Final read-only development check: database `uni_shortlist`, role `uni_shortlist_app`,
  PostgreSQL 16.15, Alembic `e5a17c9b4d20`; 19 universities, 79 programs (68 candidate / 11
  database-published), 2 users, 1 profile, 415 fact records, 415 fact versions, 415 evidence
  rows, 13 jobs, 3 audit events and 13 pending institution reviews. Readiness returned HTTP 200;
  public catalogue returned 9 programs. No development DML, ingestion, migration, seed,
  publication action or review decision occurred.
- [x] Initial implementation was intentionally held from development until approval because the
  changed policy affects institution approval eligibility. The next dated checkpoint records the
  subsequent user approval, app-only deployment, and fresh isolated browser verification. No
  schema migration was included. Source coverage remains partial: IPEDS is institutional data,
  and AAMU's automated catalogue reuse permission was not established, so no AAMU programme was
  imported. Do not interpret an empty association as proof that a university offers no Master's
  programmes.

### Authorized local deployment and browser verification (2026-10-21)

- [x] Before deployment, the development target was read-only verified as `uni_shortlist`,
  runtime role `uni_shortlist_app`, PostgreSQL 16.15, Alembic `e5a17c9b4d20`. Counts matched
  the approved baseline: 19 universities, 79 programs (68 candidates / 11 database-published),
  2 users, 1 profile, 415 facts/versions/evidence each, 13 ingestion jobs, 3 audit events and
  13 pending institution reviews. All elevated runtime-role flags were false.
- [x] The previous backup was at revision `c7f1a906d2b3` and therefore not current. A fresh guarded
  backup was created at
  `/home/parthrane/.local/share/uni-shortlist/backups/uni_shortlist_20261021T030832Z.dump`;
  metadata records revision `e5a17c9b4d20` and the baseline counts. `pg_restore --list` parsed
  the custom-format archive successfully. SHA-256:
  `b04fb351a18146124d70dc786048a68c451ddb4a5d792145629bc4e189a6361b`.
- [x] The approved app-only deployment used
  `docker compose up -d --build --no-deps api web nginx`. Only `api`, `web` (Vite), and `nginx`
  were recreated. Development PostgreSQL remained running with the existing
  `uni-grp-prj_pgdata` volume; no migration, ingestion, seed, or decision action ran.
- [x] Post-deployment read-only SQL again returned the same revision, role, counts, publication
  states, and 13 pending institution reviews. Readiness returned HTTP 200. The public catalogue
  returned 9 programs through direct API, Vite and NGINX; the two database-published UAL programs
  remain hidden while their institution review is pending. No review or publication state changed.
- [x] Fresh headless Google Chrome session used a temporary reviewer and pending institution
  only in isolated `db-test` via `nginx-test`. The actual authenticated detail showed programme
  evidence blockers and disabled approval; weak reason `checking` left submission disabled; the
  reason requirement was visible. Submitting “The official university website could not be
  verified.” succeeded with HTTP 200 and the page refreshed to show `needs_evidence` and its
  review history. Independent read-only `db-test` SQL confirmed one attributable review event and
  one audit event with that reason. No development reviewer action occurred.
- [x] Final isolated regression results: backend **278 passed, 4 skipped**; focused institution
  review tests **32 passed**; frontend typecheck, lint, **36 tests passed**, and production build
  passed. Four backend skips are opt-in live-source ingestion tests.
- [x] Deployment checkpoint is complete. Remaining source-coverage limitation is unchanged:
  institutional sources such as IPEDS do not produce named Master's catalogues; AAMU's official
  feed provides program names/URLs, but automated reuse permission remains unestablished, so no
  AAMU program was imported. The deployed UI reports missing programme availability as unknown
  and blocks institution approval pending sufficient evidence.

### Connector evidence, release freshness and reliability (2026-10-21)

- [x] Source documents now distinguish content snapshots from retrieval attempts. The additive
  freshness migration adds publication period, academic period, last check and last content-change
  metadata, and an append-only retrieval log. Identical bytes reuse their existing snapshot and
  fact/evidence identities; a real unchanged fetch advances `last_checked_at` but leaves
  `last_content_changed_at` unchanged. Offline cache replays retain the original retrieval time
  and do not claim a new request. Generic UAL `/estudios` URLs classify as a general catalogue,
  never as a verified individual program page. Admin evidence payloads expose URL role, source
  publication period, check/change dates and verification state.
- [x] `f6b2a14d8c30` and `7a3d9f2c1e60` were rehearsed against a fresh restore of the verified
  2026-10-21 development backup in disposable tmpfs recovery PostgreSQL. The restored baseline
  was revision `e5a17c9b4d20`: 19 universities, 79 programs, 2 users, 415 facts, versions and
  evidence rows, and 3 audit events. Before/after ID-set hashes and counts matched for each of
  those tables. Migration ended at `7a3d9f2c1e60`; `alembic check` reported no model drift. The
  development database remains at `e5a17c9b4d20`; no development migration was run.
- [x] IPEDS files are now separately configurable and dictionary-validated. Official NCES
  checks found HD2025 and IC2025 absent (404), HD2024 available with its official dictionary,
  and IC2024 lacking the charge variables mapped by the existing IC adapter. The configured
  institution directory is HD2024; IC remains the 2023-24 historical snapshot. The official
  IC2023 dictionary exposed a prior field-name error (`RMBRDAMT`, not `RMBDAMT`), which is fixed.
  HD2024 now uses its dictionary's `CARNEGIESIZE` field for the 2025 size classification and
  preserves absent/unsupported fields as unknown. IPEDS remains institutional metadata only and
  is not treated as a named Master's catalogue.
- [x] A bounded official HD2024 replay in isolated `db-test` processed 5 institutions and 35
  facts; the identical rerun created 0 institutions/facts and reported 5 unchanged institutions
  and 35 unchanged facts. No development import occurred. IC remains manual-only and its mapped
  facts carry `2023-24` reporting applicability.
- [x] DUO/RIO's official CC BY 4.0 dataset/API returned 6,863 records, including 2,752 rows with
  `GRAAD=MASTER` during the 2026-10-21 probe. In the first 100-row page, 34 rows met the
  single-provider pilot requirements and 66 lacked required identity/title fields or were held
  for relationship review. Five genuine Saxion offerings were ingested into isolated `db-test`:
  5 distinct source UUIDs, 5 candidate programs, 43 program fact/evidence pairs, plus 2
  institution facts and one source document. The 5 programs remain unpublished and have no
  invented course URLs; the DUO provider `WEBSITE` is retained only as an unverified candidate
  fact. The identical replay created 0 programs/facts and reported 5 unchanged programs and 45
  unchanged facts. Eight incomplete source rows kept both jobs correctly `partial` with explicit
  skip warnings. No development import or review decision occurred.
- [x] Current jobs append a version-2 breakdown for institutions, programs, facts, documents,
  rejections, conflicts, review and skipped rows while preserving the historical aggregate
  `records_*` columns. Conflict counts are explicitly marked as a subset of needs-review counts.
  Old checkpoints are exposed as legacy aggregate/partial data; the API does not invent a
  conflict breakdown or rewrite historical jobs. The admin Jobs and Source Detail views label
  the aggregate entity counters and summarize current structured metrics.
- [~] Refresh work remains bounded and conservative. IPEDS, DUO/RIO and Mon Master require
  explicit limits and have no scheduled interval. Development `ENABLE_SCHEDULER=false`; this
  implementation did not queue refreshes or change registry schedules. Existing registry
  intervals for ROR, NCES CIP, UAL and College Scorecard still require explicit operational
  schedule approval before enabling the development scheduler. Per-source job health and
  document retrieval/change timestamps are available. HTTP request retries/backoff and isolated
  queue/worker failure plus operator retry behavior were exercised; no automatic scheduler was
  enabled in development.
- [x] Verification: full guarded backend suite **297 passed, 4 skipped** (the opt-in live-source
  cases); final focused ingestion/admin/source suite **134 passed** and final conflict/job-metric
  assertions **5 passed**. Frontend typecheck, ESLint and production build passed; Vitest **36
  passed**. The frontend checks ran in disposable images and did not recreate local services.
  Read-only local checks: database `uni_shortlist`, role `uni_shortlist`, revision
  `e5a17c9b4d20`; 19 universities, 79 programs, 2 users, 1 profile, 415 facts/versions/evidence,
  13 jobs, 3 audit events; all elevated runtime-role flags false. `APP_DATABASE_URL` resolves to
  host `db`, database `uni_shortlist`, role `uni_shortlist_app`; readiness HTTP 200; direct API,
  NGINX and Vite each report 9 public programs. The development volume remains
  `uni-grp-prj_pgdata`. No development rows, decisions, configuration, schema or volume were
  changed by this checkpoint.
- [!] Development deployment of freshness fields remains gated on explicit migration approval.
  The exact pending chain is `f6b2a14d8c30` (four source metadata columns: nullable period fields
  and non-null check/change timestamps backfilled from the existing retrieval timestamp; plus a
  new append-only `source_document_retrievals` table with indexes and a mutation-rejection trigger)
  followed by
  `7a3d9f2c1e60` (partial unique index for accepted `rio_provider_id` claims). Rehearsal passed
  on the restored isolated backup with record IDs preserved. No migration, ingestion, source
  decision, publication action, scheduler activation or API/frontend recreation was performed
  against development.

### Discover runtime recovery and pre-migration compatibility (2026-10-21)

- [x] Reproduced the Discover failure before changing code. Readiness was HTTP 200, but
  `/api/v1/programs` returned HTTP 500 through FastAPI, NGINX and Vite. The API log identified
  `UndefinedColumn: source_documents.source_published_at`: the API model expected the pending
  freshness migration while the development schema was still at `e5a17c9b4d20`.
- [x] Kept the additive freshness fields deferred in ORM reads and made admin freshness reads
  check schema capabilities. On the pre-migration schema, source list/detail responses use only
  existing columns, mark freshness/retrieval metadata unavailable, and do not mislabel the
  historical `retrieved_at` value as a current check. On the migrated schema, the new fields are
  explicitly loaded. No migration was run to work around the runtime mismatch.
- [x] Rebuilt/recreated only the FastAPI `api` service with `--no-deps`; PostgreSQL, its volume,
  NGINX and Vite were not recreated. The API runtime session reports database `uni_shortlist`
  and role `uni_shortlist_app`.
- [x] Direct FastAPI, NGINX and Vite checks now return readiness 200, catalogue 200 with 9 items,
  country metadata 200, and a public program detail/evidence 200. Read-only source list/detail
  service checks against the pre-migration development schema returned successfully and marked
  freshness metadata unavailable.
- [x] Headless Chrome rendered 9 default Discover cards, 2 cards for `q=computer`, and 2 cards
  for the combined `country=DE` and `degree_level=masters` filter; the searched/sorted query also
  rendered 2 cards. No visible error state or captured browser exception/console error occurred.
  API pagination returned 3/3/3 items across pages 1–3 (total 9); the UI pagination control is
  correctly absent because its page size is 12. An authenticated isolated admin browser account reached Ingestion Jobs and its
  jobs API returned 200. The isolated student workflow rendered a program detail and completed
  Save and Compare. These browser mutations were confined to `db-test`.
- [x] Current read-only development counts remain revision `e5a17c9b4d20`, 19 universities,
  79 programs, 2 users, 415 facts/versions/evidence, 13 jobs and 3 audit events. Program states
  remain 9 published demo, 68 real candidates and 2 real published rows. All 13 institution
  reviews are pending; therefore the 2 real published rows remain hidden and public catalogue
  total is 9. Runtime role flags remain non-elevated and the PostgreSQL volume remains
  `uni-grp-prj_pgdata`. The existing latest backup passed `pg_restore --list`.
- [x] Backend isolated suite after the compatibility change and deferred-column regression test:
  **298 passed, 4 skipped**. Frontend
  typecheck, lint, production build and Vitest: **36 passed**. Isolated migration consistency
  check: `No new upgrade operations detected`.
- [!] Full freshness persistence and retrieval history are not active in development until the
  already rehearsed `f6b2a14d8c30` → `7a3d9f2c1e60` migration chain is explicitly approved.
  Development scheduler remains disabled. No development imports or review/publication changes
  were made. The admin browser verification covered Jobs; it did not make institution/program
  review decisions or claim those workflows were browser-verified in this checkpoint.

### Approved freshness migration and catalogue-reset preflight (2026-10-21)

- [x] The approved additive migration chain `f6b2a14d8c30` → `7a3d9f2c1e60` was deployed to the
  local development database with the guarded `db-admin` workflow. The first one-off used a
  stale image that did not contain the new revision; the image was rebuilt without recreating
  PostgreSQL, then the guarded upgrade succeeded. `alembic check` reports no model drift.
- [x] Before deployment, database identity was `uni_shortlist`, connected admin role
  `uni_shortlist`; revision `e5a17c9b4d20`; 19 universities, 79 programs, 2 users, 1 profile,
  415 fact records/versions/evidence each, 13 ingestion jobs, 3 audit events, and 13 pending
  institution reviews. The running API uses `uni_shortlist_app`; all elevated role flags are
  false. Development and existing test volumes remain `uni-grp-prj_pgdata` and
  `uni-grp-prj_test_pgdata`.
- [x] Fresh pre-migration backup:
  `/home/parthrane/.local/share/uni-shortlist/backups/uni_shortlist_20261021T130311Z.dump`
  (mode 600, SHA-256 `161d720f7750f4236c21ca1b26554d8efa9a4ba7873e94cdaa044193445262d6`), restored
  in isolated tmpfs recovery at `e5a17c9b4d20` with the recorded counts. A second pre-reset
  checkpoint backup after migration is
  `/home/parthrane/.local/share/uni-shortlist/backups/uni_shortlist_20261021T130912Z.dump`
  (mode 600, SHA-256 `1fe68de77a018e9eaaba357d726614da703cdb1176ad368870fe718b56a487e6`); it restored
  independently at `7a3d9f2c1e60` with 19 universities, 79 programs, 2 users, 415 facts,
  versions and evidence, 13 jobs and 3 audit events. Both custom archives passed `pg_restore
  --list`.
- [x] Isolated migration rehearsal and post-deployment read-only checks confirm unchanged ID-set
  hashes for universities, programs, users, profiles, facts, versions, evidence, institution
  reviews, identity reviews/events, audit events, jobs and source documents. The freshness columns
  exist; old document retrieval/check timestamps were backfilled; the append-only retrieval table
  exists; the accepted RIO-provider partial unique index exists; no unvalidated foreign keys or
  conflicting accepted RIO claims were found. The runtime API can read the new retrieval table.
- [x] Reset dependency scan found no saved programs, comparisons, recommendation runs/items, cost
  scenarios/items, loan/ROI scenarios or requirement evaluations. It found 3 program-specific
  scholarship links and 2 program outcome-evidence rows. The 415 facts are 61 university, 324
  program, 2 outcome, 27 city-reference and 1 scholarship fact; the last 28 and their versions and
  evidence are outside the proposed catalogue deletion scope. Reference data, the one scholarship,
  one funding opportunity, 2 users, 1 student profile, roles and settings are retained.
- [!] The catalogue reset was **not executed**. The exact bounded deletion transaction was stopped
  by automatic safety review because removing the 13 institution review rows without an explicit
  archival mechanism would discard review provenance. The database also contains approved UAL
  source-identity review `086e6d63-81da-460b-9896-2e940049309f` with immutable event
  `eefba4cc-346c-4fdb-9c06-66353d492ce9`; deleting its university would set its live
  `resolved_university_id` to NULL. Three audit events (including two program-publication events)
  were identified and remain intact. No table rows were deleted or approval/publication states
  changed. The full verified pre-reset backup retains the original associations, but the reset
  cannot proceed until the user selects an explicit archival treatment for the 13 pending review
  rows and the approved UAL identity history (for example, an additive archive design, or explicit
  authorization to treat the verified backup as the archive while retaining immutable event rows).
- [x] After migration, development remains at 19 universities and 79 programs; readiness is HTTP
  200. Direct API, NGINX and Vite each return 9 legitimately public programs (the active catalogue
  is not empty because the reset is blocked). Full backend suite on a separate isolated volume
  `uni-shortlist-reset-verify_test_pgdata`: **298 passed, 4 skipped**. Frontend scripts in a
  one-off container built from current source: typecheck passed, ESLint passed, Vitest **36 passed**,
  production build passed. Local host dependencies were absent; no package manifest or lockfile
  was changed. Existing `db-test` and its volume were not targeted.
- [~] Next safe action: decide the archival treatment for the pending institution-review rows and
  the approved UAL identity association. After that decision, rerun the reset preflight against the
  current `7a3d9f2c1e60` baseline, take a fresh verified backup, execute only the approved bounded
  transaction, then rebuild API/Vite/NGINX without recreating PostgreSQL and verify an empty public
  catalogue and empty pending-review queues. Do not ingest, seed, approve, publish or enable
  automatic refresh during reset verification.

### Master's evidence implementation and approved archived reset (2026-10-21)

This section supersedes the preceding reset preflight and historical counts.
Detailed architecture, source limitations, phase outcomes and manual commit groups
are in [MASTERS_IMPLEMENTATION_REPORT.md](MASTERS_IMPLEMENTATION_REPORT.md).
The [changed-file inventory](MASTERS_CHANGED_FILES.md) contains exact source paths.

- [x] Independently checked development at `7a3d9f2c1e60`, 19 universities,
  79 programs, 415 facts/versions/evidence, 2 users, 1 profile, 13 jobs and 3 audits.
  Took a complete private backup outside the PostgreSQL volume, restored it on
  separate marked recovery instances, and compared all application table contents.
  The original catalogue remains independently recoverable.
- [x] Implemented immutable catalogue archives and retained detached historical
  reviews. After explicit recovery-only authorization, rehearsed migration
  `85b2e4a6c910`, exact archive/reset, injected-failure rollback, protected hashes,
  original UAL source-review associations, immutable events and idempotent replay.
  Schema check reports no model drift. See [the operator runbook](CATALOGUE_ARCHIVE_RESET_RUNBOOK.md).
- [x] After separate explicit approval of the exact development operation, deployed
  compatible application services, applied **only** `85b2e4a6c910` from the existing
  `7a3d9f2c1e60`, verified the exact plan again and committed reset operation
  `a0839f88-9fd0-4a57-9499-d86f6d4540b7`. Result: **0 active universities,
  0 active programs, 1,479 independently interpretable archived rows**.
- [x] All 1,479 archive payload hashes verified after reset. Both users, roles,
  the profile, all three audits, source/job history, the live immutable UAL event
  and 13 archived institution reviews survive. Thirty reference facts and their
  versions/evidence remain. Correction to the earlier note: the two outcome rows
  have no university/program association and are retained with their two facts;
  only 385 catalogue facts were deleted. Independently compared 34 protected whole
  tables and five reference row sets. Zero unvalidated foreign keys and zero
  unarchived null-university reviews.
- [x] Master's-first readiness now derives coherent program/source/institution/title
  evidence and exact website review. No-program institutions remain in discovery;
  failed, disputed, unrelated, expired and historical program evidence cannot make
  them ready. Existing institution/fact/program decisions are reused, not replaced.
  Admin screens show grouped university identity, website, catalogue, genuine named
  offerings, qualification/pathway/stage, applicability, gaps, links and history.
- [x] Individual university pages and government program records have separate
  evidence checks. General catalogues, APIs, datasets, resolvers and candidates
  never become verified course pages by setting a flag. Exact URL evidence, title,
  institution domain and source identity are required as appropriate. The old
  catalogue's 70 real records had **zero verified individual course URLs** and no
  structured tuition/admission/intake coverage. That limitation was preserved,
  not filled with invented facts. No development data was reimported after reset.
- [x] Corrected source-specific title/field/mode mappings, canonical source identity
  ownership across IPEDS HD/IC, missing-value handling, programme identity context,
  queued worker sessions, committed metrics, retry options/history, conflict replay
  and content reversion handling. Source identifiers preserve distinct same-title
  offerings. Unsupported joint/partner structures are held for evidence.
- [x] Explicit human fact review projects supported structured fields into existing
  relations without publishing. Real eligibility uses reviewed requirements;
  optional criteria and stored OR groups are handled correctly. Costs preserve
  unknown amounts/duration/category/period and conflicts; quality badges follow
  current fact evidence. Student visibility checks remain enforced across features.
- [x] Final full isolated backend suite: **327 passed, 7 skipped**, 76.60 seconds.
  Frontend typecheck, ESLint, production build passed; Vitest **36 passed**.
  Latest combined live suite: **6 passed, 1 transient NCES DNS failure** after
  bounded retries; standalone NCES directory + successful repeated-import rerun:
  **2 passed**. All seven live cases passed across recorded runs, not a single
  all-green combined final run. ROR, UAL, Mon Master and DUO official bounded
  retrievals and source-specific idempotency were exercised on the isolated DB.
- [x] Authenticated isolated Chrome journeys passed identity linking, university
  needs-evidence and approval, website fact review, publication blocking, source
  registry, jobs, audits, Discover/detail, Save, Compare, profile/eligibility,
  shortlisting/recommendations and finance. Student review API access returns 403.
  Approving the isolated institution left its real candidates hidden and did not
  change any publication decision. Completed journeys had no JavaScript exceptions.
- [x] Actual development API :8000, NGINX :8080 and Vite :5173 return readiness 200,
  catalogue 200 with **0 programs**, and all 13 country references. Archived former
  program detail returns 404. Chrome renders the actual empty Discover state without
  errors. Runtime role remains `uni_shortlist_app`, with all elevated flags false.
  Original development volume `uni-grp-prj_pgdata` remains intact; no volume deleted.
- [~] Data coverage remains source constrained: UAL does not supply individual
  course URLs or admissions/cost facts; Mon Master is historical 2025; DUO omits
  verified course links and unsupported joint rows are held. Studyinfo data reuse,
  CRICOS access/licence and a permitted RUCT/QEDU machine interface were not
  established, so no new unlicensed connector or scraping was enabled.
- [~] Development scheduler remains disabled. Per-source approval/reference/bounded
  schedule metadata is required in addition to a global flag; explicit-limit
  sources remain manual. No operational schedule approval was requested or assumed.
  There is no remaining approval pending for the completed archive/reset.
- [x] No Git command, automatic development fact/institution approval, publication,
  seeding or ingestion was performed. The platform workflow is implemented and
  demonstrated; a newly populated, current, reviewed international catalogue is
  not claimed by this empty-catalogue reset checkpoint.

### UAL official programme pages and backend regression (2026-10-22)

#### Confirmed defects and preserved safeguards

- [x] Rechecked actual development: university
  `08a617bb-ffe6-40b3-aadb-aa71d34d9918`, the five supplied plan identities,
  approved active source identity review `3ea508eb-7229-4bdf-88b0-f1dc0716620a`,
  historic archived identity review separately retained, and succeeded baseline job
  `bf3fdf79-ce73-4679-a55e-287afc03728a`. All five programme URLs are still null
  and publication states candidate in development. This task did not modify them.
- [x] The adapter emitted no individual-page evidence. Reusing a second ordinary
  programme batch would move its `ProgramIdentifier.source_document_id` from the
  catalogue to the webpage, breaking coherent title/identity document readiness.
  Added a small in-memory supplementary-document field and reused the existing
  pipeline, `store_document`, `record_facts`, evidence queues and transaction.
  Primary catalogue identity bindings and existing programme IDs survive.
- [x] The official `/estudios/masteres` index was incorrectly classified as a
  possible course page. It and the English index now remain general catalogues.
- [x] URL fact projection previously checked syntax/domain but not supporting
  retrieval evidence. Explicit reviewer verification now uses the same supporting
  document/title/link checks as publication; UAL also requires its exact accepted
  plan identity, page plan binding and observed title. Candidate facts can be shown
  in grouped admin review without populating the relational URL before review.
- [x] Pending `ual_dataset_publisher=u04800001` identifier claims alongside an
  approved source identity review are intentional. No identity claim or decision
  was rewritten. Archived reviews cannot substitute for an active approved link.
  Source identity, institution approval, fact verification and publication remain
  separate decisions. A fresh isolated replay without an approved source link
  correctly required identity review; that was not an idempotency defect.

#### Discovery, access and source evidence

- [x] A bounded live robots check allowed the catalogue and presentation pages.
  The official catalogue actually publishes
  `/estudios/masteres/presentacion/{{t.cod_plan}}`. The adapter resolves only
  observed literal links or this publisher-provided plan template; it does not
  guess URLs from names or maintain a fabricated per-program mapping.
- [x] Maximum five individual programme pages per run, one catalogue and one robots
  check per origin, with the existing 0.5 request/second limit, timeout and retry
  budget. Redirects are checked before following, at most four requests per URL;
  unrelated domains, other plans, generic pages, unexpected query parameters,
  unsuccessful retrievals, non-HTML/oversized responses and mismatched title/plan
  content cannot become page evidence. Robots errors/redirects fail closed;
  explicit robots 404 retains the existing no-robots-file policy.
- [x] All five actual pages (7101, 7133, 7112, 7138, 7150) returned accepted
  candidate evidence in the isolated live run. Literal static metadata inside
  UAL's script append and literal `var parameters = ['plan']` establish observed
  title/plan evidence without executing scripts. Spanish accent/plural/explicit
  ELE variants are handled; bilingual pages must actually supply matching title
  evidence. Translations are not invented.
- [x] The actual HTML bytes determine source-document hashes; metadata, retrieval
  status, actual title/plan excerpts, locators and document links persist through
  the existing provenance model. One `official_program_page_discovery` fact per
  programme points to the catalogue document, and one `official_program_page_url`
  candidate fact points to its actual retrieved webpage. Shared catalogue
  retrieval is recorded once per batch, rather than once for each programme.
- [x] No ECTS, duration, tuition, admissions or dates are extracted from unresolved
  templates such as `{{pre.presentacion[0].n_creditos}}`. Those fields remain unknown.
  The dataset's CC BY declaration is not asserted as a licence for the entire
  university website; supplementary pages are bounded reference evidence.

#### Verification and actual outcomes

| Check | Result |
| --- | --- |
| Unmodified isolated backend baseline | 327 passed, 7 opt-in live cases skipped; 77.98 seconds |
| Targeted UAL/readiness/projection/URL tests | 75 passed; 17.77 seconds |
| Complete final backend suite | **372 passed, 7 skipped**; 75.94 seconds |
| Existing frontend suite | **36 passed**; typecheck and ESLint also passed; frontend unchanged |
| Schema | Existing chain initialized on a new marked isolated database; isolated and development `alembic check`: no model drift; no new migration |
| Live dry run on isolated DB | Succeeded as `dry_run`, no job ID, 7 documents and 30 candidate facts validated, no warnings/errors; transaction rolled back |
| Bounded live import with existing isolated approved-link fixture | 5 programme candidates, 7 documents, 30 candidate facts; no approval/publication action |
| Live repeated import | Job `745a4093-39ac-4034-b637-ec453cc384f7`, succeeded: university unchanged 1, programmes unchanged 5, facts unchanged 30, documents unchanged 7; created/updated/review/conflicts/errors all 0 |
| Original catalogue idempotency | Existing 20 facts remain unchanged; enrichment adds only 5 discovery + 5 URL facts. Deterministic tests also replay the original 20-fact case without duplicates |
| API compatibility | Authenticated grouped admin evidence and fact projection passed; anonymous/student approval attempts denied 401/403; candidate programmes remain 404/absent from public catalogue |
| Development preservation | All **50 application-table** fingerprints and **both archive-table** fingerprints identical before/after; original five programme IDs and bindings, 1,479 archives, 2 users, profile, 4 audits and reviews intact |
| Running development | API and NGINX readiness 200, public Discover total 0; scheduler false; no service rebuilt/redeployed |

The first targeted run found five failures caused by a wrong import in the new
test assertion (`persist.normalize_url`); corrected the test to import the existing
normalizer directly. The final targeted and complete runs pass. A first live replay
on a fresh unapproved isolated institution correctly returned a review-required
partial result; the subsequent approved-fixture replay above passed without
changing any approval. No production safeguard was relaxed to make it succeed.

#### Files changed in this task

| File | Reason |
| --- | --- |
| `backend/app/ingestion/adapters/ual.py` | Source-backed bounded link discovery, access checks, literal title/plan validation and supplementary candidate evidence |
| `backend/app/ingestion/adapters/webpage.py` | Reuse robots checks with redirect control and fail-closed status handling |
| `backend/app/ingestion/http.py` | Optional per-request redirect control using the existing retry/rate-limit client |
| `backend/app/ingestion/normalize.py` | Conservative title-word normalization without invented translations |
| `backend/app/ingestion/types.py` | In-memory `ProgramDocument` evidence container on existing candidate programmes |
| `backend/app/ingestion/pipeline.py` | Persist supplementary documents/facts without replacing primary identity bindings or double-counting shared retrievals |
| `backend/app/ingestion/registry.py` | Accurate UAL access bounds and webpage-versus-dataset reuse notes |
| `backend/app/services/program_evidence.py` | Shared URL evidence qualification, UAL identity/title binding and unverified candidate visibility in admin |
| `backend/app/services/fact_projection.py` | Require supporting evidence before explicit URL verification/projection |
| `backend/app/services/source_urls.py` | Correctly classify both UAL Master’s catalogue indexes |
| `backend/tests/test_ual_adapter.py` | Keep the existing adapter fixture deterministic with supplementary access checks |
| `backend/tests/test_ual_program_pages.py` | 45 new deterministic page, failure, identity, persistence, history, API and publication regressions |
| `docs/UNIVERSITY_SHORTLISTING_PROJECT_STATUS.md` | Current verified baseline, implementation, checks and limitations |

#### Exact commands and manual checks

The private `/tmp/ual-pages-test.env` contains random test-only credentials; the
small `/tmp/ual-pages-test.yml` selects the existing local API image for test
services. All commands ran from the repository root, without rebuilding images:

```bash
# Full suite.
docker compose --env-file /tmp/ual-pages-test.env -p uni-shortlist-ual-pages \
  -f docker-compose.test.yml -f /tmp/ual-pages-test.yml --profile test \
  run --rm -v "$PWD/backend/app:/app/app:ro" test-runner \
  python -m pytest -o addopts='' -q

# Targeted suite (same isolated compose setup).
docker compose --env-file /tmp/ual-pages-test.env -p uni-shortlist-ual-pages \
  -f docker-compose.test.yml -f /tmp/ual-pages-test.yml --profile test \
  run --rm -v "$PWD/backend/app:/app/app:ro" test-runner \
  python -m pytest -o addopts='' -q tests/test_ual_program_pages.py \
  tests/test_ual_adapter.py tests/test_masters_readiness.py \
  tests/test_reviewed_facts.py tests/test_source_urls.py

docker compose run --rm --no-deps web \
  sh -c 'npm run test && npm run typecheck && npm run lint'

# Read-only model/schema comparison; no upgrade was run on development.
docker compose --profile db-admin run --rm --no-deps \
  -e MIGRATION_TARGET=development -v "$PWD/backend/app:/app/app:ro" \
  db-admin alembic check

# Smallest manual validation of CURRENT SOURCE against development: dry run only.
# The source mount matters: the running API image was deliberately not rebuilt.
docker compose run --rm --no-deps -v "$PWD/backend/app:/app/app:ro" api \
  python -m app.ingestion.cli run ual_masters --dry-run --limit 5
```

Live isolated validation added `/tmp/ual-pages-live.yml`, which connects only the
test runner to an egress network; the test DB remains on its internal network.
The dry run used the same compose test runner with
`python -m app.ingestion.cli run ual_masters --dry-run --limit 5`.

- After loading the updated backend and explicitly choosing a bounded persistent
  import, admin `/admin/institution-reviews/08a617bb-ffe6-40b3-aadb-aa71d34d9918`
  should show candidate links and programme facts with separate catalogue/page
  documents. Open the URL fact and inspect its actual title, plan binding and
  retrieval evidence. Only an explicit reviewer action should populate the
  relational URL and mark that fact verified.
- Institution approval and programme publication must still be separate; public
  `/api/v1/programs` must remain at 0 while these programmes are candidates.
- [~] Development has not been enriched/redeployed in this task. The completed code
  and isolated validations do not claim that the five new URL facts already exist
  in development. English-only pages without matching source title evidence,
  unsupported future HTML formats and remaining academic facts require further
  evidence/review. No scheduling, mass ingestion, Git command or destructive
  development operation was performed.

### 2026-10-22 — UAL institution approval evidence investigation

This supersedes earlier development snapshots for the institution evidence state.
Development was inspected using explicit PostgreSQL READ ONLY transactions. No
identity decision, fact verification, institution approval, publication, ingestion,
archive operation, scheduling change or deployment was performed in development.

#### Actual active evidence and the three blockers

- University `08a617bb-ffe6-40b3-aadb-aa71d34d9918` remains Universidad de Almería,
  ES, stored website `https://www.ual.es`, institution review pending.
- Five candidate programmes have qualifying source-row evidence (5/5). Their five
  individual-page URL facts remain candidates: zero reviewed programme pages.
  Programme evidence does not satisfy institution identity/name/website checks.
- Exactly one active institution identifier claim exists:
  `ual_dataset_publisher=u04800001`, scope institution, pending_review, claim
  `2e8da624-4e4f-4cbc-9446-d9db0e1394b8`. It is a source publisher identifier,
  not an authoritative institution namespace. It must not be promoted to ROR.
- Active UAL publisher identity review
  `3ea508eb-7229-4bdf-88b0-f1dc0716620a` is approved and resolves to the current
  university. It supports the programme source associations; it does not approve
  the institution or make the publisher ID authoritative.
- **Zero active university facts exist**, including neither `official_name` nor
  `official_website_url`. There are no candidate university name/website versions
  or supporting fact-evidence rows available for a reviewer to verify today.
  The stored name/URL and identity-review payload are not substitutes for these
  fact records under the existing institution readiness criteria.
- Consequently all three reported blockers are correct safeguards, not stale
  counters or failed programme-page ingestion.

#### ROR evidence and reconciliation boundary

- Active ROR source `a69e89e7-73eb-4d9e-8540-14d846191077` is enabled, configured
  as public_dataset, and uses the official CC0 ROR v2 API. No active ROR (or
  other authoritative) claim belongs to the current UAL university, and no
  pending ROR identity review currently exists.
- Retained ROR search document `85e58327-b0d4-4043-bf7d-dff7433ae5ee` was fetched
  with HTTP 200 on 2026-10-20 at
  `https://api.ror.org/v2/organizations?query=Universidad+de+Almer%C3%ADa`.
  SHA256 `6bba98418ebe588a20eb61595559cea72778464d165e29e50b3ac1aeb87bf82d`.
  Its retained JSON excerpt contains ROR `003d3xx08`, the ES and EN institution
  labels, country ES, domain `ual.es` and website `https://www.ual.es`.
  A retained document is evidence for reconciliation, not an active identity link.
- A separate bounded read-only lookup using RorAdapter and the existing Fetcher
  independently retrieved the official exact-name match with HTTP 200: ROR
  `003d3xx08`, display name `University of Almería`, Spanish label
  `Universidad de Almería`, country ES, normalized website `https://ual.es`.
  Returned external IDs also include GRID `grid.28020.38`, ISNI
  `0000 0001 0196 9356`, Wikidata `Q1218488`, and funder ID `501100021713`.
  Only the exact-name query was requested; no crawling or ingestion occurred.
  This new lookup was not persisted to development.
- Archived approved publisher review `086e6d63-81da-460b-9896-2e940049309f`
  remains detached from active universities, with archive operation
  `a0839f88-9fd0-4a57-9499-d86f6d4540b7`. Its old ROR association/reason was
  not used as current identity authorization. No archived record was restored.

#### Confirmed correction and existing review flow

- Fixed `_source_discovery` in `backend/app/services/admin.py`: previously it only
  considered accepted national-registry IDs, so an approved UAL publisher source
  link still displayed `identity_mapping_required`. It now calls the same
  source/institution link helper used by programme readiness and reports that
  source as targetable. It does not manufacture an authoritative matching ID or
  change the institution approval criteria. API field shapes are unchanged.
- The existing ROR flow needs two bounded operator imports with a human link
  review between them. A first import finds the current UAL record by weak domain
  evidence and queues a proposed ROR link; it does not create a second university
  or attach university facts. A reviewer/admin can then use Approve link at
  `/admin/identity-reviews`, selecting the current UAL UUID and recording a reason.
  This creates accepted authoritative identifier claims and immutable review/audit
  events. It does not replay fact extraction or approve the institution.
- A second import resolves through the reviewed link and persists candidate
  `official_name`, `aliases`, `official_website_url` and other ROR facts with their
  actual source document/evidence. The English ROR display name is evidence;
  the Spanish label remains an alias, and the canonical Spanish name is preserved.
- An evidenced candidate/unverified/verified `official_name` satisfies the name
  prerequisite. Individual name fact verification is available but is not itself
  mandatory for institution readiness. It is evidence_only: verifying it does
  not automatically rename the university.
- For the website, a reviewer/admin must inspect the current ROR website fact and
  use Verify fact version in `/admin/review/{fact_id}` (or the existing fact
  approve endpoint). This projects the normalized URL into the university only
  on explicit review. Readiness additionally requires verified fact/version,
  normalized equality to the stored URL and successful permitted supporting
  evidence with an excerpt and locator. HTTP 200 or the stored URL alone does
  not make the website verified.
- Even after all prerequisites pass, institution approval and individual programme
  publication are separate explicit decisions. They were not performed here.

#### Regression coverage and verification

- Added `backend/tests/test_ual_institution_review.py`: six deterministic tests
  covering the exact three blockers, reviewed publisher targeting, ROR weak-match
  reconciliation, accepted authoritative claims, provenance after the second
  import, explicit website review/projection, preserved canonical/program IDs,
  repeat-import idempotency, verified-fact preservation, student visibility and
  exclusion of archived approvals (pending/deferred/rejected active links).
- Reproduced the display defect before correction (one failing regression, five
  passing after fixture corrections). The isolated ROR reconciliation workflow
  already passed before the production fix; no parallel review system was needed.
- Baseline backend suite: **372 passed, 7 skipped**.
- Targeted suite after correction: **99 passed**.
- Full backend suite after correction: **378 passed, 7 skipped**.
- The seven opt-in live ingestion tests remain disabled. The bounded ROR lookup
  above is separate from the deterministic suite. No frontend source was changed.
- Read-only fingerprints of all **53 public development tables**, including both
  archive tables, match before/after investigation. Current counts remain one
  university, five programmes, 60 facts/versions/evidence (30 programme facts and
  30 reference facts), 1,479 archive rows, two users, one student profile, four
  audit events and two immutable identity-review events. Scheduler remains false.
  Database revision remains `85b2e4a6c910`; no migration is needed or applied.
- Actual running public `/api/v1/programs` still returns total_items 0. The backend
  correction is in workspace source and has not been rebuilt/deployed this turn.

Exact isolated commands (existing private test-only credentials/configuration):

```bash
docker compose --env-file /tmp/ual-pages-test.env -p uni-shortlist-ual-pages \
  -f docker-compose.test.yml -f /tmp/ual-pages-test.yml --profile test \
  run --rm -v "$PWD/backend/app:/app/app:ro" test-runner \
  python -m pytest -o addopts='' -q tests/test_ual_institution_review.py \
  tests/test_masters_readiness.py tests/test_admin.py \
  tests/test_ual_program_pages.py tests/test_catalogue_reset.py

docker compose --env-file /tmp/ual-pages-test.env -p uni-shortlist-ual-pages \
  -f docker-compose.test.yml -f /tmp/ual-pages-test.yml --profile test \
  run --rm -v "$PWD/backend/app:/app/app:ro" test-runner \
  python -m pytest -o addopts='' -q
```

Smallest next manual steps, only if separately authorized to write development:
run a bounded ROR import with `--query 'Universidad de Almería' --limit 1
--max-pages 1`; review its proposed identity link to the current UAL UUID; rerun
the same import; inspect and explicitly verify the website fact. Inspect both
English/Spanish labels and the ROR website assertion before deciding. Reopen the
institution review to confirm readiness, leaving institution approval/publication
for their separate human decisions. None of these development writes was executed.

### 2026-10-22 — Backend/data-quality audit before controlled expansion

This is the current verified pilot state; it supersedes the earlier institution
blocker snapshot. All development access in this task was read-only. No running
service was rebuilt, restarted or redeployed, and no development ingestion,
review decision, data enrichment, migration, reset or scheduling change occurred.

#### Findings and root causes

- [x] Verified active UAL university `08a617bb-ffe6-40b3-aadb-aa71d34d9918`, ROR
  `003d3xx08`, website `https://ual.es`, institution review approved and website
  evidence verified. All five `ual:master:plan:{code}` identities are accepted,
  and each of the five URL facts is verified against its own plan-specific page.
- [x] Only plan 7101 / programme `2fffabd2-fd80-43d9-a6a8-6d0e9d6702c8` is
  published. Plans 7112, 7133, 7138 and 7150 remain candidates. No duplicate
  programme identities or orphaned programme associations were observed.
- [x] The original `db.base.slugify` discarded accented letters before they could
  be normalized. Programme creation also reused the same slug for distinct
  same-title offerings. Programme routing/search uses UUIDs/canonical names;
  slugs are metadata, while city filters do use their persisted city slug.
- [x] Legacy `catalog._data_quality` evaluates tuition, requirements, presence of
  an intake row and presence of a programme outcome row. Its `unavailable` means
  no tuition/requirement coverage, not an unverified institution or programme.
  It neither checks duration/language nor proves that an intake has a deadline.
  Cards/detail displayed this broad label and raw machine warning codes.
- [x] `Program.description` already exists. Generic fact/version/evidence storage
  can represent a description, but no supported official-page extraction or
  reviewer-authored description projection existed. No new column is needed.

#### Unicode slugs and existing compatibility

- [x] New slugs use casefolding, NFKD decomposition, ASCII conversion and explicit
  mappings for common Latin letters without decomposition (including œ, æ, ø,
  ł, đ, ð and þ). German ß becomes ss, umlauts lose the diacritic, and composed
  and combining-accent forms produce the same slug. Punctuation is collapsed;
  truncation removes trailing separators. Empty/non-transliterable input uses
  `item`; uniqueness adds suffixes for distinct records.
- [x] New programme slugs are collision-checked per university, including pending
  rows. University slug collision checks retain their global uniqueness. These
  checks do not deduplicate legitimate same-title source offerings.
- [x] Reproduced another shared-slug defect before correction: distinct non-Latin
  city names both fell back to `item`, causing the second city to reuse the first
  record. City identity/cache lookup now uses country, exact name and region;
  new colliding city slugs receive bounded suffixes. Both cached and uncached
  ingestion paths are covered. Existing city UUIDs and filter slugs remain intact.
- [x] Repeat programme ingestion resolves the source identifier first and preserves
  its UUID and existing slug. Existing cities are reused by exact country/name/
  administrative-region when their legacy slug differs from the new normalization,
  preserving existing filter URLs. No stored or archived slug was rewritten.
- [x] The real published slug remains `m-ster-en-comunicaci-n-social`, and the
  stable `/programs/{UUID}` route still works. Canonical Unicode names, name-based
  search and existing filter semantics are unchanged; this is not a new
  transliteration or accent-insensitive search engine.

**Separate optional stored-slug repair plan — NOT executed:**

1. Obtain separate approval of a data-only change after checking external consumers
   of slug metadata. No repair is needed for the current UUID routes.
2. Save a pre-change backup and a reversible manifest containing only the current
   programme UUID, old slug `m-ster-en-comunicaci-n-social`, proposed slug
   `master-en-comunicacion-social`, university UUID and operation timestamp.
3. Rehearse on an isolated copy; require exactly one matching UUID/old-slug row and
   no intended collision in that university. Apply a single transactional update
   guarded by both UUID and the expected old value; abort on any mismatch.
4. Rollback would update that same UUID only when its slug still equals the proposed
   value, restoring the manifest's old value. Do not alter source identifiers,
   relationships, reviewer decisions or archived payloads. If slug-based URLs are
   introduced, preserve old URLs through an approved alias/redirect design first.

#### Additive source and academic quality semantics

- [x] `data_quality` and its warnings remain unchanged for existing clients.
  New `source_verification` and `academic_completeness` objects are available in
  catalogue summaries/detail, saved programmes and comparison responses.
- [x] Source metadata reports accepted source identity separately from official-page
  status (`verified`, `candidate`, `unavailable`, `demo_fixture`), plus verified
  URL, review time and source-document/retrieval metadata where established.
  It reuses `official_program_page` and its existing plan/title/document evidence
  checks. HTTP 200, an approved university, or a stored URL alone never verifies it.
- [x] Academic coverage reports each of seven categories independently: duration,
  teaching language, tuition, admission requirements, intake dates, application
  deadline and programme-specific outcomes. Missing values are unavailable;
  populated values without current matching reviewed fact/evidence are unverified.
  Wrong fact keys, mismatched values, failed/conflicting/unpermitted evidence and
  an intake row with no deadline do not count as verified coverage.
- [x] Academic status is limited when zero categories are verified, partial when
  some are verified and complete when all seven are verified. It describes those
  categories, not exhaustive academic information, current applicability, admission
  eligibility or promised future outcomes. Source verification does not increase
  academic coverage. No academic values were inferred or extracted in this task.
- [x] New page-evidence context is loaded in the existing catalogue batch query;
  accepted programme keys add one batch query. A regression confirms listing
  query counts do not grow per additional programme.
- [x] Existing page designs are retained. Discover cards, detail, saved programmes
  and comparison now label official-page verification and academic information
  separately. Detailed warnings are preserved and displayed as readable sentences,
  with readable fallback for unknown future warning codes.

#### Official description evidence and explicit human review

- [x] Inspected the supplied official 7101 page using bounded, robots-checked
  reference retrieval only. Its literal presentation paragraphs are inside
  `div.col-sm-12.col-md-8.col-lg-8`. Menus/notices and dynamic academic fields are
  outside that narrow extraction scope. No live ingestion was run.
- [x] On a future authorized import, the existing UAL supplementary-page fetch can
  emit a `program_description` candidate on the same HTML document as its URL
  evidence. It requires existing programme title/plan validation first and adds
  no HTTP requests. It retains at most 80 words/800 characters as a private
  reference excerpt; summary initially remains null. Hidden/navigation/notice
  content, empty text and unresolved templates are ignored.
- [x] HTML prose is not asserted to inherit the dataset's CC BY licence. The short
  passage is reference evidence for review, not public copied description text.
  Raw description drafts/passages are excluded from public evidence pagination.
- [x] The existing reviewer/admin fact approval accepts `description_summary` plus
  a reason for description facts. The reviewer writes 40–600 plain-text characters,
  at most 90 words, independently of the source wording. Long copied runs, HTML
  and templates are rejected. There is no automatic summarizer or automatic review.
- [x] Approval appends a `reviewer_summary` version, preserving the original
  candidate and copying its exact evidence/document links, then uses the normal
  fact review/audit path. Projection requires a permitted official-university HTML
  document, accepted programme identity, matching plan/title, exact page URL and
  supporting excerpt. Generic pages, wrong plans/titles and unrelated sources fail.
- [x] Existing authored descriptions are preserved; this action cannot overwrite
  any existing different description. Programme publication is independent. A
  reviewed summary is shown with attribution, source URL and retrieval/review time.
  Withdrawing it hides the public projection without deleting its stored text,
  versions, evidence or review history. Unchanged reimports retain the verified
  summary and create no duplicate fact versions.
- [~] Development description remains null and no description candidate was added
  there. A later separately authorized bounded import and an explicit human summary
  review are required to populate it. The narrow UAL selector intentionally fails
  closed if the official presentation layout changes. Replacing existing authored
  descriptions remains a separate editorial operation.

#### Executed verification and preservation

| Check | Actual result |
| --- | --- |
| Baseline complete backend | 378 passed, 7 skipped |
| Baseline frontend | 36 passed |
| Unicode/ingestion/catalogue phase | 125 passed |
| Quality/catalogue/page-evidence phase | 71 passed |
| Focused review/quality set | 141 passed |
| Final focused set including ingestion and city collision/cache regressions | **233 passed** |
| Complete backend before final city correction | 428 passed, 7 skipped |
| Complete backend after all backend changes | **430 passed, 7 skipped** |
| Frontend regression suite | **41 passed** |
| Frontend typecheck | Passed; corrected comparison status undefined/null mismatch |
| Frontend lint | Passed |
| Frontend production bundle | Passed; output only in disposable `/tmp/uni-quality-dist` |
| Isolated Alembic check with PostgreSQL READ ONLY | No new upgrade operations detected |
| Development revision | `85b2e4a6c910`, unchanged; no migration needed/applied |
| Development integrity | All **53 public table** counts/content hashes identical before/after |
| Running public catalogue | Exactly one published programme; original UUID/slug retained |

The seven live-ingestion tests remain opt-in and skipped. New tests use deterministic
HTTP fixtures. A first description test run found an invalid fixture enum; it was
corrected to the existing licensed_aggregator type, and all regressions were rerun.

A one-off read-only projection using current workspace backend code against the
actual pilot confirmed all pre-existing response fields are unchanged. It adds:
verified official-page status, accepted source identity, limited academic coverage
(0/7 categories verified), and null description/source. The other four programme
UUIDs still return 404 publicly. Running services continue serving the previous
image because no deployment was authorized.

Protected counts remain 1 university, 5 programmes, 65 facts/versions/evidence,
1,479 archive rows, 2 users, 1 student profile, 14 audit events, 3 institution identity
review events and 1 institution approval event. All original reviewer IDs/timestamps,
source documents, relationships and publication decisions remain unchanged.

#### Exact verification commands

Existing private `/tmp/ual-pages-test.env` and image-only `/tmp/ual-pages-test.yml`
select the marked isolated PostgreSQL instance and existing local image. No image
build or development deployment is performed by these commands.

```bash
# Baseline and complete backend suite; executed before and after backend changes.
docker compose --env-file /tmp/ual-pages-test.env -p uni-shortlist-ual-pages \
  -f docker-compose.test.yml -f /tmp/ual-pages-test.yml --profile test \
  run --rm -v "$PWD/backend/app:/app/app:ro" test-runner \
  python -m pytest -o addopts='' -q

# Final focused backend regressions.
docker compose --env-file /tmp/ual-pages-test.env -p uni-shortlist-ual-pages \
  -f docker-compose.test.yml -f /tmp/ual-pages-test.yml --profile test \
  run --rm -v "$PWD/backend/app:/app/app:ro" test-runner \
  python -m pytest -o addopts='' -q tests/test_program_descriptions.py \
  tests/test_program_quality.py tests/test_unicode_slugs.py \
  tests/test_ual_program_pages.py tests/test_admin.py tests/test_library.py \
  tests/test_ingestion.py

# Frontend suite, typecheck, lint and disposable production bundle.
docker compose run --rm --no-deps -v "$PWD/frontend:/app" -v /app/node_modules web npm test
docker compose run --rm --no-deps -v "$PWD/frontend:/app" -v /app/node_modules web npm run typecheck
docker compose run --rm --no-deps -v "$PWD/frontend:/app" -v /app/node_modules web npm run lint
docker compose run --rm --no-deps -v "$PWD/frontend:/app" -v /app/node_modules web \
  npm run build -- --outDir /tmp/uni-quality-dist

# Schema comparison only, enforced read-only; this is not alembic upgrade.
docker compose --env-file /tmp/ual-pages-test.env -p uni-shortlist-ual-pages \
  -f docker-compose.test.yml -f /tmp/ual-pages-test.yml --profile test \
  run --rm -e MIGRATION_TARGET=test -e 'PGOPTIONS=-c default_transaction_read_only=on' \
  -v "$PWD/backend/app:/app/app:ro" test-runner alembic check
```

#### Changed files and manual commit boundaries

| File | Reason |
| --- | --- |
| `backend/app/db/base.py` | New-record Unicode/ASCII slug normalization |
| `backend/app/ingestion/persist.py` | Programme/city slug collisions, exact city/cache identity and legacy city reuse |
| `backend/tests/test_unicode_slugs.py` | Accents, Unicode edge cases, duplicates, legacy IDs/routes/filter regressions |
| `backend/app/services/program_evidence.py` | Reuse existing evidence checks with batched catalogue context |
| `backend/app/services/program_quality.py` | Independent source and academic coverage projections |
| `backend/app/services/catalog.py` | Batched metadata, additive API fields, reviewed description output/private drafts |
| `backend/app/services/library.py` | Consistent saved/comparison quality semantics |
| `backend/tests/test_program_quality.py` | Verification/completeness, missing/mismatched values and batching regressions |
| `backend/app/ingestion/adapters/ual.py` | Narrow, bounded literal description-reference extraction |
| `backend/app/services/program_descriptions.py` | Human-written summary versions, evidence validation and public provenance |
| `backend/app/services/fact_projection.py` | Explicit reviewed description projection |
| `backend/app/services/admin.py` | Description approval through existing fact-review/audit workflow |
| `backend/app/routers/v1/admin.py` | Additive description-summary approval payload |
| `backend/tests/test_program_descriptions.py` | Extraction, wrong-page/template/privacy/history/approval/idempotency safeguards |
| `frontend/src/types/api.ts` | Optional additive quality and description provenance types |
| `frontend/src/utils/programQuality.ts` | Human-readable warning/source/coverage labels |
| `frontend/src/components/ProgramQuality.vue` | Shared source-versus-coverage presentation |
| `frontend/src/components/ProgramCard.vue` | Accurate discovery-card labels |
| `frontend/src/features/program-detail/ProgramDetailView.vue` | Separate quality indicators and description attribution |
| `frontend/src/features/saved/SavedView.vue` | Consistent saved-programme quality labels |
| `frontend/src/features/comparison/CompareView.vue` | Separate page verification and academic coverage rows |
| `frontend/src/services/api/admin.ts` | Optional reviewer summary in existing approval request |
| `frontend/src/features/admin/FactDetailView.vue` | Independent summary/reason entry and accurate verification confirmation |
| `frontend/src/tests/catalogue-rendering.test.ts` | Verified/candidate/missing pages, warning labels, UUID routing and attribution |
| `frontend/src/tests/description-review.test.ts` | Explicit human summary/reason submission requirement |
| `docs/API_Contract.md` | Additive API semantics and description review/privacy contract |
| `docs/UNIVERSITY_SHORTLISTING_PROJECT_STATUS.md` | Verified findings, results, migration boundary and delivery inventory |

Suggested manual commit boundaries: (1) Unicode slugs and their regressions;
(2) source/academic quality API, UI and regressions; (3) description evidence/review
workflow and regressions; (4) accompanying contract/status documentation. No Git
command or commit was performed.

#### Deployment and smallest manual validation

- [~] Backend and frontend images/assets need an explicitly authorized rebuild and
  deployment to expose these changes in the running application. No database
  migration or slug repair is needed. Do not reseed, ingest or reapprove the pilot
  as part of deployment.
- After such deployment, GET `/api/v1/programs` and the published UUID's detail:
  one programme, same UUID/legacy slug/official URL, unchanged legacy data_quality,
  new source status verified and academic status limited. Check all four candidate
  UUIDs remain 404 publicly. Inspect Discover/detail/saved/comparison labels;
  missing duration/language/tuition/requirements/deadline/outcomes must stay unknown.
- The existing UAL institution review must remain approved with 5/5 verified pages.
  The published programme's description should still be absent, since no development
  description evidence or summary review was authorized. Validate description
  extraction/approval in isolation using the focused tests above before any later
  separately approved enrichment operation.
- Before adding universities, review/deploy these changes and retain source-specific
  permissions and explicit identity/publication gates. Academic coverage gaps are
  genuine unknowns, not invented values or an engineering reason to autoapprove.
  Additional official academic sources and editorial description review are future
  controlled data work. Optional existing-slug repair and broader non-Latin
  transliteration/accent-insensitive search are lower-priority separate decisions.


### 2026-10-22 — Global institution reference directory: deployed after exact authorization

#### Submission summary and boundaries

- [x] Official ROR v2.15, published **2026-10-20**, release DOI
  [10.5281/zenodo.23500708](https://zenodo.org/records/23500708), obtained through
  [the official bulk-data release](https://doi.org/10.5281/zenodo.6347574).
  No full-registry REST pagination was used.
- [x] **146,716** source organizations examined; **30,328** active `education`
  references selected; **116,388** inactive/noneducation records excluded.
  **223 country/territory codes**, zero malformed rows, zero repeated ROR IDs,
  zero conflicting source IDs, **913 missing websites**. Counts are source
  coverage, not a census of accredited universities or Master's providers.
- [x] Retrieved 2026-10-22T05:07:28Z; ZIP 39,263,398 bytes. Published MD5
  `5522990688eb1b94811a8145e131b41e` verified. Independently calculated ZIP SHA256:
  `7a7bf58d5ac18436ed98daf5da906913761d54869edf86d405e51966609dd133`.
  Identity data is CC0-1.0; GeoNames location data attribution is retained under
  CC BY 4.0. Manifest records DOI, version, publication/retrieval/validation dates,
  checksums, licensing, source row ordinal and individual record hashes.
- [x] Source ZIP, official metadata and 27,451,392-byte prepared SQLite artifact
  retained under ignored `.ingestion_cache/ror/v2.15/`. Artifact SHA256:
  `7a9522210d1eb34417ac41ff97099ecdf90579742c53d93245eaea15194ae575`.
- [x] Separate `directory_releases` / `directory_institutions` snapshots preserve
  the Master's-first university review model. References are explicitly
  `unreviewed_reference`; websites are candidates or unavailable; Master's
  availability is `not_assessed`. No facts, programmes or approvals are generated.
- [x] Exact strong-ID matching, conflict quarantine and read-only reconciliation:
  **30,322** reference-only records, **1** active ROR match (UAL), **5** archive-only
  matches requiring reconciliation. UAL also has historical archived context;
  its accepted active identity remains unchanged. No name-only merges, archived
  reactivation, identity acceptance or automatic review decisions occurred.
- [x] Development import **succeeded**: **30,328 directory rows**, one release,
  one new bulk source document and one new job; zero source-import failures.
  Job `c87b1464-3965-4cb6-a9e1-9fe59d3fc014`. Existing active catalogue: **1 approved institution,
  0 unapproved active institutions, 5 verified programme-page URLs, 1 published
  Master's programme, 4 unpublished candidates**. Directory reference status is
  independent of those institution/programme review decisions.

#### Implemented architecture and root-cause corrections

The existing `universities` table represents canonical catalogue institutions;
its admin queue derives Master's evidence readiness per institution. Feeding
30,000 identity-only organizations into that table would overwhelm the review
workflow and misrepresent readiness. The minimal additive directory layer avoids
that problem and leaves existing discovery/publication filters intact.

- Streaming bounded JSON-array validation into SQLite; filtered records keyed by
  ROR ID, duplicate/conflicting payload quarantine, resumable source download via
  curl, no per-institution remote calls during import.
- Configurable PostgreSQL batches (1–2,000; validated default 500), atomic row and
  checkpoint commits, release-level advisory lock, resumable existing ingestion
  jobs with per-country and reconciliation counters. Failed batches roll back;
  CLI retry uses the approved plan and recorded job checkpoint.
- Repeat imports insert zero duplicate rows. New source releases retain prior
  snapshots; partial releases stay invisible and the last completed release stays
  available. Reconciliation never changes canonical institutions or claims.
- Plans bind the exact source artifact, database/role, protected catalogue/history
  fingerprints, batch size, and verified backup checksum. Source enabled/use policy
  is enforced. Development requires a backup-bearing plan and exact confirmation.
- Generic admin retry, ordinary source-pipeline adoption and scheduler dispatch
  now refuse/skip directory jobs. This prevents a directory resume from turning
  into ordinary ROR institution ingestion. Admin job metrics explicitly count
  directory references while canonical institution/programme/fact counters stay zero.
- `9c24a7e6d180` creates only two tables and their indexes. Existing archive/reset
  tooling now recognizes this additive schema and records the actual revision;
  unknown revisions still fail closed. No reset was performed on development.
- Public API: `GET /api/v1/directory/institutions` supports Unicode substring
  search `q`, `country`, bounded `page`/`page_size`, explicit unreviewed status and
  release provenance. `GET /api/v1/directory/stats` provides coverage counts.
  Public provenance excludes local file paths. Reviewer/admin-only
  `GET /api/v1/admin/directory/reconciliation` exposes conflicts/archive hints;
  it performs no reconciliation writes. Existing `/programs` is unchanged.

#### Executed tests, real-source rehearsal and preservation

- [x] Pre-change isolated backend baseline: **430 passed, 7 skipped**.
- [x] Initial targeted directory/archive regressions: **25 passed**; final targeted
  directory/archive/admin regression run: **59 passed**. Covers 100/500-record
  imports, repeat imports, duplicate/conflicting ROR IDs, same-name/different-country
  institutions, non-Latin search, absent/malformed websites, rollback and resume,
  partial snapshot visibility, auth, exact-plan refusal, source-policy enforcement,
  malformed JSON, licensing/checksum/host validation and public visibility isolation.
- [x] Complete final backend run against deployed source: **452 passed, 7 skipped**
  (244.62 seconds). Earlier pre-dispatch-guard runs passed 451 tests. The seven
  optional live-source tests remain opt-in; the official bulk release itself was
  retrieved and validated live. No failing tests remain.
- [x] Frontend regression suite: **41 passed**; typecheck, lint and production build
  succeeded. No frontend source/design changes.
- [x] Migration applied only to isolated test and restored recovery databases;
  `alembic check`: **No new upgrade operations detected**.
- [x] Backup outside active PostgreSQL volume:
  `.db-backups/global-directory/uni_shortlist_20261022T050514Z.dump` (+ metadata),
  private file permissions; SHA256
  `fd19ef85bc17ca68dcf11c4e1bd3db622440ebbbf4fa7a8762227f8db83354cb`.
  Restored using `scripts/db-restore-recovery.sh` to separately marked project
  `uni-shortlist-global-recovery`: internal network, no ports, tmpfs PostgreSQL.
- [x] Real release rehearsal: first 500 rows checkpointed, then resumed to
  **30,328 created**, **0 failures**, **5 reconciliation flags**. Recovery job
  `e526e6a0-e912-4d68-96eb-e6d5c73f6093` succeeded. Entire repeated import job
  `55af3067-f141-40e0-a376-b731994085f9`: **0 created, 30,328 unchanged**.
- [x] All **52 original non-schema tables** verified against the original
  development snapshot, excluding only newly added source-document/job rows from
  those two tables. All original source rows/documents/jobs, accounts/roles,
  profiles, reviews/events, facts/versions/evidence, university/programme UUIDs,
  publication decisions and **1,479 archive rows** match original fingerprints.
- [x] Actual restored UAL published programme detail response, including reviewed
  description, equals the running development response. Public Discover remains
  **1**; all four candidate UUIDs return **404**. Scheduler remains false.
- [x] Recovery directory storage: institutions **54,345,728 bytes**, release
  **49,152 bytes**, before WAL/backup overhead. Initial measured reads: first page
  91 ms, Unicode search 117 ms, last page 228 ms, five reconciliation entries 72 ms,
  existing pending institution-review queue 8 ms/zero entries. Local measurements
  are a bounded rehearsal, not a production concurrency benchmark.

#### Actual development deployment verification

- [x] Applied exactly `85b2e4a6c910 → 9c24a7e6d180`; no other migration.
  Runtime role and existing source permissions remain unchanged.
- [x] Backend API image rebuilt and only `api` recreated. No frontend/database
  rebuild/restart, scheduling activation, reseed, archive/reset or review action.
- [x] Live `localhost:8000`, NGINX `localhost:8080` and Vite API proxy
  `localhost:5173` return the new reference directory correctly. Health is ready;
  stats report 30,328 references / 223 country-territory codes. Spanish filter
  returns 223; Unicode `大学` search returns 2,202, with bounded page sizes.
- [x] All 52 original non-schema table fingerprints match after excluding only
  newly added source-document/job rows. No original data was overwritten/deleted.
  Actual UAL public detail, including reviewed description, is byte-equivalent
  after JSON decoding; one published programme remains, all four candidates 404.
- [x] Deployed schema comparison using current source/migration mounts:
  **No new upgrade operations detected**. The separate db-admin image was not
  rebuilt; source/migration mounts are required for its new-head commands.
- [x] Live directory tables occupy 54,403,072 bytes combined (approximately
  51.9 MiB), excluding WAL and backups. Initial live read-only checks: first page
  65 ms, Unicode search 38 ms, last page 99 ms, reconciliation queue 37 ms;
  existing pending institution review queue remains zero entries / approximately 2 ms.
- [x] Development bulk job `c87b1464-3965-4cb6-a9e1-9fe59d3fc014`
  succeeded with 30,328 created / zero updated / zero rejected / zero failures.
  Its five review flags are archive reconciliation items, not approval requests.
  Original source/history rows remain unchanged. The source release overlaps the
  existing approved UAL institution, leaving 30,327 additional ROR reference
  identities without canonical institution approval; every directory snapshot
  remains explicitly unreviewed regardless of separate catalogue decisions.
- [x] No development operation remains awaiting approval for this delivery.
  Future enrichment, canonical promotion, reconciliation, approvals and programme
  publication remain separate operator/reviewer work.

#### Source connector inventory and limitations

| Source | Coverage and reuse | Safe use / limitation |
| --- | --- | --- |
| ROR bulk v2.15 + existing identity connector | Global; CC0 identities, GeoNames attribution | Active education reference directory; no accreditation, programmes, tuition or admissions |
| IPEDS HD2024 (configurable) | US; NCES public-domain directory | Institution identities and graduate flags; dictionary checked; explicit bounded manual run |
| IPEDS IC2023 | US; NCES public domain | Historical 2023–24 institution charges, not current programme tuition |
| NCES CIP | US classification taxonomy; public domain | Discipline reference data, not programme identity or existence |
| UAL Master's | Universidad de Almería, Spain; dataset CC BY | Authentic plan IDs/names; bounded official page evidence; independent human review; HTML is not presumed CC BY |
| French Mon Master | France; Open Licence; historical 2025 campaign | Named offerings/tracks, explicit limit; historical applicability, no invented current availability |
| DUO/RIO | Netherlands; CC BY 4.0 | Named Master's offering IDs/validity, bounded manual only; joint/foreign providers held for review |
| IPEDS Completions | US; disabled pending official dictionary mapping | Not a safe source of individual named programme descriptions |
| WHED | Global; automated access prohibited | Disabled; licence/permission required |
| Erasmus Mundus / licensed provider / community datasets | EU/global depending on source | Disabled awaiting access, credentials/licensing or dataset review |

The registry has **7 enabled connectors**, with **5 persisted source rows**:
ROR, UAL, French Mon Master, IPEDS HD and one manual-reference source. IPEDS IC,
NCES CIP and DUO/RIO are implemented/registered but were not newly persisted or
run against development. Enabled does not mean automatically scheduled.
No other connector or scheduler was enabled. Coverage gaps in named Master's
catalogues remain genuine: ROR cannot fill academic fields, deadlines, prices or
admission requirements. Reference-directory expansion does not make additional
universities ready for Master's approval. Joint providers/subunits and national
accreditation require separate evidence; ROR education type alone proves neither.

#### Exact approved development operation — executed

The user explicitly approved **“Approve exact migration, directory import and API
deployment”** against the operation and confirmation below. All three protected
operations have now completed successfully. The executed operation was:

1. Apply **only** additive migration `9c24a7e6d180` to `uni_shortlist` from current
   `85b2e4a6c910`.
2. Execute `.ingestion_cache/ror/v2.15/development-plan.json` with confirmation
   `55f7d5672dbc7c45795ed6401b79d38c19b6aa94e189ef6cb452d1fb1191143f`:
   one directory release, 30,328 reference rows, one bulk source document and one
   checkpointed job, in batches of 500. Existing ROR source reused. No active
   university, programme, fact, review, archive, student or approval changes.
3. Build the backend API image and replace **only** the API service to expose
   these additive directory routes. No frontend, PostgreSQL or scheduler change.
4. Recheck original data fingerprints, UAL publication visibility, health and the
   directory API. If the protected fingerprint or source artifact changed, the
   import refuses; inspect and obtain approval for a fresh plan.

```bash
# Already executed after exact authorization; retained for audit/resume.
# Do not start a duplicate development run merely to validate the deployment.
docker compose --profile db-admin run --rm --no-deps \
  -e MIGRATION_TARGET=development \
  -v "$PWD/backend/app:/app/app:ro" -v "$PWD/backend/alembic:/app/alembic:ro" \
  db-admin alembic upgrade 9c24a7e6d180

docker compose --profile db-admin run --rm --no-deps \
  -v "$PWD/backend/app:/app/app:ro" \
  -v "$PWD/.ingestion_cache/ror/v2.15:/data:ro" \
  -v "$PWD/.db-backups/global-directory:/backups:ro" \
  db-admin python -m app.ingestion.ror_directory apply --target development \
  --artifact /data/directory.sqlite --plan /data/development-plan.json \
  --confirm 55f7d5672dbc7c45795ed6401b79d38c19b6aa94e189ef6cb452d1fb1191143f

docker compose build api
docker compose up -d --no-deps api
```

Resume an interrupted authorized operation by repeating the same `apply` command
with `--resume-job JOB_UUID` (use its printed checkpoint). Start no new plan while
an old worker is running; the source lock also refuses competing workers. SQL
batch failures are recorded as failed jobs; rerun/resume after addressing the
reported cause. The importer makes no external API requests or rate bursts.

Monitor existing admin **Jobs** / `GET /api/v1/admin/jobs/{JOB_UUID}` (admin)
or the printed JSON progress: seen/created/unchanged, source ordinal, per-country
counts and reconciliation counts. Read-only validation of the completed deployment:

```bash
curl -fsS http://localhost:8000/api/v1/health/ready
curl -fsS http://localhost:8000/api/v1/directory/stats
curl -fsS 'http://localhost:8000/api/v1/directory/institutions?country=ES&page_size=5'
curl -fsS 'http://localhost:8000/api/v1/directory/institutions?q=Almer%C3%ADa'
curl -fsS http://localhost:8000/api/v1/programs
```

Full-suite commands executed (private isolated-test credentials supplied by the
existing env file, never committed):

```bash
docker compose --env-file /tmp/ual-pages-test.env -p uni-shortlist-ual-pages \
  -f docker-compose.test.yml -f /tmp/ual-pages-test.yml --profile test run --rm \
  -v "$PWD/backend/app:/app/app:ro" -v "$PWD/backend/alembic:/app/alembic:ro" \
  test-runner python -m pytest -o addopts='' -q
# Initial targeted: append tests/test_ror_directory.py tests/test_catalogue_reset.py
# Final targeted (59 passed): append the same two files plus tests/test_admin.py

docker compose run --rm --no-deps -v "$PWD/frontend:/app" -v /app/node_modules web npm test
docker compose run --rm --no-deps -v "$PWD/frontend:/app" -v /app/node_modules web \
  sh -c 'npm run typecheck && npm run lint && npm run build'
```

#### Changed files / suggested manual commit boundaries

| File | Purpose |
| --- | --- |
| `backend/app/ingestion/ror_dump.py` | Official release/checksum validation, bounded parsing, filtered keyed local artifact |
| `backend/app/ingestion/ror_directory.py` | Read-only exact planning, reconciliation, transactional batch import/resume and provenance |
| `backend/app/models/directory.py` | Separate versioned reference snapshots |
| `backend/app/models/__init__.py` | Register additive directory models |
| `backend/alembic/versions/9c24a7e6d180_reference_directory.py` | Two-table additive migration; populated downgrade refuses history loss |
| `backend/app/db/catalogue_reset.py` | Preserve existing archive regressions on the additive directory schema; exact revision in plans |
| `backend/app/services/directory.py` | Paginated/searchable references, coverage and restricted reconciliation |
| `backend/app/routers/v1/directory.py` | Additive public reference and protected reconciliation endpoints |
| `backend/app/routers/v1/router.py` | Register directory routes |
| `backend/app/services/admin.py` | Accurate directory job counters; block generic retry that bypasses the approved bulk plan |
| `backend/app/ingestion/pipeline.py` | Refuse adopting directory jobs into normal catalogue ingestion |
| `backend/app/core/scheduler.py` | Exclude directory jobs from ordinary queued-job dispatch |
| `backend/tests/test_ror_directory.py` | Bulk scale, safety, identity, rollback/resume and API regressions |
| `docs/API_Contract.md` | Document new reference-only endpoints and separation from reviewed catalogue |
| `docs/UNIVERSITY_SHORTLISTING_PROJECT_STATUS.md` | Verified source, counts, tests, safety, protected commands and deployment state |

Suggested manual commits: (1) directory schema/importer and isolated regressions;
(2) read-only directory APIs/contract; (3) verified status. No Git operations or
commits were performed. Raw source artifacts, plans, logs and private backups
remain ignored and must not be committed.


**Submission-ready outcome:** UniShortlist now serves a source-versioned global
reference directory of **30,328 active education organizations in 223 country and
territory codes**, backed by the official ROR v2.15 bulk release and verified
checksums. It supports search, country filtering, pagination, conflict/archive
inspection and checkpointed, idempotent batch imports. The reviewed Master's
catalogue remains independently gated: **one approved UAL university, five
verified official programme pages, one published programme and four candidates**.
All original data/history was preserved. Final automated results: **452 backend
passed / 7 opt-in skips; 41 frontend passed; typecheck/lint/build/schema checks
passed**. Controlled expansion of real Master's offerings still requires suitable
permitted programme sources and explicit evidence/reviewer decisions.

### 2026-10-22, 08:20 UTC / 13:50 IST — Documentation-only recovery checkpoint

The user paused implementation to preserve context before the usage limit.
Only Markdown documentation was created/edited. No Git commands, database writes,
tests, ingestion, migrations, approvals, publications, restores, deployments,
scheduling changes or external source crawls were performed for this checkpoint.
Earlier records above remain historical and are not rewritten by this addition.

#### Read these first

- [Interrupted work recovery](UNISHORTLIST_INTERRUPTED_WORK_RECOVERY.md): exact
  interruption, files, source snapshots, isolated experiments, backup/plan hashes,
  commands, permission boundary and ready-to-copy next-session prompt.
- [Complete project handover](UNISHORTLIST_COMPLETE_PROJECT_HANDOVER.md): architecture,
  chronology, actual deployment, schema/migrations, pilot, tests and incomplete work.
- [Global programme execution plan](UNISHORTLIST_GLOBAL_PROGRAMME_EXECUTION_PLAN.md):
  client requirement matrix, milestone dependencies and ordered backlogs.
- [Source coverage matrix](UNISHORTLIST_SOURCE_COVERAGE_MATRIX.md): all registered,
  disabled/proposed sources, rights, actual counts and all 223 reference-country codes.
- [Submission summary](UNISHORTLIST_DEADLINE_SUBMISSION_SUMMARY.md): client-facing
  account of deployed coverage versus isolated international import capacity.

#### Independently checked current development state

Read-only SQL and current public GET requests confirmed:

| Measure | Current development |
| --- | --- |
| Database / revision | `uni_shortlist` / `9c24a7e6d180` |
| ROR reference directory | **30,328 records / 223 country-territory codes** |
| Canonical institutions / active approvals | **1 / 1**, Universidad de Almería |
| Master's programmes / accepted source identities | **5 / 5**, all UAL |
| Verified individual official-page facts | **5** |
| Published / candidates | **1 / 4** |
| Facts / versions / evidence | **66 / 67 / 67** |
| Source documents / ingestion jobs / audits | **14 / 23 / 15** |
| Archived catalogue records | **1,479** |
| Users / profiles | **2 / 1** |
| Running main services | `db` healthy; `api`, `web`, `nginx` running; isolated test DB also running |
| Readiness / public Discover | Ready / **one** published programme |
| Runtime / scheduling | `uni_shortlist_app` / **disabled** |

UAL ROR `003d3xx08` is accepted; the separate UAL publisher claim remains pending
while the source association is approved. All five URL facts retain the correct
plan code. The published programme UUID remains
`2fffabd2-fd80-43d9-a6a8-6d0e9d6702c8`, with reviewed description and unchanged
legacy slug. Missing academic values remain unknown. Archived reviews remain
detached from active institution matching/approval.

#### Interrupted international programme work — completed in isolation only

- [x] Existing DUO/RIO and Mon Master sources accessed and rights/version metadata
  captured; immutable official snapshots preserved under
  `.ingestion_cache/program-expansion/`.
- [x] New `backend/app/ingestion/program_import.py` wraps the existing pipeline:
  frozen capture/replay, permission and identity holds, exact backed-up plans,
  outer transaction/savepoints, unchanged-original-row checks and idempotent retry.
- [x] New `program_coverage.py` reports actual PostgreSQL coverage read-only.
- [x] Real isolated recovery addition: **1,501 Dutch offerings / 41 pending
  providers + 7,843 historical French 2025 offerings / 108 pending institutions**
  = **9,344 extra candidates / 149 institutions**. Repeated import added zero
  programmes/facts/evidence. Source jobs retain `partial` for known holdout warnings,
  not missing selected records; no unexpected selected-record failures/conflicts.
- [x] Independently queried isolated recovery now has **150 institutions / 9,349
  programmes**, one approved institution / one published programme, 80,713 facts,
  80,717 versions, 81,599 evidence records, 119 source documents and 1,479 archive rows.
- [x] Provider shared-board/subunit ambiguity held: 23 Dutch providers / 693
  offerings. French holds: two archived identities / 312 offerings and three
  overlong titles. No archive identity was automatically revived or merged.
- [x] Fixed confirmed multi-page dry-run source-FK rollback, provider cache scoping,
  campaign/joint classification and persisted-source policy handling. Bounded
  corrected 100-record dry runs and actual full isolated persistence passed.
- [x] Review-detail evidence batching measured 279 → 29 queries in a representative
  12-programme institution. Final queue fast path measured 1.908 seconds for 149
  pending institutions, correct evidence-collection stage counts. Saved verification
  confirms 54 original table fingerprints, unchanged UAL public detail/description,
  Discover one, and candidate UUIDs hidden.
- [x] **Final automated regression completed on the final file state** (OpenCode
  continuation, 2026-10-22 09:00 UTC). Isolated runner, current source mounted:
  full backend suite **470 passed / seven opt-in skips in 174.61 s**; targeted
  `test_program_import.py` **17 passed in 59.12 s**; admin/quality/institution-review/
  adapter/ingestion subset **152 passed in 42.81 s**; frontend **41 passed** with
  clean typecheck, lint and build. `alembic current`/`heads` = `9c24a7e6d180`;
  `alembic check` reports "No new upgrade operations detected". The 465/41 figures
  above are historical and are superseded by this run.
- [x] Five regression gaps closed in `backend/tests/test_program_import.py` (this
  is the 465 → 470 delta): mixed Dutch/French single plan, cross-source no-merge,
  identical-name provider hold, 20-institution queue pagination/stage determinism,
  catalogue/publication/archive preservation, and interrupted-apply → clean
  rollback → exact re-apply.
- [x] New importer and review-performance code **deployed 2026-10-22 10:05 UTC**
  (user-approved operation B). API image `1211a2a67b55` → `9e5d86be4360…`; only the
  `api` service was recreated — `db`, `db-test`, `nginx` and `web` kept their original
  start times. No migration/model/frontend change was introduced.
- [x] **Development import approved and executed 2026-10-22 09:45–09:58 UTC** (user-approved
  operation A). See the execution checkpoint below and
  [interrupted recovery §11](UNISHORTLIST_INTERRUPTED_WORK_RECOVERY.md).
  The exact operation proposal is prepared and awaiting explicit user approval.

Saved unapproved plan: `.ingestion_cache/program-expansion/plans/development.json`;
9,344 candidate additions / 149 pending institutions; confirmation
`38ca6c48b406b8908e6e450eb0da962f05c9e02c40c399edf8e1d4829ee69a2f`.
Pre-programme backup: `.db-backups/program-expansion/uni_shortlist_20261022T063327Z.dump`,
SHA256 `bba27871fef9b42e7628746a465d4a18f21dcb5bc1aeb1b85e713e6a681381ff`.
This checksum is not authorization; any drift requires fresh inspection/plan.
No migration is needed for this candidate import. An API-only deployment is a
separate protected operation. Earlier ROR approval does not cover either action.

**Next session:** read the recovery file, validate final queue regressions and full
isolated suite, verify snapshots/backup/plan freshness, then prepare the precise
development-import request. Preserve the deployed directory and UAL pilot. Do not
repeat ROR import, catalogue reset, approvals or description work. Only after exact
user authorization may the candidate operation proceed. Current submission can
demonstrate the deployed reference directory and reviewed UAL pilot, plus a genuine
international programme import **rehearsal**, not 9,344 deployed programme additions.

### OpenCode continuation checkpoint — 2026-10-22, 09:00–09:10 UTC / 14:30–14:40 IST

Code inspection, read-only verification and isolated testing only. **No development
database write, migration, deployment, review decision, publication, source crawl
or scheduler change was performed.**

#### Independently re-verified development baseline (read-only SQL)

| Measure | Value |
| --- | --- |
| Alembic revision | `9c24a7e6d180` |
| Canonical universities / approved | 1 / 1 |
| Programmes (published / candidate) | 5 (1 / 4) |
| Accepted programme identities | 5 |
| Verified `official_program_page_url` facts | 5 |
| ROR directory rows / country-territory codes | 30,328 / 223 |
| Facts / source documents / ingestion jobs | 66 / 14 / 23 |
| Archived catalogue records | 1,479 |
| Public Discover | `total_items: 1` |
| Scheduler | disabled |

Published programme and its university are unchanged:
`2fffabd2-fd80-43d9-a6a8-6d0e9d6702c8` (slug `m-ster-en-comunicaci-n-social`) at
`08a617bb-ffe6-40b3-aadb-aa71d34d9918` (Universidad de Almería).

Isolated recovery `uni_shortlist_recovery` was also re-read and is unchanged:
150 institutions (1 approved / 149 pending), 9,349 programmes (ES 5 / NL 1,501 /
FR 7,843), 1 published and 9,348 candidates, 80,713 facts / 80,717 versions /
81,599 evidence, 119 source documents, 1,479 archive rows, zero rows in
`program_fees`, `admission_requirements` and `program_intakes`.

#### Frozen artefact integrity re-checked (read-only file hashing)

| Artefact | Result |
| --- | --- |
| `code_hash()` vs `plans/development.json` | **match** — `75e159351e475196fd5211c623adf3b005ef3007117798f076eae2566df2801d` |
| DUO snapshot manifest SHA256 | **match** — `7552d042304b5a09c214cb4d9a0f68f7454e57b7fde6ce4a12932de6fd69d13c`; 28/28 response bodies rehashed, **0 missing / 0 mismatched** |
| Mon Master snapshot manifest SHA256 | **match** — `596ebe9336fedfba…`; 82/82 response bodies rehashed, **0 missing / 0 mismatched** |
| Pre-import backup SHA256 | **match** — `bba27871fef9b42e7628746a465d4a18f21dcb5bc1aeb1b85e713e6a681381ff`, 6,050,213 bytes |
| `confirmation_sha256` recomputed | **match** — `38ca6c48b406b8908e6e450eb0da962f05c9e02c40c399edf8e1d4829ee69a2f` |
| Planned additions | 9,344 programmes / 149 new institutions |
| Held by plan | DUO 23 shared-board-subunit providers; FR 2 archived UAI identities; FR 3 over-limit titles |

The plan remains internally consistent and unapproved. A checksum is an integrity
token, **not** execution authority.

#### Files changed in this continuation

- `backend/tests/test_program_import.py` — only. The `snapshot()` fixture helper
  gained a `name` argument so several independent snapshots can be captured in one
  test, and five regressions were appended. **No application code was changed.**

#### Fresh isolated results (current source mounted, marked isolated PostgreSQL)

| Command | Result |
| --- | --- |
| `pytest tests/test_program_import.py` | **17 passed** in 59.12 s |
| `pytest tests/test_admin.py tests/test_program_quality.py tests/test_ual_institution_review.py tests/test_duo_rio_adapter.py tests/test_monmaster_adapter.py tests/test_ingestion.py` | **152 passed** in 42.81 s |
| `pytest` (full backend) | **470 passed, 7 skipped** in 174.61 s |
| `alembic current` / `heads` / `check` | `9c24a7e6d180` / `9c24a7e6d180` / "No new upgrade operations detected" |
| `npm run test` (frontend) | **41 passed**, 7 files, 3.18 s |
| `npm run typecheck` / `lint` / `build` | all clean |

The seven skips remain the explicit `RUN_LIVE_INGESTION_TESTS=1` opt-ins in
`tests/test_ingestion_live.py`. This run **is** on the final file state, including
the last queue fast path and its query-count assertions.

#### New regressions added (465 → 470)

1. `test_mixed_source_plan_keeps_national_offerings_and_identities_separate` — one
   plan carrying both national sources; disjoint identifier namespaces
   (`duo:offering:*` vs `fr-monmaster:ifc:*`); an identical institution name in NL
   and FR stays **two** canonical universities; 18 candidates, 2 pending reviews,
   0 approved, 0 published; replay adds nothing.
2. `test_second_provider_with_an_identical_name_is_held_instead_of_merged` — a new
   provider identifier sharing an existing institution name is **held** with reason
   `name_country`; the existing canonical university is not duplicated.
3. `test_review_queue_pagination_is_deterministic_and_stage_filtered_at_scale` —
   20 institutions / 100 offerings; 4 pages of 5 are disjoint and complete;
   pagination is stable across repeated calls; stage filtering happens before
   pagination; **each item's own `workflow_stage` agrees with the queue fast-path
   bucket**; query count bounded.
4. `test_existing_catalogue_publication_and_archive_state_survive_the_import` —
   pre-existing programme UUIDs/slug/publication status and university rows are
   unchanged, archive count unchanged, public Discover unchanged, every new
   programme returns 404, nothing newly published.
5. `test_interrupted_import_leaves_nothing_behind_and_the_exact_plan_reapplies` —
   an injected mid-import failure leaves zero partial catalogue/document state and
   an unchanged original-row fingerprint; re-applying the *same* approved plan
   completes the exact 100-record addition.

#### Queue fast-path equivalence established

`discovery_stage()` can return `ready_for_review`, `discovery`, `program_evidence_needed`,
`website_evidence_needed` or `institution_evidence_needed`. The queue groups only
`discovery` / `evidence_collection` / `ready_for_review`, mapping the three
"*_needed" stages onto `evidence_collection`. Because an absent canonical website
always blocks approval, a website-less institution can never be `ready_for_review`,
so the fast path (no website → `discovery` with no programmes, otherwise
`evidence_collection`) is **exactly equivalent** to full serialization. Regression 3
asserts this on real imported data.

#### Next action

Submit the exact bounded development import and deployment proposal for explicit
approval. Until that approval is given, development must remain at five programmes.

### Execution checkpoint — 2026-10-22, 09:45–10:10 UTC / 15:15–15:40 IST — IMPORT AND DEPLOYMENT COMPLETE

> User approved both operations explicitly. Full execution record with every gate and
> query: [interrupted recovery §11](UNISHORTLIST_INTERRUPTED_WORK_RECOVERY.md).

Both protected operations are now **executed and independently verified**.

| Measure | Before | After |
| --- | --- | --- |
| Programmes (published / candidate) | 5 (1 / 4) | **9,349 (1 / 9,348)** |
| Canonical institutions | 1 | **150** (149 pending: FR 108, NL 41) |
| Global ROR directory rows / countries | 30,328 / 223 | **30,328 / 223** (unchanged) |
| Archived catalogue records | 1,479 | **1,479** (unchanged) |
| Facts / versions / evidence | 66 / 67 / 67 | **80,713 / 80,717 / 81,599** |
| Source documents | 14 | **119** |
| Approved institution reviews | 1 | **1** (unchanged — UAL only) |
| Verified facts | 8 | **8** (unchanged — UAL only) |
| Fees / requirements / intakes | 0 / 0 / 0 | **0 / 0 / 0** (unchanged) |
| Alembic revision | `9c24a7e6d180` | `9c24a7e6d180` (no migration) |
| API image | `1211a2a67b55` | `9e5d86be4360…` (API service only) |
| Public Discover | `total_items: 1` | **`total_items: 1`** (API and NGINX) |

- **Operation A** — bounded import from the frozen, checksum-verified snapshots under the
  approved plan (confirmation `38ca6c48…`, backup `bba27871…`): **1,501 Dutch** offerings
  (40.0 s) and **7,843 historical French 2025** offerings (744.35 s) in one atomic,
  advisory-locked transaction. Both sources `partial` as planned (holds only);
  `validation_errors: []`, `http_failures: []`, `programs_rejected: 0`, `review: 0`.
- **Idempotent replay** of the identical command: **0 programmes, 0 institutions,
  0 facts, 0 documents**; all counts unchanged.
- **Operation B** — only the `api` service rebuilt and replaced. `db`, `db-test`, `nginx`
  and `web` kept their original start times. No migration ran. The deployed image now
  contains `program_import.py` and matches the workspace hashes for `admin.py`,
  `catalog.py` and `program_evidence.py`; its `code_hash()` equals the workspace value.
- **Safeguards held on the real database**: 0 auto-approvals, 0 auto-verified facts,
  0 auto-publications, 0 duplicate `(source_key, external_key)` pairs, UAL UUIDs/slug/
  479-char reviewed description and all 8 UAL evidence rows unchanged, all 7,843 French
  offerings labelled `academic_campaign = {"session":"2025"}`, sampled NL/FR candidates
  return HTTP 404 publicly, scheduler disabled.

Two observations recorded honestly:
1. **504 slug values are shared by 1,883 candidate rows** (all French, all `candidate`,
   none published; UAL slug unique). Harmless today — public routing is by UUID and
   `_load_program()` requires `published` + `is_active` + approved institution — but
   **slug disambiguation must be handled in human review before any French publication**.
2. **13 pre-existing university-less pending reviews (2026-10-20)** remain; **0** were
   created during the import window. Untouched.

**Next:** human review of the 149 pending institutions and their 9,344 candidates.
Development must not be re-imported, and no programme may be published, without
reviewer decisions. Remaining original work is unchanged: Dutch provider reconciliation
(23 held providers), French archived-identity reconciliation (2 held UAI), verified
course pages and academic enrichment.

---

## Import validity audit (2026-10-23)

A separate verification-only audit independently re-derived the imported catalogue from
the frozen source snapshots (not import counters), audited every stored URL, and ran
bounded, policy-compliant reachability checks. Full report:
`docs/UNISHORTLIST_PROGRAMME_IMPORT_VALIDITY_AUDIT.md`.

Headline findings:

- **Snapshot↔database field agreement is 100% over all 9,344 imported records — 0 mismatches** on title, provider/UAI identifier, country, degree level and publication status; **0 database rows absent from source**.
- **Institution association:** all 149 checked, **0** cross-country collisions, **0** duplicate canonical names, **0** identifier reuse, **0** name mismatches vs source.
- **URLs:** 419 distinct; 5 individual programme pages (all UAL, all HTTP 200); 316 checked, 280 passed, 30 failed — **all 30 are infrastructure (16 `ou.nl` DNSSEC SERVFAIL, 2 `hotelschool.nl` CA-chain) or stale source-reported DUO URLs (10 × 404), none fabricated**. 103 government API endpoints deliberately unpollled.
- **Public surface re-confirmed:** Discover `total_items: 1` on `:8000` and `:8080`; candidates → HTTP 404; `ENABLE_SCHEDULER=false`; DB counts byte-identical to post-import baseline.

Development DB was **not** written to during the audit.
