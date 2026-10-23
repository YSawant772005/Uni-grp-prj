# University Shortlisting Tool — UI Flow and Routes
**Version:** 1.0  
**Status:** Implementation baseline derived from the project implementation and architecture plans.  
**Audience:** Product coordinator, frontend, backend, database, QA, and AI coding agents.

## 1. Purpose and authority
This document defines the user journeys, page inventory, route conventions, navigation behavior, and screen-level states for the University Shortlisting Tool for Indian applicants considering international Master's programs.

It is the shared frontend behavior contract. It does **not** replace `API_Contract.md` or `Database_Schema.md`. If a route or interaction requires server data, the corresponding API must be defined in the API contract. Do not silently invent endpoint names, response fields, or database fields during implementation.

### 1.1 Product principles
- The product is an evidence-first decision-support tool, not merely a university directory.
- Keep the primary profile journey short: an 8-question quick profile, with optional advanced details available later.
- Distinguish eligibility, admission likelihood, and overall fit. They are not interchangeable.
- Use explainable portfolio labels: **Ambitious**, **Target**, and **Safer-fit**. Never imply guaranteed admission.
- Show source, applicable intake/year, verification state, and last-verified date for critical facts.
- Unknown or missing data must remain visible as unknown/unavailable; do not turn it into a confident claim.
- Keep user profile and saved work private to the authenticated user.
- Every data-driven screen needs loading, empty, error, stale-data, and partial-data states as appropriate.
- The backend is authoritative for eligibility, recommendations, costs, and financial calculations. Frontend-only calculations are presentation previews, never authoritative decisions.

## 2. Actors and permissions
| Actor | Purpose | Access |
|---|---|---|
| Visitor | Understand product and start signup | Public landing, public help/policy pages if implemented, registration/login |
| Student | Build profile, discover programs, shortlist, compare, estimate costs and outcomes | Own profile, own recommendation runs, saved programs, comparisons and scenarios |
| Researcher/reviewer | Review candidate facts and conflicting sources | Authorized review queue and evidence; no student private data unless explicitly needed and authorized |
| Administrator | Manage source registry, jobs, reviewer access and operational controls | Admin functions according to role permissions |
| Worker/service identity | Import, normalize, check and refresh source data | Narrow machine permissions; no interactive user session |

## 3. Global information architecture
### 3.1 Primary student navigation
- Discover programs
- My shortlist / recommendation runs
- Saved programs
- Compare
- Finance
- Scholarships and funding
- Career and ROI
- Destination guide
- Profile/settings

Navigation may adapt for small screens, but the same core destinations and authorization rules must remain.

### 3.2 Admin/research navigation
- Data review queue
- Institution identity review
- Sources registry
- Ingestion/refresh jobs
- Fact and source history
- Audit events / operational status (restricted)

Admin navigation must never be shown as an authorization mechanism by itself. Every protected route must also be protected by backend authorization.

## 4. Route conventions
- Use Vue Router with history mode and a centralized route table.
- Use kebab-case paths and stable IDs in path segments.
- Routes are frontend routes, not API endpoints.
- Use query parameters for shareable search/filter state; do not put sensitive personal information in URLs.
- Never put access tokens, private transcript data, or secrets in route parameters.
- Unknown routes render a Not Found page. Expired sessions route to login with a safe local `redirect` parameter.
- A redirect must be restricted to local application paths to prevent open-redirect vulnerabilities.
- Protected routes should preserve the intended destination after login, but should not expose private data before authorization.
- Route titles and breadcrumbs should be accessible and descriptive.

