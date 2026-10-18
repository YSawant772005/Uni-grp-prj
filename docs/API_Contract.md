# University Shortlisting Tool — API Contract
**Version:** 1.0  
**Status:** Proposed implementation contract aligned to the implementation/architecture plan.  
**Base path:** `/api/v1`  
**Audience:** Frontend, backend, database, QA, and AI coding agents.

## 1. Purpose and contract rules
This document defines the expected HTTP interface between Vue frontend and FastAPI backend. The endpoint inventory is a project baseline and should be implemented consistently. Where deployment/auth decisions remain open, use the explicit rule in this document and record any approved change in the decision log.

- Stack: Vue 3 + TypeScript + Vite; Python + FastAPI + Pydantic; PostgreSQL; Alembic; background worker/queue.
- Backend responses are authoritative for eligibility, recommendations, costs, funding matching, loan calculations and ROI calculations.
- Database is not exposed directly to the browser. All access goes through authenticated/authorized API services.
- Use JSON for request/response bodies unless an endpoint explicitly serves a file.
- Publish the generated OpenAPI schema at `/docs` in development and maintain examples.
- Do not silently change endpoint names, field names, enum values or nullability. Coordinate contract changes and update frontend types/tests.
- No endpoint may fabricate missing university facts. Unknown/unavailable is a valid response state.
- All private resources must enforce ownership and role checks on the server.

## 2. Base URL, versioning and content negotiation
- Local development base: `http://localhost:8000/api/v1` (configurable).
- `Content-Type: application/json` for JSON requests.
- `Accept: application/json` for normal API calls.
- API prefix version is `/api/v1`. Breaking changes require a versioned migration plan; additive optional fields are preferred.
- CORS origins must be explicitly configured for known frontend origins.
- Do not place secrets or private student details in URLs/query strings.

## 3. Authentication and authorization
The implementation blueprint leaves the final session/token mechanism configurable. For the first implementation, use one established secure mechanism selected by the backend owner and document it in `.env.example`/README. Prefer secure, HttpOnly cookies when the deployment supports them; if bearer tokens are chosen, follow the selected library's refresh/revocation guidance. The browser must never store server secrets.

Roles:
- `student`
- `reviewer`
- `admin`
- `worker` (service identity, not an interactive user)

Rules:
- Public catalogue endpoints may be readable without login according to deployment policy.
- Student-private resources require authentication and ownership checks.
- Reviewer/admin endpoints require explicit roles.
- Worker endpoints should not be exposed as public API; use queue/service credentials.
- Do not trust `user_id`, role or ownership fields from client payloads.
- Authentication endpoints must be rate-limited; error messages must avoid account enumeration.

## 4. Common conventions
### 4.1 IDs and timestamps
- Use opaque UUIDs for primary public API IDs unless an existing repository standard has already been approved.
- Timestamps use ISO 8601 UTC, e.g. `2026-10-17T10:30:00Z`.
- Dates without time use `YYYY-MM-DD`.
- Country codes use ISO 3166-1 alpha-2 where applicable; currencies use ISO 4217; languages use BCP 47 or ISO language tags consistently.
- Money must carry amount, currency, period/basis and data status; never treat different currencies or time bases as directly comparable.

### 4.2 Pagination
List endpoints use:
`page` (1-based, default 1), `page_size` (default 20, maximum 100), and optional `sort`/`order` where supported.
Standard paginated response:
```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total_items": 0,
  "total_pages": 0
}
```
`total_items` may be omitted only if the endpoint explicitly documents cursor pagination. Pagination is server-side.

### 4.3 Filtering and sorting
- Unknown filter values should produce a clear validation error rather than silently changing meaning.
- Sort fields must be allowlisted; never interpolate user-provided sort strings into SQL.
- Search should have documented matching behavior and sensible query length limits.
- Filters and sort must be deterministic for stable pagination.

