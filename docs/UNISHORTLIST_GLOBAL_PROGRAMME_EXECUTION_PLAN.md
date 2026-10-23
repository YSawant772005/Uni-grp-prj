# UniShortlist — global Master's programme continuation plan

Documentation-only checkpoint: **2026-10-22, 08:20 UTC / 13:50 IST**. This is a reconstruction and continuation plan, not authorization to execute imports, migrations, reviews or deployments.

## 1. Requirement provenance and limits

The exact teammate document titled **“UNISHORTLIST — MASTER EXECUTION PROMPT: GLOBAL MASTER'S PROGRAM DATA POPULATION”** was not found in the inspected repository Markdown or the three existing architecture/implementation DOCX specifications, and is not supplied verbatim in the available conversation. Its complete wording is **UNKNOWN — previous execution context not recoverable**. Do not present this file as its verbatim replacement.

This plan maps the ten client goals explicitly supplied in the documentation request, the preceding visible **“Deadline Priority: Populate Real International Master's Programmes”** task, actual repository functionality, persisted data and saved execution evidence. Obtain the original prompt from the client/teammate if finer acceptance conditions are required. No unsupported completion percentage is assigned.

Core success is genuine individual Master's offerings with defensible identity, provenance and honest applicability. Institution-directory volume alone does not meet that success metric. Automatic approval/publication is never a substitute for review.

Read [interrupted recovery](UNISHORTLIST_INTERRUPTED_WORK_RECOVERY.md) first; [complete handover](UNISHORTLIST_COMPLETE_PROJECT_HANDOVER.md) and [source matrix](UNISHORTLIST_SOURCE_COVERAGE_MATRIX.md) provide implementation and rights detail.

## 2. Starting state, not a target projection

| Layer | Actual development | Actual isolated rehearsal |
| --- | --- | --- |
| Reference directory | 30,328 ROR v2.15 rows / 223 country-territory codes, deployed | Same preserved |
| Canonical institutions | One approved UAL | 150 total: one approved, 149 pending |
| Master's offerings | Five UAL | 9,349: ES 5, NL 1,501, FR 7,843 |
| Official pages verified | Five | Five (original UAL) |
| Published | One | One (original UAL) |
| Candidate offerings | Four | 9,348 |
| Programme academic facts | Missing tuition/admissions/deadlines/duration for all five | Same gaps for all 9,349 |
| Historical records | Archived catalogue preserved; no active French offerings | 7,843 historical French 2025 offerings |
| Protected history | 1,479 archive rows, existing reviews/users/description intact | Preserved by saved original-row fingerprint verification |

**No additional development programme import has been authorized.** The proposed 9,344-addition operation and API performance-code deployment remain pending. No migration is required for the selected pipeline. Scheduler stays disabled.

## 3. Client requirement-by-requirement matrix

Completion refers to the entire stated requirement, not a small happy-path implementation. “TESTED” below refers to saved executions; final queue edits need rerun. Codes: P0 deadline-critical, P1 next controlled expansion, P2 later breadth/optimization.

