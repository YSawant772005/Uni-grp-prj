# University Shortlisting Tool — Project Status

Single source of implementation progress. Markers: `[ ]` not started, `[~]` in progress, `[x]` completed+verified, `[!]` blocked/failing.
Update after each meaningful task with test results and commit reference.

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

## Blockers / open items

- `docs/refernce image.png` could not be viewed (model limitation): UI follows documented design in UI_Flow_and_Routes.md + implementation plan §12.
- Pilot countries/fields/program counts (plan §17) still owned by product owner; demo fixtures used meanwhile and clearly labelled.