### 4.4 Standard error response
Use a consistent error envelope:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "One or more fields are invalid.",
    "request_id": "uuid",
    "details": [
      {"field": "budget.amount", "code": "must_be_positive", "message": "Amount must be greater than zero."}
    ]
  }
}
```
Suggested HTTP mapping:
- `400` malformed request/business conflict where 422 is not appropriate
- `401` unauthenticated
- `403` authenticated but forbidden
- `404` not found or inaccessible private resource (avoid leaking ownership)
- `409` state/version conflict
- `413` upload too large
- `422` schema/field validation
- `429` rate limit
- `500` unexpected server error with request ID only; no stack trace/secrets
- `503` temporary dependency/service unavailability

### 4.5 Provenance model for facts
A critical fact returned to the UI should include a compact provenance object where applicable:
```json
{
  "value": 15000,
  "unit": "EUR",
  "period": "academic_year",
  "academic_year": "2026-2027",
  "applicable_intake": "2027-fall",
  "status": "verified",
  "source": {
    "source_id": "uuid",
    "title": "Official program fees",
    "url": "https://example.edu/program/fees",
    "retrieved_at": "2026-10-17T10:00:00Z",
    "verified_at": "2026-10-17T10:30:00Z"
  }
}
```
Illustrative only. Never emit a fake official URL or claim a synthetic fixture is verified.

## 5. Endpoint inventory
The following is the agreed proposed route inventory. An endpoint can be deferred only if the feature is explicitly deferred from the release; do not ship a visible UI control with no defined behavior.

### 5.1 Health and metadata
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/health/live` | Public/internal | Process liveness |
| GET | `/health/ready` | Public/internal, safe output | Dependency readiness |
| GET | `/meta` | Public | API version and non-sensitive capability metadata |

### 5.2 Authentication and account
| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/auth/register` | Public, rate-limited | Create account |
| POST | `/auth/login` | Public, rate-limited | Authenticate |
| POST | `/auth/logout` | Authenticated | End session/revoke selected credential |
| GET | `/auth/me` | Authenticated | Current user and role-safe account summary |
| POST | `/auth/password-reset-requests` | Public, rate-limited if password auth enabled | Start reset flow without account enumeration |
| POST | `/auth/password-resets` | Public with valid one-time token | Complete reset flow |

### 5.3 Student profile and onboarding
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/profile` | Student, own profile | Retrieve profile |
| PUT | `/profile` | Student, own profile | Replace/update profile according to documented PUT semantics |
| PATCH | `/profile` | Student, own profile | Partial profile update |
| GET | `/profile/completeness` | Student | Required/optional profile completion summary |
| POST | `/profile/onboarding/complete` | Student | Mark wizard complete and validate required quick-profile fields |
| POST | `/profile/export-requests` | Student | Request export if implemented |
| POST | `/profile/deletion-requests` | Student | Request account/data deletion according to retention policy |

Minimum quick profile:
- intended degree/level
- field/specialization
- preferred countries
- academic background (degree, institution, grade value and scale)
- graduation year/status
- English-test status and score details if available
- total budget with currency and basis
- target intake (year/term)

The full profile can additionally capture backlogs, course prerequisites, standardized tests, work experience, projects, career goals, preferences and priorities. Use explicit fields and controlled enums where possible. Do not assume every field is known at onboarding.

### 5.4 Programs and discovery
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/programs` | Public or authenticated per deployment policy | Search/list/filter programs |
| GET | `/programs/{program_id}` | Public or authenticated per policy | Program overview |
| GET | `/programs/{program_id}/requirements` | Public or authenticated per policy | Admission requirements and prerequisites |
| GET | `/programs/{program_id}/fees` | Public or authenticated per policy | Tuition and other fee facts |
| GET | `/programs/{program_id}/intakes` | Public or authenticated per policy | Intakes and deadlines |
| GET | `/programs/{program_id}/evidence` | Public or authenticated per policy | Sources and fact provenance |
| GET | `/programs/{program_id}/outcomes` | Public or authenticated per policy | Career/outcome evidence with scope |
| GET | `/programs/{program_id}/reviews` | Public or authenticated per policy | Moderated reviews if enabled |

Suggested `GET /programs` query parameters:
`q`, `country`, `city`, `field`, `degree_level`, `language`, `intake`, `min_duration_months`, `max_duration_months`, `max_tuition`, `currency`, `recognition_status`, `page`, `page_size`, `sort`, `order`.
Budget/tuition filtering must clearly define whether it filters tuition alone or full estimated cost. Do not conflate them.

### 5.5 Eligibility and recommendations
| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/eligibility/evaluations` | Student; own profile or explicitly supplied permitted inputs | Evaluate one or more programs against rules |
| POST | `/recommendations` | Student | Create a new recommendation run |
| GET | `/recommendations` | Student | List own recommendation runs |
| GET | `/recommendations/{run_id}` | Owner only | Retrieve run and portfolio |
| POST | `/recommendations/{run_id}/refresh` | Owner only | Create a new run based on current profile/data; preserve original |
| GET | `/recommendations/{run_id}/explanations` | Owner only | Detailed reasons, exclusions, rule outcomes and score breakdown |