| Requirement ID | Client requirement | Existing implementation | Actual data present | Tests | Deployment status | Completion status | Remaining work | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C01 | Audit existing system | Evidence/review architecture, guarded DBs, current handover | Actual dev/recovery baselines separated | Historical 452 baseline; 465 before last edit; read-only checkpoint | Core, UAL and directory deployed | COMPLETED | Reinspect drift on resume | P0 |
| C02 | Find legitimate high-volume programme sources | DUO/Mon Master adapters and frozen official metadata | NL 1,501 + FR 7,843 in recovery only | Bounded acquisition, samples, dry runs, actual isolated import | New wrapper not deployed | PARTIALLY COMPLETED | Extend beyond NL/FR/UAL with rights checks | P0/P1 |
| C03 | Unified programme model | Programmes, stable scoped IDs, facts, periods, projection | Five active UAL; 9,344 isolated additions | Identity/ownership/level/hold tests; schema head 9c | Existing model deployed | PARTIALLY COMPLETED | Joint/consortium qualification, awarding/offering relationships | P1 |
| C04 | Bulk structured programme ingestion | Frozen replay, exact plans, permission/identity holds, atomic apply | 9,344 actual additions and zero-addition replay in isolation | 100/500 fixtures, real recovery, rollback/idempotency; **final full 470-pass certification done** | Tool not deployed; no dev apply | TESTED BUT NOT DEPLOYED | Plan/backup freshness reverified; needs approval and execution | P0 |
| C05 | Discover official individual programme pages | UAL catalogue mapping, robots/redirect/title/plan checks; generic adapter | Five UAL verified pages; none verified for new NL/FR offerings | Mismatch/generic/redirect/robots/template/provenance tests | UAL deployed; global discovery absent | PARTIALLY COMPLETED | Source-backed mappings per new source/provider | P1 |
| C06 | Evidence-backed academic enrichment | Typed facts, versions, review/projection; DUO detail candidates; descriptions | UAL field/mode/page/summary; essentials unknown; NL candidates isolated | Projection/conflict/unknown/description tests | Core deployed; new bulk facts not in dev | PARTIALLY COMPLETED | Applicable official fees/admissions/duration/intakes/outcomes and human verification | P1/P2 |
| C07 | Details, shortlisting and comparison integration | Catalogue/library/eligibility/recommendations/finance APIs and UI | One public UAL programme | Historical student/browser tests; current public GET; bulk candidate 404 checks | Existing student app deployed | PARTIALLY COMPLETED | Reviewed international coverage and post-import journeys | P1 |
| C08 | Actual international programme imports | UAL pilot and rehearsed Dutch/French operation | Dev: five ES; isolated additions: 1,501 NL + 7,843 FR | Genuine isolated persistence, repeat and preservation | Additional offerings not in development | BLOCKED | Explicit exact development-write approval after final validation; human review later | P0 |
| C09 | Quantitative coverage reporting | New read-only programme report, directory stats, job metrics | Real counts for both DBs documented | Actual reports and direct SQL rechecked | Directory stats deployed; new report local | PARTIALLY COMPLETED | Post-import report if authorized; preserve period/offering distinctions | P0 |
| C10 | Global country/source strategy | Source matrix and confirmed coverage/gaps | References in 223 codes; active programmes ES only; recovery ES/NL/FR | Existing connector tests; other countries not validated | No worldwide programme catalogue deployed | PARTIALLY COMPLETED | Assess official programme source rights/formats country by country | P1 |
| S01 | Preserve pilot/history/users and honest unknowns | Original-row fingerprints, archive context and null semantics | UAL UUIDs, description, one publication and 1,479 archives intact | Saved 54-table verification; current SQL/public GET | Existing controls deployed | COMPLETED | Recheck after any authorized operation | P0 |
| S02 | Independent human approval/publication | Role-guarded identity, institution, fact and programme decisions | One approved UAL, one publication unchanged | Review/publication boundary tests; candidates 404 | Core deployed | COMPLETED | Preserve gates for every new source | P0 |
| S03 | Refresh/currentness/retry reliability | Retrieval history, backoff/cache/conflicts, manual limits | Real source versions; FR historical; DUO validity | Prior freshness/retry tests; frozen replay | Scheduler disabled; manual core deployed | PARTIALLY COMPLETED | Source-specific tested schedules, health and operational approval | P2 |
| S04 | Final latest-code certification | Last queue optimization and query-count assertions written | Real recovery queue correct at 1.908 seconds | Full **470-pass** run on the final file state; queue pagination/query-count regressions executed | Not deployed | **COMPLETED** | Awaiting development import/deployment approval | P0 |

No original text supporting a separate additional requirement is invented. Most broad goals are partial because authentic source coverage and human review remain limited even where the software mechanisms exist.

## 4. Interrupted task acceptance criteria and present result

| Phase | Required result | Actual result / remaining gate |
| --- | --- | --- |
| A: Inspect connectors | Rights/access/period/stable IDs and identity requirements | Done for DUO/Mon Master/UAL; official metadata and samples saved. Other placeholders are not immediately importable. |
| B: Select highest-value sources | Maximum defensible distinct offerings with honest applicability | NL 1,501 and FR 7,843 selected after holds; remaining 30 UAL plans outside this operation. |
| C: Isolated scale | Representative inspection, dry runs, identity/deduplication, import/replay, no publication | Actual 9,344 addition succeeded; 100/500 fixtures and 100-record dry runs; final queue regressions pending. |
| D: Exact development request | Counts/version/table impact/identity prerequisites/period/backup/commands; explicit approval | Plan and rehearsal exist. Request not submitted; no development programme writes. |
| E: Coverage | PostgreSQL counts by source/country/status/missing fields/conflicts | Reports show development five and recovery 9,349; headline counts independently reconfirmed. |

