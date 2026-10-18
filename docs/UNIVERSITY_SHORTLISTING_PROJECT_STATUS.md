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
- **Currency FX:** fixed reference table of dated rates seeded as clearly-labelled planning rates; no live FX provider in MVP.
- **Seed data:** all catalogue rows from fixtures are labelled `unverified`/`estimated` with synthetic source URLs marked `demo_fixture=true`; never presented as official verified facts.

## Phase 0 — Bootstrap

- [ ] Git repo, .gitignore, .env.example, README, docker-compose (db/api/web/nginx), folder layout
- [ ] This status tracker

## Phase 1 — Database foundation

- [ ] SQLAlchemy models: reference (countries, cities, fields), catalogue (universities, campuses, programs, intakes, requirements, fees)
- [ ] Evidence/provenance models (sources, source_documents, fact_records, fact_versions, fact_evidence, fact_review_events)
- [ ] Identity/profile models (users, roles, user_roles, student_profiles, country prefs, priorities)
- [ ] Recommendation models (rulesets, runs, items, requirement_evaluations) + saved/comparisons
- [ ] Finance models (cost scenarios, scholarships + rules/links, funding opportunities, loan/ROI scenarios) + outcomes, living costs, official rules, audit, ingestion jobs
- [ ] Alembic init + initial migration; fresh-DB upgrade verified
- [ ] Seed reference data + labelled demo fixtures

## Phase 2 — Backend core + auth

- [ ] Config, error envelope + request_id middleware, health/meta endpoints
- [ ] Auth endpoints (register/login/logout/me), JWT, roles, ownership dependencies, rate limiting

## Phase 3 — Catalogue & discovery API

- [ ] GET /programs (search/filter/sort/pagination) + detail, requirements, fees, intakes, evidence, outcomes

## Phase 4 — Profile & onboarding API

- [ ] GET/PUT/PATCH /profile, completeness, onboarding/complete with 8-question validation

## Phase 5 — Eligibility & recommendation engines

- [ ] Deterministic rule evaluator (groups/operators, mandatory-unknown rule)
- [ ] Hard constraints → fit scoring → tiers; run persistence + recommendations endpoints + explanations

## Phase 6 — Save/compare/finance/scholarships/loans/ROI/destinations

- [ ] Saved programs + comparisons + POST /programs/compare
- [ ] Cost estimates (line items, low/base/high, currency/period preserved)
- [ ] Scholarships list/detail/matches + funding opportunities
- [ ] Loan scenarios (EMI math) + ROI scenarios (unit tested)
- [ ] Destinations countries/cities/rules + outcomes search

## Phase 7 — Admin/review API

- [ ] Review queue, fact detail/history, approve/reject/request-evidence + audit events
- [ ] Sources registry CRUD, refresh enqueue, jobs list/retry, audit-event filter, scheduler

## Phase 8 — Frontend

- [ ] App shell: router, guards, layouts/nav, typed API client, stores, error handling
- [ ] Auth screens + 8-step onboarding wizard + profile
- [ ] Discover + program detail (evidence tabs)
- [ ] Shortlist runs + run detail, compare, saved
- [ ] Finance, scholarships, loans, ROI, destinations
- [ ] Admin: review queue, fact detail, sources, jobs, audit
- [ ] Landing, settings, privacy/terms, 404; loading/empty/error/stale states everywhere

## Phase 9 — Verification

- [ ] Backend pytest suite on fresh PostgreSQL (constraints, ownership, engines, math)
- [ ] Frontend type-check, lint, unit tests, production build
- [ ] Real integration journey (signup → onboarding → shortlist → detail → compare → save → finance → admin review)
- [ ] docker compose build/up verification

## Blockers / open items

- `docs/refernce image.png` could not be viewed (model limitation): UI follows documented design in UI_Flow_and_Routes.md + implementation plan §12.
- Pilot countries/fields/program counts (plan §17) still owned by product owner; demo fixtures used meanwhile and clearly labelled.