Eligibility enum:
- `eligible`
- `conditionally_eligible`
- `ineligible`
- `unknown_needs_review`

These describe evidence-based requirement assessment, not admission probability. Each evaluated requirement must return status, evaluated value, expected condition, evidence/source reference, and explanation. If a mandatory requirement is unknown, the program must not be presented as fully eligible.

Recommendation behavior:
- Apply strict hard constraints before soft preference scoring.
- Return tier labels `ambitious`, `target`, `safer_fit` using a documented configurable heuristic.
- Do not call safer-fit “safe admission”.
- Explain inclusion, exclusion, uncertainty, score dimensions and active ruleset version.
- Never produce a numeric admission probability unless a separately validated model and relevant permissioned data exist.
- Persist run inputs/profile snapshot reference, data/ruleset versions, timestamp and results for reproducibility.

Illustrative request:
```json
{
  "profile_id": "uuid",
  "filters": {
    "countries": ["DE", "NL"],
    "fields": ["artificial_intelligence"],
    "max_total_budget": {"amount": 2000000, "currency": "INR", "basis": "full_degree"}
  },
  "limit_per_tier": 20
}
```
Illustrative response:
```json
{
  "run_id": "uuid",
  "created_at": "2026-10-17T10:30:00Z",
  "ruleset_version": "eligibility-v1",
  "tiers": {
    "ambitious": [],
    "target": [],
    "safer_fit": []
  },
  "excluded_count": 0,
  "data_warnings": []
}
```

### 5.6 Save, shortlist and comparison
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/saved-programs` | Student | List own saved programs |
| POST | `/saved-programs` | Student | Save a program |
| DELETE | `/saved-programs/{program_id}` | Student | Remove saved program |
| GET | `/comparisons` | Student | List saved comparisons if supported |
| POST | `/comparisons` | Student | Create/save a comparison |
| GET | `/comparisons/{comparison_id}` | Owner only | Retrieve comparison |
| PATCH | `/comparisons/{comparison_id}` | Owner only | Update selected programs/title |
| DELETE | `/comparisons/{comparison_id}` | Owner only | Delete saved comparison |
| POST | `/programs/compare` | Public/authenticated according to policy | Return normalized comparison data for supplied program IDs |

Comparison requests must validate the configured maximum number of programs, reject duplicate IDs or normalize them consistently, and return comparable facts with status/currency/period/source. Do not turn missing data into zero.

### 5.7 Affordability, funding and loans
| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/cost-estimates` | Public/authenticated per policy; saved scenarios require auth | Calculate cost breakdown/scenarios |
| GET | `/programs/{program_id}/cost-estimates` | Public/authenticated per policy | Retrieve available cost facts/estimates |
| GET | `/scholarships` | Public/authenticated per policy | Search scholarships/funding |
| GET | `/scholarships/{scholarship_id}` | Public/authenticated per policy | Scholarship details and evidence |
| POST | `/scholarships/matches` | Student | Match opportunities against profile/program |
| GET | `/funding-opportunities` | Public/authenticated per policy | Search grants, awards and funding schemes |
| GET | `/funding-opportunities/{opportunity_id}` | Public/authenticated per policy | Funding details |
| POST | `/loan-scenarios` | Student | Calculate and optionally persist a loan scenario |
| GET | `/loan-scenarios` | Student | List own scenarios |
| GET | `/loan-scenarios/{scenario_id}` | Owner only | Retrieve scenario |
| DELETE | `/loan-scenarios/{scenario_id}` | Owner only | Delete scenario |