Do not reclassify source-selected “accepted programme identity” as a human-approved institution. Dutch provider/reporting-unit IDs and French UAI claims can establish exact source ownership while authoritative institution/package/website approval remains pending.

## 5. Milestones and dependencies

Relative effort is small/medium/large. It excludes unknown human review throughput and licensing delays; no delivery date is promised.

### Milestone A — confirm and stabilize interrupted work

- **Objective:** certify the exact final workspace, not an earlier passing version.
- **Starting state:** import wrapper and source fixes tested; actual 9,344-offering recovery dataset; final queue code and assertions postdate the full suite.
- **Tasks:** read recovery file; inspect final `admin.institution_review_queue`, batched evidence and tests; verify snapshots/backup/plan hashes and actual dev/recovery counts; run final targeted tests then full marked backend suite; confirm no source-policy or API-shape regression. Frontend unchanged; rerun existing 41 tests if any response-sensitive change is required.
- **Files:** `services/{admin,catalog,program_evidence}.py`, `tests/test_program_import.py`, source adapters/pipeline and frozen manifests.
- **Dependencies:** intact private isolated test configuration; source-mounted current code; no new external crawl needed.
- **Permissions:** implementation must be resumed by user; no dev writes or deployment. Isolated tests must pass database target guards.
- **Tests:** query counts, stage pagination, 100/500 and replay, unexpected-failure atomic rollback, archive holds, source policy and full suite; distinguish seven live opt-ins.
- **Deployment:** none for validation. Existing API remains old image until specifically approved.
- **Acceptance:** current-source passing logs, no automatic approvals/publication, unchanged pilot/archive; resolved failures without weakening tests.
- **Effort/deliverables:** small–medium; final regression record, corrected plan if necessary, concise readiness report.

### Milestone B — import legitimate Master's datasets

- **Objective:** add the largest validated append-only candidate set using existing official sources.
- **Starting state:** NL 1,501 / 41 providers and FR 7,843 / 108 institutions fully rehearsed; development unchanged.
- **Tasks:** recheck saved rights, version and metadata, exact selections and holds; fresh backup if baseline changed; update/rehearse plan under current code; document expected table growth; prepare exact operation and rollback boundary; obtain approval; apply only approved source snapshots; compare original fingerprints; generate post-import SQL report.
- **Files:** `ingestion/program_import.py`, `program_coverage.py`, `persist.py`, `pipeline.py`, `adapters/{duo_rio,monmaster}.py`, local snapshot/plan/backup paths in recovery document.
- **Dependencies:** A; correct provider identity scope, source policy, valid backup and human approval.
- **Permissions:** **explicit bounded development write approval**. No migration required. API deployment requires its own explicit authorization; earlier ROR approval cannot be reused.
- **Tests:** deterministic parsing, idempotency and atomic rollback plus real isolated selection; post-apply SQL/public API preservation and current review-queue performance.
- **Deployment:** source-mounted db-admin one-off can execute approved frozen plan without rebuilding main API. Deploy read-performance code only if approved; frontend unchanged.
- **Acceptance:** exact approved count (9,344 or newly replanned); zero original-row changes; 149 pending institutions; no extra public programmes; French historical 2025 labels and all failures/holds reported.
- **Effort/deliverables:** medium; approved operation, execution log/job IDs, real coverage report. The remaining 30 UAL plans need a separate bounded plan and approval.

### Milestone C — expand country/source coverage