## 5. Route inventory
| Route | Access | Screen / purpose | Key actions |
|---|---|---|---|
| `/` | Public | Landing page; explain value, trust principles and supported scope | Start profile, sign up, log in |
| `/signup` | Public | Account registration | Create account, go to login |
| `/login` | Public | Sign in | Authenticate, return to requested safe route |
| `/forgot-password` | Public if password auth enabled | Request password reset | Request reset email/token flow |
| `/reset-password` | Public, time-limited token flow | Set new password | Submit new password |
| `/onboarding` | Authenticated | 8-question profile wizard; save/resume | Back/next, save draft, complete profile |
| `/profile` | Authenticated | View/edit full profile and preferences | Edit, save, resume onboarding |
| `/discover` | Public catalogue view or authenticated according to deployment policy | Program search, filters, sorting and result cards | Search, filter, sort, open details, save, compare |
| `/programs/:programId` | Catalogue visibility policy | Program detail, requirements, fees, intakes, evidence, outcomes | Save, compare, inspect sources |
| `/shortlist` | Authenticated | List prior recommendation runs and latest portfolio | Open run, create/re-run recommendations |
| `/shortlist/:runId` | Authenticated; owner only | Recommendation portfolio and explanations | Filter tiers, inspect reasons, save, compare |
| `/compare` | Authenticated for saved comparison; temporary compare may be public | Side-by-side program comparison | Add/remove items, change comparison set |
| `/saved` | Authenticated | Saved programs and user-created collections if supported | Open, remove, compare |
| `/finance` | Authenticated | Full-degree cost model and low/base/high scenarios | Adjust assumptions, save scenario |
| `/scholarships` | Catalogue view; personalized matching requires auth | Scholarships and funding opportunities | Filter, inspect eligibility, save, open official source |
| `/loans` | Authenticated | User-controlled loan assumptions and EMI scenario | Edit assumptions, recalculate, save scenario |
| `/roi` | Authenticated for saved scenarios; read-only educational view may be public | Career evidence, employment assumptions and ROI scenarios | Adjust assumptions, compare scenarios |
| `/destinations/:countryCode` | Catalogue view | Country guide, official visa/work-rule resources and context | Explore cities, inspect sources |
| `/destinations/:countryCode/:citySlug` | Catalogue view | City living-cost, housing and student-life information | Adjust living assumptions, compare cities |
| `/settings` | Authenticated | Account preferences, privacy and notification settings | Update settings, request deletion/export if implemented |
| `/admin` | Admin/reviewer only | Admin overview | Navigate to review, sources and jobs |
| `/admin/review` | Reviewer/admin only | Candidate facts awaiting review | Inspect evidence, approve/reject/request changes |
| `/admin/review/:factId` | Reviewer/admin only | Fact detail, conflicts, source history | Verify, reject with reason, record correction |
| `/admin/identity-reviews` | Reviewer/admin only | Ambiguous source institution candidates and source evidence | Approve a source identifier link to an existing institution, reject, or defer with reason; no physical merge |
| `/admin/sources` | Admin/reviewer according to policy | Source registry and source-use policy | Add/edit source, disable source, inspect policy |
| `/admin/sources/:sourceId` | Admin/reviewer according to policy | Source details and field coverage | Edit metadata, test URL, review ingestion history |
| `/admin/jobs` | Admin only | Ingestion and refresh job history | Inspect/retry/cancel where safe |
| `/admin/audit` | Admin only | Audit log | Filter and inspect authorized events |
| `/privacy` | Public | Privacy explanation | Read policy |
| `/terms` | Public | Terms and limitations | Read terms |
| `/:pathMatch(.*)*` | Public | Not Found | Return home/discover |

**Implementation note:** Password reset, privacy export/deletion, user collections, notification settings and temporary public compare are route recommendations. If not included in the first release, hide them rather than shipping inert links.