Cost model must distinguish:
- tuition and mandatory academic fees
- living costs and their period
- health insurance
- visa/application/travel/setup costs where data exists
- deposits and contingent costs where relevant
- currency and conversion date/rate source
- low/base/high scenario assumptions
- verified published facts vs estimates vs user-entered assumptions
- funding amount and funding gap

Loan calculations must return inputs, assumptions, interest method, repayment period, grace/moratorium handling if modelled, EMI/payment schedule and disclaimer. Never imply loan approval or provide personalized regulated financial advice.

### 5.8 Career, ROI and destination information
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/outcomes` | Public/authenticated per policy | Search scoped outcome evidence |
| POST | `/roi-scenarios` | Student | Calculate scenario-based ROI/payback |
| GET | `/roi-scenarios` | Student | List own saved scenarios |
| GET | `/roi-scenarios/{scenario_id}` | Owner only | Retrieve scenario |
| DELETE | `/roi-scenarios/{scenario_id}` | Owner only | Delete scenario |
| GET | `/destinations/countries` | Public | Supported country list |
| GET | `/destinations/countries/{country_code}` | Public | Country context and official rule references |
| GET | `/destinations/countries/{country_code}/cities` | Public | City catalogue |
| GET | `/destinations/cities/{city_id}` | Public | City living-cost/housing context |
| GET | `/destinations/rules` | Public | Official visa/work/study rule resource index |

ROI must disclose scope (program/institution/subject/country), cohort/year, metric definition, sample size if available, currency, source, assumptions and uncertainty. It is a scenario, not a promise. Country rules must link to official sources and display checked/effective dates.

### 5.9 Reviews
If user reviews are in the release:
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/programs/{program_id}/reviews` | Public | List approved reviews |
| POST | `/programs/{program_id}/reviews` | Authenticated student | Submit review |
| PATCH | `/reviews/{review_id}` | Owner or moderator per policy | Edit/moderate review |
| DELETE | `/reviews/{review_id}` | Owner/moderator per policy | Remove review |

Reviews require moderation, anti-abuse controls, privacy-safe display and clear separation from official university facts. Do not fabricate reviews.