- **Objective:** grow genuine programme evidence beyond Spain/Netherlands/historical France.
- **Starting state:** source matrix names implemented sources and explicit unsupported gaps. ROR does not supply programmes; IPEDS HD/IC/CIP do not supply individual named Master's pages.
- **Tasks:** prioritize current, machine-readable, officially licensed programme registries; assess Studyinfo/Konfo, RUCT/QEDU, CRICOS or Erasmus only after rights/access evidence; record schema/period/owner/identifier mappings; implement bounded adapter only when materially useful; deterministic fixtures; isolated import and exact approval per source.
- **Files:** `registry.py`, `adapters/`, `types.py`, `validate.py`, source tests; matrix.
- **Dependencies:** B operational validation, source rights, authoritative identity and joint-relationship scope.
- **Permissions:** licences/credentials where needed, explicit development imports, any migration/deployment. No scraping prohibited sources.
- **Tests:** native formats, periods, non-Latin names, duplicate IDs, owner conflicts, missing websites, rights restrictions, idempotency and public isolation.
- **Deployment:** additive connector/reviewer-compatible release; source-specific operational plan.
- **Acceptance:** each new country has named source-backed programme IDs, documented period/rights, actual SQL counts and no guessed fields.
- **Effort/deliverables:** large/ongoing; country priority matrix, source-specific reports and tested connectors. No invented global completion percentage.

### Milestone D — academic-data enrichment

- **Objective:** populate reliable tuition, admissions, duration, language, intake/deadline, scholarship and outcome facts under explicit applicability.
- **Starting state:** fact/evidence/projection/description workflows exist; the five pilot and all recovery offerings lack essential relational academic coverage.
- **Tasks:** source-backed programme page mappings first; permitted evidence extraction; preserve applicant category, currency, year, intake and academic stage; keep candidates until review; independently authored summaries where required; structured projection tests; no unreviewed overwrites.
- **Files:** `adapters/webpage.py`, source-specific adapters, `types.py`, `fact_projection.py`, `program_descriptions.py`, `program_quality.py`, catalogue/finance/eligibility services and tests.
- **Dependencies:** C or permitted official university APIs, correct identity/page ownership and human verification capacity.
- **Permissions:** licensed source access, exact persistent enrichment approval, explicit fact verification; migration only if truly unsupported relationship needed.
- **Tests:** templates, boilerplate, mismatched plans, unknown costs, fee periods/categories/currencies, requirement operators, deadline periods, verified-fact conflicts and description preservation.
- **Deployment:** compatible API projection changes; minimal required UI only.
- **Acceptance:** increased measured verified-field coverage with exact source/date/applicability; no duration guessed from credits, currentness inferred from validity, or invented salary/aid.
- **Effort/deliverables:** large; source-backed candidate packages, review queues, field-coverage reports.

### Milestone E — student workflow integration

- **Objective:** make reviewed international data useful in Discover/details/saved/shortlist/comparison/finance/scholarships.
- **Starting state:** deployed one-programme UAL workflow, earlier isolated browser journeys and verified candidate/public boundaries.
- **Tasks:** maintain public filters across library/recommendations/costs; test profile/eligibility unknowns; distinguish reference/source/academic coverage; check scholarship links without implied eligibility; run authenticated admin/student journeys after authorized publication.
- **Files:** `catalog.py`, `library.py`, `eligibility.py`, `recommendations.py`, `costs.py`, `funding.py`, existingVuefeaturepages/APItypes.
- **Dependencies:** B data, reviewed D facts and independent human institution/programme decisions.
- **Permissions:** publication only via human review; isolated browser accounts with real roles; no automatic student-data enrichment.
- **Tests:**401/403/404 boundaries, candidate exclusion from saved/compare, known/unknown rendering, JSON compatibility and frontend tests/typecheck/lint/build.
- **Deployment:** only compatible backend and necessary minimal frontend changes after approval.
- **Acceptance:** a genuinely published international programme journey with accurate evidence and unknowns; no frontend redesign.
- **Effort/deliverables:** medium; authenticated journey evidence and client demonstration script.

### Milestone F — scale, performance and quality assurance