## 6. Core user journeys
### 6.1 First-time applicant
1. Visitor opens `/`.
2. Selects “Get my shortlist” and signs up at `/signup`.
3. After successful registration, app sends user to `/onboarding`.
4. Wizard asks eight quick questions:
   1. Intended degree/level (Master's; specific degree type if relevant).
   2. Intended field/specialization.
   3. Preferred destination countries.
   4. Academic background (degree, institution, grade and grading scale; detail can be expanded).
   5. Graduation year/status.
   6. English-test status (not taken / booked / completed; scores if available).
   7. Total budget and currency/period basis.
   8. Intended intake (year and term).
5. User can go back, see validation errors, save draft, and resume later.
6. On completion, app persists profile and offers “Generate shortlist”.
7. User sees a recommendation run with Ambitious, Target and Safer-fit groups, eligibility states, fit reasons, concerns, cost summaries and evidence freshness.
8. User opens a program detail page, reviews source evidence, saves programs and compares selected options.
9. User explores finance, scholarships, destination information and career/ROI evidence.
10. User returns to `/shortlist` or `/saved` later.

### 6.2 Returning applicant
1. Login.
2. Land on latest shortlist/dashboard destination or requested safe redirect.
3. Show profile completeness, latest run date, stale critical data warnings, saved programs and next useful actions.
4. Allow user to update profile and explicitly regenerate a recommendation run. Existing runs remain historically reproducible.

### 6.3 Discover without a profile
1. Open `/discover`.
2. Search by program, university, country, subject or keyword.
3. Apply filters and sort.
4. Open `/programs/:programId`.
5. Prompt for login only when an action requires personal persistence, such as saving a program or storing a scenario.

### 6.4 Compare options
1. User selects two or more programs, within the configured maximum.
2. Compare tray displays selected count and provides remove/clear actions.
3. `/compare` shows aligned columns for program, location, duration, admission requirements, tuition, living cost, total cost, funding evidence, career metrics and data confidence.
4. Missing/incomparable values are labelled; do not display zero as a substitute for unknown.
5. User may save comparison if authenticated.

### 6.5 Finance and funding
1. User opens `/finance` from a program or shortlist.
2. Show cost components separately: tuition, mandatory fees, living expenses, insurance, travel/visa, deposits, one-time setup and contingency where applicable.
3. Show currency, cost period, academic year/intake, source/estimate status and assumptions.
4. Offer low/base/high scenarios; distinguish published facts from estimates and user-entered assumptions.
5. Link matching scholarships and funding options to `/scholarships`.
6. Optional loan scenario at `/loans` is illustrative and not financial advice. Approval and terms are not guaranteed.

### 6.6 Career and ROI
1. User opens `/roi`.
2. Show evidence scope clearly: exact program, institution, subject, country or broad benchmark.
3. Display cohort, year, metric definition, currency, source and sample size when available.
4. Allow adjustable scenarios for employment delay, salary, taxes/expenses if supported, loan repayment and discount assumptions.
5. Never imply guaranteed employment, salary or payback.

### 6.7 Researcher verification
1. Authorized reviewer opens `/admin/review`.
2. Filters candidate facts by country, entity, field, source, confidence, age and conflict status.
3. Opens `/admin/review/:factId` to inspect proposed value, original source, excerpt/evidence, retrieval time, applicable intake/year, conflicting evidence and prior versions.
4. Reviewer approves, rejects with a reason, or requests more evidence.
5. Approval publishes a versioned fact and records reviewer, time, reason and source evidence.
6. Changed critical facts may mark affected recommendation/cost data stale and trigger recalculation/review according to policy.

### 6.8 Source refresh
1. Admin opens `/admin/sources` or `/admin/jobs`.
2. Inspects enabled sources, usage policy, last successful run, failure rate and freshness policy.
3. Starts or inspects a permitted ingestion/refresh job.
4. Worker retrieves only permitted sources, records retrieval metadata and creates candidate changes.
5. Changed facts go through validation/review; scraping/extraction does not automatically publish unverified facts.
6. Job status, retries, parse failures and change history remain auditable.

## 7. Screen behavior requirements
### 7.1 Landing
- Explain the tool in plain language and show core value propositions: fit, affordability, funding, outcomes and evidence.
- Avoid guaranteed outcomes and fabricated sample statistics.
- Calls to action: start profile, explore programs, login.
- Include scope/limitations and privacy links.

### 7.2 Signup/login
- Inline validation and accessible error summary.
- Do not reveal whether an arbitrary email exists in ways that enable account enumeration.
- Disable duplicate submission while a request is in progress.
- Never log passwords, tokens or full authentication payloads.
- Use backend-defined session/cookie/token behavior.

### 7.3 Onboarding wizard
- Display step number, progress, required/optional status and concise help.
- Validate on step transition and server submission.
- Preserve draft across refresh if backend supports it.
- Store grade and grading scale explicitly; do not assume CGPA and percentage are directly interchangeable.
- Store budget amount, currency, time basis and included cost components.
- Allow multiple destination countries and a clear preference order if ranking is supported.
- Test status is not the same as a test score; distinguish not taken, booked, completed, waived/unknown as supported.
- Show confirmation before generating recommendations.

### 7.4 Discovery/results
- Search input supports debounce, submit/clear, loading and no-result states.
- Filters should be reflected in query parameters where safe and shareable.
- Pagination must be server-driven. Show current page/total when known; do not download the full catalogue to paginate locally.
- Sorting must be explicit and deterministic; show active sort.
- Each card should show program/university, location, degree/field, duration, tuition/cost context, intake if known, eligibility only when profile-based evaluation exists, freshness indicator and save/compare controls.
- Distinguish missing tuition from free tuition.
- Do not label an item “eligible” from catalogue data alone without evaluating the user's profile and the relevant requirements.

### 7.5 Program detail
Suggested sections/tabs:
- Overview
- Admission requirements and prerequisites
- Tuition and other fees
- Intakes/deadlines
- Scholarships/funding
- Career/outcomes
- University/program quality and recognition evidence
- Destination/living context
- Student reviews (only when moderated and policy-compliant)
- Sources and data history

Each material fact should link to evidence/source details. Show source date, applicable intake/year, verification state, and whether value is official, estimated, user-provided or unavailable.

### 7.6 Shortlist and explanations
- Present tier groups with a description of what the tier means.
- Explain hard-filter exclusions as well as recommendations.
- Separate requirement-level eligibility from fit score and from admission likelihood.
- Show fit dimensions and weighted breakdown if scoring is configured.
- Show missing information that could change the outcome.
- Show the rules/scoring version and run timestamp.
- Re-running creates a new run; do not silently overwrite historical run results.

### 7.7 Comparison
- Align the same attributes across programs.
- Make cost basis and currency conversions visible.
- Display “unknown”, “not published” or “not comparable” as appropriate.
- Provide source drill-down for important facts.
- Enforce a configurable comparison limit and explain the limit in UI.

### 7.8 Admin screens
- Distinguish candidate, reviewed, published, rejected, stale, conflicted and superseded states.
- Require reason for rejecting or overriding a critical fact.
- Show before/after value and evidence.
- Confirm destructive or high-impact actions.
- Admin pages must not rely on frontend hiding alone for security.

## 8. Loading, empty, error and freshness states
Every data-dependent view must implement:
- Initial loading/skeleton.
- Empty state with an actionable next step.
- Validation errors near relevant fields and an accessible summary.
- API/network error with retry where safe.
- Session-expired behavior.
- Partial result state when some fields are unavailable.
- Stale-data warning for critical facts.
- “Not available” rather than a fabricated value.
- Safe cancellation/navigation behavior for long-running jobs.
- Duplicate-submit protection for mutation requests.

## 9. Responsive and accessibility requirements
- Support desktop and mobile-width layouts; tables such as comparison must remain usable via responsive stacking or controlled horizontal scroll.
- Keyboard navigation, visible focus, semantic headings, form labels and accessible names for icon-only controls.
- Status must not be communicated only by color.
- Use understandable copy and define terms like “Safer-fit”, “unknown”, “estimated”, and “verified”.
- Respect reduced-motion preferences.
- Charts must have textual summaries or accessible tabular alternatives.

## 10. Route guards and authorization
- Public: landing, signup/login, public catalogue pages as deployment policy allows, terms/privacy.
- Authenticated student: profile, onboarding persistence, shortlist runs, saved items, private comparisons, finance/loan/ROI saved scenarios, settings.
- Reviewer/admin: review queue and source operations according to explicit role.
- Admin-only: high-impact source configuration, operational controls, audit access as policy specifies.
- Backend authorization is mandatory for every private record and mutation.
- Do not trust user IDs or role claims supplied in request bodies.
- If a user requests deletion/export, verify identity and follow documented retention/deletion policy.

## 11. Frontend module boundaries
Suggested Vue project structure:
```text
frontend/
  src/
    app/
    router/
    layouts/
    features/
      auth/
      onboarding/
      profile/
      discovery/
      program-detail/
      shortlist/
      comparison/
      finance/
      scholarships/
      loans/
      roi/
      destinations/
      saved/
      admin-review/
      admin-sources/
    components/
    services/api/
    stores/
    composables/
    types/
    tests/
```
- Use Vue 3, TypeScript and Vite as the agreed stack.
- Typed API client belongs in `services/api`; UI components must not invent backend behavior.
- Keep authoritative eligibility, ranking, costs, loan math and ROI math on the backend.
- Use shared types generated from or kept consistent with OpenAPI where practical.
- Centralize API error handling, authentication/session behavior and route metadata.

## 12. Definition of done for UI flow
- All shipped navigation items point to implemented routes.
- Every route has documented access policy.
- Every data-driven view has loading, empty, error and partial-data states.
- Search/filter/sort/pagination state is predictable and testable.
- Critical facts show provenance and uncertainty.
- Private screens cannot be accessed by unauthenticated users, and private data is enforced by backend ownership checks.
- Main end-to-end path works: signup/login → profile → discovery/shortlist → detail/evidence → compare → save/reopen.
- Admin path works: review candidate fact → publish/reject with reason → inspect history.
- No screen implies guaranteed admission, scholarship, visa, job, salary or ROI.