### 5.10 Admin/researcher data review and sources
| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/admin/review-queue` | Reviewer/admin | List candidate facts needing review |
| GET | `/admin/facts/{fact_id}` | Reviewer/admin | Inspect fact, evidence and history |
| POST | `/admin/facts/{fact_id}/approve` | Reviewer/admin | Approve/publish with audit event |
| POST | `/admin/facts/{fact_id}/reject` | Reviewer/admin | Reject with reason |
| POST | `/admin/facts/{fact_id}/request-evidence` | Reviewer/admin | Request more evidence |
| GET | `/admin/sources` | Reviewer/admin | List source registry |
| POST | `/admin/sources` | Admin | Register source |
| GET | `/admin/sources/{source_id}` | Reviewer/admin | Source detail |
| PATCH | `/admin/sources/{source_id}` | Admin | Update source metadata/policy |
| POST | `/admin/sources/{source_id}/refresh` | Admin | Enqueue permitted refresh |
| GET | `/admin/jobs` | Admin | List ingestion/refresh jobs |
| GET | `/admin/jobs/{job_id}` | Admin | Job detail/log summary |
| POST | `/admin/jobs/{job_id}/retry` | Admin | Retry safe failed job |
| GET | `/admin/audit-events` | Admin | Filter audit history |

No candidate extraction may automatically publish a critical fact unless an explicit, tested policy permits it. Source-use policy, robots/terms/licensing, rate limits and access restrictions must be respected. Avoid displaying secrets, raw sensitive documents or full private payloads in logs.

## 6. Canonical request/response shapes
These are contract patterns; specific Pydantic models should be typed and documented in OpenAPI.

### 6.1 Program summary
```json
{
  "id": "uuid",
  "university": {
    "id": "uuid",
    "name": "Example University",
    "country_code": "DE",
    "city": "Example City"
  },
  "name": "MSc Example Subject",
  "degree_level": "masters",
  "field": "artificial_intelligence",
  "duration_months": 24,
  "language": "en",
  "intakes": [],
  "tuition_summary": null,
  "data_quality": {
    "status": "partial",
    "last_verified_at": null,
    "warnings": ["tuition_not_verified"]
  }
}
```
Illustrative demo object only. Do not seed it as real official information.

### 6.2 Fact status enums
Use a documented set and map any internal statuses to it consistently:
- `verified`
- `estimated`
- `user_provided`
- `unverified`
- `stale`
- `conflicted`
- `unavailable`
- `superseded`

If the project needs a separate review lifecycle (`candidate`, `in_review`, `approved`, `rejected`), keep it separate from factual confidence/freshness.

### 6.3 Cost amount
```json
{
  "amount": 15000,
  "currency": "EUR",
  "period": "academic_year",
  "academic_year": "2026-2027",
  "status": "verified",
  "source_evidence_id": "uuid"
}
```
Never compare amounts without normalizing currency and period; preserve original amount/currency.

## 7. Validation and domain rules
- Grade values must be paired with grading scale/system; never infer a universal CGPA-to-percentage conversion.
- Budget must specify currency and basis (annual vs full degree; tuition-only vs all-in).
- Country list must be valid codes; degree/field/test status should use controlled values with an extension path.
- Intake/deadline facts must have applicability year/term and source.
- Costs must preserve original currency and period and indicate conversion assumptions when converted.
- Requirement rules must support AND/OR groups, minimum thresholds, required tests, course prerequisites and conditional/missing evidence.
- Eligibility result for a mandatory unknown requirement cannot be `eligible`.
- Scoring weights and rule versions must be persisted with recommendation runs.
- Program details and comparisons must not silently substitute missing values with zero or generic assumptions.
- Admin approve/reject actions must record actor, timestamp, reason and evidence/version.
- Ingestion jobs must be idempotent, bounded in retries and safe to re-run.

## 8. Idempotency, concurrency and long-running jobs
- `POST` requests that create expensive recommendation/cost/ingestion work should support an idempotency key or equivalent duplicate-submit protection where appropriate.
- Use a stable request ID/correlation ID across API logs and worker jobs.
- Return `202 Accepted` plus job/resource ID for work that is genuinely asynchronous; provide a status endpoint.
- Use optimistic concurrency/version fields for editing high-impact facts or source configurations if concurrent editing is possible.
- Retrying a job must not duplicate universities, programs, evidence or audit events incorrectly.

## 9. Security and privacy requirements
- Password hashing via a vetted library if local passwords are used; never store plaintext passwords.
- Restrict CORS; validate inputs; use parameterized ORM queries; rate-limit authentication and expensive endpoints.
- Do not log passwords, tokens, full transcripts, resumes, or sensitive personal data.
- Upload support (if enabled) requires type/size validation, private storage, malware scanning and short-lived access links.
- Students may access only their own profile, runs, saved programs, comparisons and scenarios.
- Reviewer/admin access is role-controlled and audited.
- Provide deletion/export flows if implemented, with retention and legal constraints documented.
- Keep credentials in environment/secrets management, never in frontend bundles or Git.

## 10. Testing and acceptance
Required API tests:
- Authentication success/failure/rate limiting and session invalidation.
- Cross-user authorization denial for every private resource.
- Request validation, enum/nullability, pagination and sort allowlists.
- Program search filters and deterministic pagination.
- Requirement rule operators and all eligibility states.
- Same profile + same active rules/data version produces reproducible recommendation results.
- Costs reconcile to line items and preserve currency/period.
- Loan amortization and ROI scenario formulas have unit tests.
- Provenance included for critical facts or explicitly marked unavailable/estimated.
- Admin publication/rejection requires authorization and records audit history.
- Ingestion is idempotent and failed source parsing does not publish invented values.
- OpenAPI schema and frontend TypeScript types match.
- Integration tests run against a disposable test database, not a developer's production data.

## 11. Implementation checklist
1. Confirm any repository conventions and finalize auth mechanism.
2. Define Pydantic schemas before or alongside endpoints.
3. Create/update SQLAlchemy models and Alembic migrations.
4. Implement repository and domain-service layers; keep routers thin.
5. Add endpoint tests and OpenAPI examples.
6. Connect Vue typed API client and handle loading/empty/error states.
7. Update this document whenever a contract changes.
8. Use a shared Git branch/PR review; do not merge unreviewed contract-breaking changes.