- **Objective:** predictable imports, recovery, review and search at larger volumes.
- **Starting state:** directory 30,328 checkpointed/replayed; programme 9,344 atomic rehearsal; final review queue 1.908 seconds locally.
- **Tasks:** finish final queue assertions; profile large providers/publication queue; measure memory, WAL, transaction duration and query plans; test interruption/retry/rollback/replay; decide whether programme checkpoints are needed; monitor staleness/health; prepare tested schedules but keep them disabled pending approval.
- **Files:** `pipeline.py`, `program_import.py`, `ror_directory.py`, `admin.py`, `catalog.py`, `program_evidence.py`, `core/scheduler.py`, load/regressiontests.
- **Dependencies:** A/B, representative isolated data and operational review.
- **Permissions:** any new database index/migration or deployment needs approval; scheduling requires separate approval; no destructive development load tests.
- **Tests:**100/500 fixtures, actual bounded imports, replay, forced failure, identity ambiguity, pagination/search, query counts, stale/conflict history and source policy.
- **Deployment:** only justified optimizations; staged isolated rehearsal first.
- **Acceptance:** documented bounded resource use, no lost history/duplicates, honest partial-job meanings and stable review/public boundaries.
- **Effort/deliverables:** medium–large; scale/recovery report, operational runbook and safe schedules.

### Milestone G — final project acceptance

- **Objective:** demonstrate actual persisted programme coverage and user workflows transparently.
- **Starting state:** directory and UAL can be demonstrated today; international additions remain isolated only.
- **Tasks:** report PostgreSQL coverage by country/source/period/status, rights and missing fields; check backup/preservation and running image/schema/readiness; demonstrate identity/fact/institution/publication decisions and student details/shortlist/compare; disclose gaps.
- **Files:** `program_coverage.py`, `services/directory.py`, status/source/recovery docs, existing API/browser tools.
- **Dependencies:** verified authorized deployments/data operations, human-reviewed records and original client prompt if available.
- **Permissions:** only approved data/review operations; no fabricated demos or automatic approvals.
- **Tests:** final current-source backend/frontend/schema/API/browser verification; separate skip reasons and unexecuted checks.
- **Deployment:** report exact service image/schema state; no inferred release claims.
- **Acceptance:** directory references, approved institutions, candidates and published programmes are distinguished; all figures are SQL-backed; demonstration shows completed workflows and coverage gaps.
- **Effort/deliverables:** medium; submission report, demonstration record and continuation backlog.

## 7. Ordered deadline-critical backlog

1. **Preserve and verify current baseline.** Read-only counts and UAL/detail/archive checks; do not repeat directory deployment/reset. Reason: a deadline gain cannot sacrifice the successful pilot.
2. ~~Certify final queue code.~~ **DONE (2026-10-22 continuation).** Targeted isolated regressions and the full backend suite were run on the final file state: **470 passed, 7 skipped**; frontend 41 passed with clean typecheck/lint/build; `alembic check` reports no new operations. No failures required fixes; no application code was changed.
3. **Finalize the exact 9,344-offering operation.** Validate plan/code/source/backup/baseline; report 149 pending institutions, French historical 2025 applicability, held identities, table growth and unchanged Discover. Reason: highest proven legal volume already rehearsed.
4. **Request explicit development write and deployment approval.** Present concrete commands/results. Reason: existing authorization covers the earlier ROR operation only.
5. **If approved, import once and independently verify.** Use selected snapshots; verify original fingerprints and SQL coverage, zero new publications and unchanged pilot. Reason: actual development programme volume is the measurable progress.
6. **Produce submission-ready coverage/demo.** Distinguish active/isolated, current/historical, reviewed/unreviewed and unknown academic facts. Reason: client progress must be accurately reported.

If approval is not granted, deliver the existing deployed pilot plus **isolated rehearsal evidence**, not a claim of 9,344 development records. No alternative unapproved write is justified by the deadline.

## 8. Ordered post-deadline backlog

1. **Provider/archive identity reconciliation and joint model:** recover held legitimate coverage without incorrect university merges.
2. **Programme-specific official page mappings for NL/FR:** enables defensible review rather than just more candidates.
3. **Current programme sources/new countries:** prioritize official structured rights/identifiers rather than unreviewed community volume.
4. **Fees/admissions/intakes/language/duration enrichment:** improve student decisions using applicable verified facts.
5. **Scholarship/outcome relationships:** only genuine programme links, populations and official methods.
6. **Human review scalability:** batch evidence packages, conflict triage, pagination/performance; no bulk autoapproval.
7. **Source monitoring/refresh:** tested cadences, health alerts, retrieval history and conflicts; scheduling requires operational approval.
8. **Programme checkpointing/search/load optimization:** only after actual resource measurements justify added complexity.
9. **Stored slug optional repair/non-Latin search and UI polish:** preserve existing URLs; lower priority than programme evidence.

## 9. Risks and acceptance boundaries

| Risk | Existing mitigation / remaining decision |
| --- | --- |
| Historical offers look current | Source documents and campaign 2025 preserved; warning/readiness restrictions; never claim open admissions. |
| Provider faculty becomes fake standalone university |23 Dutch providers held; official organisational reconciliation required. |
| Archive identity reused silently |Two French identities held; archived context cannot approve active records; explicit reconciliation required. |
| Source rights differ from webpage rights | Dataset licence is not blanket HTML prose permission; robots/access checks, short reference excerpt and independent reviewer summary. |
| Old test result treated as final release | Exact test/file timestamps recorded; final queue regressions must run. |
| Old image executes new plan incorrectly | Source mounts and current code hashes; new tool absent from running API; deployment remains separate. |
| Missing fields become invented defaults | Unknowns remain null; typed projection checks; source verification does not imply academic completeness. |
| Failed import partially changes development | Outer transaction/savepoints, exact counts and original fingerprints; post-commit restoration still requires separate approval. |
| Temporary artifacts vanish | Durable manifest/backup/plan paths documented; verify existence/hash on resume; do not rely solely on tmpfs or /tmp. |

## START HERE — NEXT CODEX SESSION

Use the ready-to-copy prompt in [interrupted recovery](UNISHORTLIST_INTERRUPTED_WORK_RECOVERY.md#start-here--next-codex-session). Begin with **Milestone A**, then finalize **B**. Do not start a new connector, repeat ROR work, fill unrelated academic fields or redesign the UI before the rehearsed programme operation is certified and presented for approval. Development bulk ingestion requires valid rights/snapshots/identity selection, current isolated tests, a verified backup/fresh plan and explicit operation authorization.

---

## EXECUTION RESULT — 2026-10-22, 09:45–10:10 UTC

Both gated operations are **executed and verified**. Full record:
[interrupted recovery §11](UNISHORTLIST_INTERRUPTED_WORK_RECOVERY.md).

| Plan item | Status now |
| --- | --- |
| C02 legitimate high-volume sources | **COMPLETED for NL/FR** — 1,501 + 7,843 imported from frozen, licence-verified official snapshots (CC BY 4.0 / Licence Ouverte v2.0) |
| C04 bulk structured ingestion | **EXECUTED** — one atomic transaction; idempotent replay adds 0 |
| S04 final certification + deployment | **COMPLETED** — 470-pass suite, then API redeploy with hash-verified code |
| Institution association | **150 canonical institutions**, 149 pending human review; 0 false merges |
| Official programme evidence | 81,599 evidence rows / 119 source documents |
| Historical vs current classification | **7,843 FR offerings labelled `academic_campaign = {"session":"2025"}`**; 1,501 NL carry official `offering_validity_period` |
| Shortlist / comparison compatibility | public Discover unchanged (`total_items: 1`); candidates 404 publicly |
| Coverage reporting | NL 1,501 / FR 7,843 / ES 5 = 9,349; **not** worldwide |

### Milestone status after execution

- **A (stabilize interrupted work):** COMPLETE.
- **B (certify and deploy):** COMPLETE — API image `9e5d86be4360…` contains the validated
  importer and review-performance code; deployed `code_hash()` equals workspace.
- **C (client-facing coverage):** NL and FR tranche complete and deployed; **the 30,328 ROR
  rows remain institution references, not programmes**, and worldwide coverage is not claimed.

### Next milestones (human work, post-import)

1. Review the **149 pending institutions** (identity, name, website) and the **9,344 candidates**.
2. Reconcile **23 Dutch held providers** and **2 French archived UAI identities** with official
   organisational / historic evidence.
3. Handle **slug disambiguation** before any French publication (504 shared slug groups).
4. Extend coverage beyond NL/FR/UAL with fresh rights checks and new frozen captures.
