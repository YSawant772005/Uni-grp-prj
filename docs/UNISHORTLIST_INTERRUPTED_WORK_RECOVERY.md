# UniShortlist — interrupted programme-ingestion recovery

Checkpoint: **2026-10-22, 08:20 UTC / 13:50 IST**. Documentation-only recovery; observations were collected starting 07:53 UTC. No implementation, ingestion, migration, review action, database write, test run or deployment was performed for this checkpoint.

## 1. Read this before doing anything

The last task was **“Deadline Priority: Populate Real International Master's Programmes”**. It requested authentic programme-level volume from existing DUO/RIO, French Mon Master and UAL connectors: inspect rights/access, capture bounded source responses, validate persistent imports in isolation, then request **explicit approval of an exact development operation**. ROR directory work was already complete and was not to be repeated.

**Development still contains five programmes.** The successful 9,344-programme addition exists **only in an isolated restored database**. No programme bulk-development import was authorized or executed. The plan checksum below is an integrity token, not permission.

The user paused implementation to preserve context. Resume only after a new instruction authorizes implementation. Never run Git commands, reset development, reapply the old archive reset, activate scheduling, infer approvals, or publish candidates automatically.

Related documents:

- [Complete technical handover](UNISHORTLIST_COMPLETE_PROJECT_HANDOVER.md)
- [Global programme execution plan](UNISHORTLIST_GLOBAL_PROGRAMME_EXECUTION_PLAN.md)
- [Source coverage and rights](UNISHORTLIST_SOURCE_COVERAGE_MATRIX.md)
- [Historical status tracker](UNIVERSITY_SHORTLISTING_PROJECT_STATUS.md)

## 2. Exact state at interruption

### Independently read from PostgreSQL during this documentation checkpoint

| Measure | Development `uni_shortlist` | Isolated `uni_shortlist_recovery` |
| --- | ---: | ---: |
| Alembic revision | `9c24a7e6d180` | `9c24a7e6d180` |
| ROR directory references | 30,328 | 30,328 |
| Canonical institutions | 1 | 150 |
| Approved / pending active institution reviews | 1 / 0 | 1 / 149 |
| Master's programme offerings | 5 | 9,349 |
| Published / candidate programmes | 1 / 4 | 1 / 9,348 |
| ES / NL / FR programmes | 5 / 0 / 0 | 5 / 1,501 / 7,843 |
| Facts / versions / evidence | 66 / 67 / 67 | 80,713 / 80,717 / 81,599 |
| Source documents | 14 | 119 |
| Archived catalogue records | 1,479 | 1,479 |

Development also has 23 ingestion jobs, 15 audit events, two users and one profile. Its directory covers 223 country/territory codes. Actual public GET requests during this checkpoint returned readiness `ready`, directory `reference_only`, Discover `total_items: 1`, and the published UAL detail with its reviewed description. All five URL facts and all five programme identities were read directly as verified and accepted respectively.

### Last completed work and last action

1. Captured immutable official DUO/RIO and Mon Master responses with rights/version metadata.
2. Implemented an exact-plan wrapper around the existing pipeline; no parallel persistence system or schema extension.
3. Rehearsed **1,501 Dutch + 7,843 historical French offerings**, creating 149 pending institutions, in a restored isolated database.
4. Repeated the import: zero new programmes, facts, versions or evidence; diagnostic job rows were appended.
5. Fixed a confirmed multi-page dry-run rollback defect and source-permission/cache hazards; added regressions.
6. Batched programme review evidence queries. Then optimized the institution-review queue to avoid loading all off-page institutions without a canonical website.
7. Verified the final queue against the real isolated import: 149 evidence-collection institutions, zero ready-for-review; 1.908 seconds locally. Original UAL public detail/description and all 54 fingerprinted original tables remained unchanged according to the saved verification log.
8. Last successful full-suite log: **465 passed, seven skipped**, completed **07:27:47 UTC**. The **final queue change and new query-count assertions were saved at 07:28:10–12 UTC**, after that run. They have a successful real isolated check, but **do not yet have a completed automated regression run on the final file state**.
9. The last completed inspection before the documentation request examined import table deltas and job metrics. No protected-operation approval request had been submitted.

**Exact stopping point:** final review-queue regression assertions need to run; then complete the final isolated/full validation and prepare a fresh, concrete development-import approval request. No ingestion should be started while merely reconstructing context.

## 3. Files attributable to the interrupted task

This inventory is reconstructed from actual code, source manifests, saved execution logs and the preceding task context. **No Git status/diff was run.** It is not a claim to identify every uncommitted file in the repository; unrelated earlier work is preserved. A complete historical before/after diff is **UNKNOWN — previous execution context not recoverable** without an external baseline. Modification times alone were not used to assign purpose.

| File | Change and current state |
| --- | --- |
| `backend/app/ingestion/program_import.py` | **New** operator CLI: capture, frozen replay, identity/permission preflight, plan, atomic apply. Reuses `run_source`, actual adapters and persistence. Tested before the final admin-only change; not in deployed API image. |
| `backend/app/ingestion/program_coverage.py` | **New** read-only SQL coverage CLI, explicit target safety and read-only transaction. Actual development/recovery reports saved. Not deployed. |
| `backend/app/ingestion/adapters/duo_rio.py` | Bounded snapshot capacity 5,000 offerings / 10,000 scanned rows; ordinary runs above 100 require the planned snapshot workflow; provider-specific cache hash; frozen replay avoids network/cache mutation. |
| `backend/app/ingestion/adapters/monmaster.py` | Up to 10,000 bounded records, strict 2025 row campaign, explicit joint/double-award holdouts; no newly invented current offers. |
| `backend/app/ingestion/registry.py` | Documents DUO manual bulk bounds and exact approval restriction; no scheduling activation. |
| `backend/app/ingestion/pipeline.py` | Dry runs use per-page nested transactions instead of rolling back the newly created source after page one. Normal persistent batch semantics retained. |
| `backend/app/services/admin.py` | Institution detail reuses batched catalogue evidence, caches source/institution links; final queue pagination fast path for institutions lacking canonical websites. **Final fast path still needs automated regression.** |
| `backend/app/services/catalog.py` | Defers large source-document excerpts in batched context to avoid repeated payload loading. No public JSON shape change. |
| `backend/app/services/program_evidence.py` | Optional batched context for official-registry evidence, retaining existing evidence rules and SQL fallback. |
| `backend/tests/test_program_import.py` | **New** deterministic 100/500 imports, rollback, repeated import, tamper refusal, ownership conflicts, archive holds, shared-board holds, policy restrictions, campaign filters, cache isolation and dry-run regression. Last added queue/detail query-count assertions are not yet confirmed by a final automated run. |
| `backend/tests/test_duo_rio_adapter.py` | Updated bounds and ordinary-run-above-100 rejection test. |

No new adapter country, migration, model, frontend component or dependency was introduced. No unfinished schema migration exists. The programme tool was not deployed: `/app/app/ingestion/program_import.py` is **absent** in the running API. Deployed versus workspace SHA256 values for the three modified service files differ.

> **Superseded 2026-10-22:** this describes the pre-deployment state. Operation B later replaced the API image; the importer and all three service files now match the workspace. See §11.

## 4. Source snapshots, eligibility and exclusions

All files below already exist; do not recapture them just to repeat completed work.

### Netherlands: `duo_rio_masters`

- Official dataset: <https://onderwijsdata.duo.nl/datasets/ho_opleidingsoverzicht>
- CKAN datastore API: <https://onderwijsdata.duo.nl/api/3/action/datastore_search>
- Resource: `ffffa7ad-e6a2-4ba7-9fc2-a09df4128555`; package `7c0686f4-b5c2-418e-8e44-7be0057d8084`.
- Rights checked in the interrupted task using official CKAN metadata and <https://data.overheid.nl/dataset/ho_opleidingsoverzicht>: **CC BY 4.0**, attribute DUO and identify normalization.
- Source modification: **2026-10-21T02:35:16.559393**. Capture completed **2026-10-22T06:33:57Z**, 28 responses, 5,000-record / 100-page bound.
- Raw MASTER rows 2,752. Adapter candidates 2,194 after 466 missing identifiers/titles, 91 partner offerings and one repeated offering row were excluded.
- Further identity preflight holds **693 offerings belonging to 23 providers** with shared governing boards or faculty/subunit labels. **1,501 offerings / 41 provider institutions selected**.
- Stable source identity: `duo:offering:{official UUID}`; provider `rio_provider_id` at reporting-unit scope. Names/domains/boards do not trigger automatic canonical merges.
- Snapshot manifest `.ingestion_cache/program-expansion/duo-snapshot/manifest.json` SHA256:
  `7552d042304b5a09c214cb4d9a0f68f7454e57b7fde6ce4a12932de6fd69d13c`.
- Actual isolated applicability: **1,484 unexpired registry offerings, 17 future**. These are not admissions-open assertions; academic year is unknown. Same-title offerings with distinct official UUIDs are legitimate distinct offerings, not necessarily distinct qualification families.
- All selected records remain candidates. Source website fields are institution-site candidates, not programme-page URLs or approved canonical websites.

The 23 held provider IDs and board IDs are explicitly recorded in `plans/development.json`. They include Maastricht/UMIO; Amsterdam arts schools; eight Radboud faculty units; Royal arts units; Radiant/Pentanova; and ArtEZ units. Reconcile with authentic institutional/organisational evidence, not name similarity.

### France: `fr_monmaster`

- Official API: <https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1/catalog/datasets/fr-esr-mon_master/records>
- Official metadata saved locally; **Licence Ouverte v2.0**. Attribute the ministry and the 2025 campaign.
- Source modification **2025-12-04T08:00:00+00:00**; capture **2026-10-22T06:35:43Z**, 82 responses, 10,000-record / 100-page bound.
- **8,167** raw campaign rows; nine joint/double-award pathways held, leaving 8,158 adapter candidates.
- **312 offerings held** because their two institution identities occur in the archive: UAI `0755976N` Université Paris Cité and `0931238R` Université Sorbonne Paris Nord. No archived identity was revived or automatically linked.
- Three more titles exceed the current 250-character validation limit: `fr-monmaster:ifc:2400012P6SQF`, `fr-monmaster:ifc:2400012PGW1S`, `fr-monmaster:ifc:2400012PISGY`. Held, not silently truncated.
- Final **7,843 offerings / 108 institutions**, all **historical 2025**, not current open admissions.
- Stable identity `fr-monmaster:ifc:{ifc}`, institution UAI reporting-unit claim. Mention/pathway/M1 semantics retained; no guessed university course URLs.
- Manifest `.ingestion_cache/program-expansion/fr-snapshot/manifest.json` SHA256:
  `596ebe9336fedfbad7ed6f50b51eb21694e0197235826dd0b8cb99ea0af64484`.

### UAL: inspected, not expanded

Official JSON returned 64 plan rows, 35 eligible nonjoint/nondouble Master's plans. Five are the reviewed pilot. The remaining 30 were **not imported**, not included in the proposed operation, and not subjected to new course-page crawling. The approved pilot must remain unchanged.

## 5. Importer architecture and exact plan

`capture` uses the existing timeout/retry/rate-limited fetcher, requires source rights metadata, and refuses snapshot overwrites. It stores bounded HTTP 200 response bodies, exact URLs, checksums, acquisition timestamps and an allowlist of response headers. `batches` replays only recorded URLs through the real adapters: no network fallback, original retrieval time, replay attempt count zero, original source publication date.

`selection` enforces both registry and persisted-source permission; detects conflicting duplicate identifiers before an adapter can use first-wins; uses the existing resolver; holds ambiguous/archived/subunit identities; validates names/degree/title lengths; and skips already persisted programme identities. Accepted programme IDs are deterministic source identity claims, **not** human approval of the institution or facts.

`plan` binds the database/role/revision, source manifests, parser/persistence code digest, backup digest, selected identities and original row fingerprints. `apply` wraps normal pipeline batch commits inside savepoints under one outer database transaction/advisory lock. It verifies exact creation counts, candidate status, owner/title/degree, known warnings and unchanged original rows before committing. Unexpected failure rolls back the whole planned addition. No review decision is made.

Important boundary: the original-row fingerprint covers 54 existing tables but **excludes `sources`**, whose registry metadata can be resynchronized. Directory/archive tables are whole-table hashed. Existing original rows in other tables are hashed by saved primary keys so new rows are allowed. Source policies are checked before pipeline synchronization. The code digest covers six ingestion files; **it does not cover the admin service files or every registry/normalization dependency**. Any source policy, parser, snapshot or deployment change requires fresh inspection and plan validation, not reliance on an old approval token.

### Existing development plan — unapproved

Path: `.ingestion_cache/program-expansion/plans/development.json`.

| Field | Saved value |
| --- | --- |
| Database / administrative role | `uni_shortlist` / `uni_shortlist` |
| Revision | `9c24a7e6d180` |
| Expected additions | 9,344 candidate offerings; 149 pending institutions |
| Code digest | `75e159351e475196fd5211c623adf3b005ef3007117798f076eae2566df2801d` |
| Confirmation digest | `38ca6c48b406b8908e6e450eb0da962f05c9e02c40c399edf8e1d4829ee69a2f` |
| Backup as mounted | `/backup/uni_shortlist_20261022T063327Z.dump` |
| Backup SHA256 | `bba27871fef9b42e7628746a465d4a18f21dcb5bc1aeb1b85e713e6a681381ff` |

Host backup: `.db-backups/program-expansion/uni_shortlist_20261022T063327Z.dump`, approximately 5.8 MiB, private permissions, outside PostgreSQL storage; `.dump.meta` is private metadata. This backup was restored to the marked isolated recovery database. Future legitimate development writes can invalidate the plan's baseline. Obtain a fresh backup/plan if necessary. Superseded plans with 10,037 offerings or other confirmation hashes are not executable authority.

Affected append-only areas: universities, institution identifier claims and pending reviews, fields where absent, programmes, programme identifiers, source metadata/new source row, documents/retrievals, facts/versions/evidence, ingestion jobs/items. No original UAL programme/fact/review/user/archive row should change. No new migration. Public Discover should remain **one**, not 9,345.

## 6. Actual isolated rehearsal and metrics

Project `uni-shortlist-program-recovery`, database container `uni-shortlist-program-recovery-db-recovery-1`, database/role `uni_shortlist_recovery`. It remains running at this checkpoint. Private internal network, no published database port, tmpfs; stopping/removing this container loses the rehearsal database. Durable recovery is the backup plus frozen snapshots/plans, not that tmpfs database.

Compose files: `docker-compose.recovery.yml` plus temporary `/tmp/uni-program-recovery.yml`. Private environment file `/tmp/uni-global-recovery.env` contains recovery credentials: **do not print, copy into docs, or commit it**. Overrides mount current backend source, snapshots, plans and backup; ordinary recovery image alone may be older.

| Successful addition | Programmes | Distinct new institutions | New facts |
| --- | ---: | ---: | ---: |
| DUO job `3363d75b-a4e7-4adb-ba19-14b7c47fc97b` | 1,501 | 41 | 11,743 |
| Mon Master job `4e452dc4-dedb-4b94-9c02-a20758dc4ba9` | 7,843 | 108 | 68,904 |
| Total | **9,344** | **149** | **80,647** |

Total deltas: +80,650 versions, +81,532 evidence links, +105 source documents (23 DUO / 82 French). Three extra versions update newly introduced institutional facts, not old verified facts. Page-level “institution seen/unchanged” counters are not distinct institution counts.

Both first-import jobs are `partial` because known source holdouts remain warnings, while **every selected record was persisted** with zero validation errors, HTTP failures, conflicts or review requests. Do not report `partial` as a clean source-wide import or confuse warnings with missing selected records.

Replay plan `.ingestion_cache/program-expansion/plans/recovery-repeat.json` selected zero additions. Replay jobs `e3bd78a0-40b2-4c6b-9bc0-f7f7a2488fe8` and `8ca44115-eb59-4192-bec9-b1b6e1023ef1` succeeded with zero catalogue/fact/evidence additions.

All 9,349 isolated programmes lack relational tuition, admissions, deadlines and duration. Only the original five have verified official pages; only original UAL has institution approval; only original programme is published. Isolated review queue correctly reports 149 institutions collecting evidence, not ready for approval.

## 7. Failed and superseded experiments

| Experiment | Result / resolution |
| --- | --- |
| Initial 10,037-offering / 172-institution proposal | Superseded after Dutch provider/faculty audit. Do not reuse its counts or plans. |
| First full isolated import | Wrapper incorrectly rejected `partial` jobs caused by known holdouts. Outer transaction rolled back. Changed to allow only manifest-known warnings with exact selected counts and no unexpected failures. |
| Subsequent oversized rehearsal | Deliberately stopped when subunit ambiguity was found. Isolated database restored again from backup; development was not restored or reset. |
| DUO 100-record multi-page dry run | Failed after page one with `source_documents_source_id_fkey`: session rollback removed the new source. Fixed nested per-page rollback. Both sources subsequently completed 100-record dry runs with no persistent state change. |
| Wrapper session defaults | Aligned autoflush/expiration with existing `SessionLocal`: both false. |
| Provider-specific response cache | Missing query component could reuse another provider response. Cache key now includes query digest. |
| French campaign/joint rows | Strict 2025 check and explicit joint/double-award holdouts added. |
| Persisted source permission versus registry sync | Preflight now refuses disabled/forbidden persisted sources before registry metadata can overwrite the policy. |
| Review detail N+1 | Saxion 12-programme example: 279 queries/0.609 s before, 29/0.414 s after batching; saved response payloads equal. |
| Review queue scanning all evidence | First batching still took 59.759 s for 149 institutions. Final no-website/off-page fast path measured 1.908 s, correct stage counts. Automated assertions saved afterwards still need execution. |

No unresolved exception is known in the successful selected-data rehearsal. That is not a final automated certification of the latest queue edit, browser verification, or production-scale concurrency result.

### Executed command families versus pending commands

Saved results establish execution of these existing interfaces in the **preceding
implementation task**, not during documentation:

| Interface | Established execution / target |
| --- | --- |
| `python -m app.ingestion.program_import capture` | DUO: limit 5,000 / max-pages 100; France: limit 10,000 / max-pages 100; official metadata supplied; saved manifests record exact source request URLs |
| `python -m app.ingestion.program_import plan` | `development`, `recovery` and recovery-repeat plans written; planning is read-only against PostgreSQL |
| `python -m app.ingestion.program_import apply` | **Recovery target only**; exact full selected import and repeat, with results/job IDs above |
| Existing pipeline `run_source(..., dry_run=True)` | Corrected 100-programme dry runs for each source; no persistent catalogue changes |
| `python -m app.ingestion.program_coverage --target ...` | Development and recovery reports saved under `/tmp/uni-program-*` |
| Guarded `python -m pytest -o addopts='' -q` | Targeted/full runs documented above; final queue assertions still pending |
| Frontend `npm run test` | Existing suite: 41 passed; no frontend changes |
| Backup/isolated restore tooling | Current development backup created and restored to the marked recovery project; not a development restore |

The complete original shell invocations/container IDs for every command are not
recoverable. The exact mount/runner syntax known for future reproduction is given
below; do not invent a full command transcript from file timestamps.

**Not executed:** development programme `apply`; any new migration; API rebuild or
replacement for this code; remaining UAL plan import; new country connector;
institution/fact approval or programme publication; scheduler activation. The last
queue regression rerun was planned but not executed before the pause.

## 8. Evidence files and retention

### Durable workspace artifacts (ignored/private; preserve securely)

- `.ingestion_cache/program-expansion/duo-package.json`, `duo-sample.json`, `fr-metadata.json`, `fr-sample.json`, `ual-feed.json`, each with retrieval sidecars.
- `duo-snapshot/`: manifest, 28 response files, adapter cache; `fr-snapshot/`: manifest, 82 response files.
- `plans/development.json`, `plans/recovery.json`, `plans/recovery-repeat.json`.
- `.db-backups/program-expansion/` backup and metadata.
- Prior ROR release, validation store and directory plans under `.ingestion_cache/ror/v2.15/`; do not download/reimport it again.

These are local artifacts, not guaranteed to transfer with source documentation. No Git inspection was performed. A successor must verify existence, checksums and permissions before relying on them. Do not upload source dumps, private backups or credentials to a public repository.

During the documentation checkpoint, all **28 Dutch and 82 French captured response
body checksums** were independently recomputed and matched their manifests. The
5.8 MiB programme backup checksum also matched the value above. No source was
retrieved and no backup was restored to perform those read-only file checks.

### Existing temporary logs (can disappear after restart)

| Path | What it establishes |
| --- | --- |
| `/tmp/uni-program-recovery-final-import.txt` | Exact successful 9,344-record isolated import results |
| `/tmp/uni-program-recovery-coverage.json` | PostgreSQL-derived 9,349-offering recovery coverage |
| `/tmp/uni-program-development-before.json` | Development five-programme baseline |
| `/tmp/uni-program-recovery-repeat.txt` | Zero-addition replay |
| `/tmp/uni-program-final-verification.txt` | 54 original table fingerprints, queue stage counts/timing, unchanged UAL/public boundaries |
| `/tmp/uni-program-review-before.txt`, `...-after.txt` | Review-detail query reduction; corresponding payload JSON files compare equal |
| `/tmp/uni-program-dryrun.txt` | Corrected 100-record dry runs |
| `/tmp/uni-program-targeted-permissions-final.txt` | 37 passed in 67.97 seconds |
| `/tmp/uni-program-admin-targeted.txt` | 60 passed in 65.87 seconds, before last queue edit |
| `/tmp/uni-program-backend-complete.txt` | 465 passed / 7 skipped in 443.65 seconds |
| `/tmp/uni-program-backend-delivery.txt` | 465 passed / 7 skipped in 259.68 seconds, completed before final queue edit |
| `/tmp/uni-program-frontend.txt` | 41 passed, seven files, 2.96 seconds |

Earlier backend logs record 460, 463 and 464 passes as fixes accumulated; they are superseded, not cumulative test counts. Seven skips are explicit `RUN_LIVE_INGESTION_TESTS` opt-ins. No tests were rerun during documentation.

Temporary operator scripts `/tmp/uni-program-review-profile.py`, `/tmp/uni-program-verify-recovery.py`, `/tmp/uni-program-dryrun.py` and temporary Compose overrides helped execute checks. Do not blindly execute old scripts: some write local files or restore isolated data. Their full prior shell command history is **UNKNOWN — previous execution context not recoverable**; saved result logs and repository CLIs/tests are the reproducible evidence.

## 9. Safe continuation order

1. Read this file, the complete handover, execution plan, source matrix and latest status checkpoint. Reinspect current workspace and live DB read-only. Preserve unrelated files.
2. Check that the marked test/recovery targets and private environment files still exist. Never point pytest at `uni_shortlist`; its fixtures truncate test tables.
3. Run targeted tests on **the final current queue code**, then the full isolated backend suite. Recheck the final test count rather than copying 465. No live crawl needed.
4. Inspect the saved snapshots/plans and matching code/backup hashes. Review reporting-unit ownership and held identities; do not “fix” them by automatic merges.
5. If importer code or target baseline changed, generate a new read-only selection/plan and refresh/rehearse backup as appropriate. A plan file write is not development ingestion permission.
6. Finish source/coverage report and exact execution request: 1,501 Dutch + 7,843 historical French candidates, 149 pending institutions, unchanged UAL/archive, no migration, no new public visibility. State measured storage and rollback boundary.
7. **Wait for explicit user approval of the exact development write and separately any API deployment.** The earlier ROR deployment authorization does not authorize programme imports.
8. Only after approval: apply approved plan; verify database counts, all old row fingerprints, no duplicated identities, unchanged description/publication and scheduler false. Deploy API only if specifically approved. Human review/publication remains later work.

### First safe inspection commands

Run from the repository root. These do not start import/migration/refresh jobs:

```bash
docker compose ps --format '{{.Service}} | {{.State}} | {{.Status}}'
sed -n '1,240p' backend/app/ingestion/program_import.py
sed -n '490,565p' backend/app/services/admin.py
tail -8 /tmp/uni-program-backend-delivery.txt
docker compose exec -T db psql -U uni_shortlist -d uni_shortlist -X \
  -c "BEGIN READ ONLY; SELECT version_num FROM alembic_version; SELECT publication_status,count(*) FROM programs GROUP BY 1; SELECT count(*) FROM catalogue_archive_records; ROLLBACK;"
curl -fsS http://localhost:8000/api/v1/health/ready
curl -fsS http://localhost:8000/api/v1/programs
```

### First unfinished automated validation (future implementation session only)

Existing private isolated stack was invoked as follows; verify temporary files/targets first:

```bash
docker compose --env-file /tmp/ual-pages-test.env -p uni-shortlist-ual-pages \
  -f docker-compose.test.yml -f /tmp/ual-pages-test.yml --profile test run --rm \
  -v "$PWD/backend/app:/app/app:ro" -v "$PWD/backend/alembic:/app/alembic:ro" \
  test-runner python -m pytest -o addopts='' -q \
  tests/test_program_import.py tests/test_admin.py tests/test_program_quality.py \
  tests/test_ual_institution_review.py
```

For the full suite, omit the four test paths. The image and mount combination must use current source/tests. Missing temporary configuration must be recreated from supported isolated test Compose configuration and fresh private test secrets; never substitute development URLs.

### Future protected operation — reference syntax only, NOT authorized

```bash
docker compose --profile db-admin run --rm --no-deps \
  -v "$PWD/backend/app:/app/app:ro" \
  -v "$PWD/.ingestion_cache/program-expansion:/snapshots:ro" \
  -v "$PWD/.ingestion_cache/program-expansion/plans:/plans:ro" \
  -v "$PWD/.db-backups/program-expansion:/backup:ro" \
  db-admin python -m app.ingestion.program_import apply --target development \
  --plan /plans/development.json --confirm <fresh-explicitly-approved-confirmation>
```

No migration command belongs in this operation. API rebuild/replacement is a separate operational permission. Do not execute `run-all`, a direct high-limit adapter import, seed commands, old reset runbooks or automatic scheduler activation.

## START HERE — NEXT CODEX SESSION

> **SUPERSEDED for validation work by the OpenCode continuation checkpoint below.**
> The remaining open item is now the explicit development import/deployment approval.

**First unfinished task:** validate the final review-queue fast path and query-count regressions, then finish the exact candidate-import approval request. **Next measurable success:** current-source targeted/full isolated tests pass, the saved 9,344-offering selection is reproducible with unchanged UAL/archive, and a precise development operation is ready for user approval. Development counts must remain five until that approval.

Ready-to-copy continuation prompt:

> Resume UniShortlist in `~/Parth/Internship/Uni-grp-prj` only after reading `docs/UNISHORTLIST_INTERRUPTED_WORK_RECOVERY.md`, `docs/UNISHORTLIST_COMPLETE_PROJECT_HANDOVER.md`, `docs/UNISHORTLIST_GLOBAL_PROGRAMME_EXECUTION_PLAN.md`, `docs/UNISHORTLIST_SOURCE_COVERAGE_MATRIX.md` and the latest appended project-status checkpoint. Inspect the actual repository, current development/recovery databases read-only, saved manifests/plans and logs. The ROR directory is already deployed: do not repeat it. Development has five UAL programmes; 9,344 extra Dutch/French offerings were imported only in isolated recovery. The last queue optimization and query-count assertions postdate the last full 465-pass run: validate them first using marked isolated tests. Reuse existing snapshots/importer, preserve all original records and the published UAL description, and resume only the highest-priority unfinished programme-import validation. No Git commands, resets, automatic approvals/publication, scheduling, fabricated facts or unbounded crawling. No development ingestion or deployment until the user explicitly approves the exact freshly verified operation. Prepare that concrete request after finishing independent tests, rights/identity checks, backup readiness and SQL coverage. Do not restart already completed implementation or mistake reference-directory rows for Master's programmes.

---

## 10. OpenCode continuation checkpoint — 2026-10-22, 09:00–09:10 UTC / 14:30–14:40 IST

This section supersedes §2, §7 (pending items) and §9 step 3 above. It records code
inspection, read-only verification and isolated testing. **No development database
write, migration, deployment, review decision, publication, source crawl or
scheduler change was performed, and no Git command was run.**

### 10.1 What the continuation actually did

1. Read the full documentation set and inspected the real code of
   `program_import.py`, `program_coverage.py`, `adapters/duo_rio.py`,
   `adapters/monmaster.py`, `pipeline.py` (`_consume`), `services/admin.py`
   (`institution_review_queue`, `institution_review_detail`), `services/catalog.py`
   (`_page_context`) and `services/program_evidence.py`.
2. Re-verified the development and isolated recovery databases read-only (values
   unchanged; see the project-status checkpoint).
3. Re-hashed every frozen artefact read-only: both snapshot manifests, all 28 Dutch
   and 82 French captured response bodies, the pre-import backup, the importer code
   digest and the plan confirmation digest. **All match the values in §4, §5 and §6.**
4. Ran the targeted isolated regressions, then the full isolated backend suite,
   then the frontend suite/typecheck/lint/build, then a read-only Alembic check.
5. Closed five genuine regression gaps in `backend/tests/test_program_import.py`.
6. Re-verified the running API image is still the pre-import build
   (`program_import.py` absent; `admin.py`, `catalog.py`, `program_evidence.py`
   hashes differ from the workspace).

### 10.2 Interruption matrix — final state

| Task | State |
| --- | --- |
| Frozen DUO capture (28 responses, CC BY 4.0) | COMPLETE |
| Frozen Mon Master capture (82 responses, Licence Ouverte v2.0, campaign 2025) | COMPLETE |
| `program_import.py` capture/plan/apply wrapper | COMPLETE, now fully regression-tested |
| `program_coverage.py` read-only reporting | COMPLETE |
| Dutch bounds, provider-scoped cache, `frozen_replay` | COMPLETE, tested |
| French 2025 campaign filter and joint/double-award holdouts | COMPLETE, tested |
| Multi-page dry-run savepoint rollback fix | COMPLETE, tested |
| Persisted-source permission preflight | COMPLETE, tested |
| Institution identity holds (shared board / subunit / archived / over-length) | COMPLETE, tested |
| Batched institution detail evidence | COMPLETE, tested |
| Review-queue pagination fast path | COMPLETE, **now regression-tested** (see 10.3) |
| Review-queue query-count assertions | COMPLETE, executed |
| Isolated 9,344-offering rehearsal and zero-addition replay | COMPLETE, counts reconfirmed |
| Plan / backup / snapshot / confirmation integrity | COMPLETE, reverified |
| Full isolated backend suite on the final file state | COMPLETE — **470 passed / 7 skipped** |
| Frontend suite, typecheck, lint, build | COMPLETE — 41 passed, clean |
| Alembic drift check | COMPLETE — "No new upgrade operations detected" |
| Development import of 9,344 offerings | ~~BLOCKED~~ → **EXECUTED AND VERIFIED 2026-10-22 09:45–09:58 UTC** (user-approved; see §11) |
| API deployment of the importer and review-performance code | ~~BLOCKED~~ → **EXECUTED AND VERIFIED 2026-10-22 10:05 UTC** (user-approved; see §11) |
| Institution identity/name/website review for the 149 new institutions | NOT STARTED — human review work |
| Verified course pages and academic enrichment for the new offerings | NOT STARTED — post-deadline |
| Dutch provider reconciliation (23 providers / 693 offerings) | NOT STARTED — requires official organisational evidence |
| French archived-identity reconciliation (2 institutions / 312 offerings) | NOT STARTED — requires historic association evidence |

Nothing in the interrupted implementation was found incomplete or defective. No
application code was modified in this continuation.

### 10.3 Five regressions added to `backend/tests/test_program_import.py`

The `snapshot()` fixture helper gained a `name` argument so a test can capture
several independent snapshots (snapshot directories are never overwritten).

| Regression | Guards against |
| --- | --- |
| `test_mixed_source_plan_keeps_national_offerings_and_identities_separate` | One plan carrying both national sources must keep identifier namespaces disjoint (`duo:offering:*` vs `fr-monmaster:ifc:*`, `rio_provider_id` vs `uai`), must not merge an identical institution name across NL and FR, must leave all 18 offerings as candidates under 2 pending reviews with 0 approved and 0 published, and must add nothing on replay. |
| `test_second_provider_with_an_identical_name_is_held_instead_of_merged` | A different provider identifier carrying an existing institution name is **held** (`name_country`), never merged; the existing canonical university is neither duplicated nor relabelled. |
| `test_review_queue_pagination_is_deterministic_and_stage_filtered_at_scale` | 20 institutions / 100 offerings: pages are disjoint and complete, ordering is stable, stage filtering happens **before** pagination, each item's own `workflow_stage` agrees with the queue's fast-path bucket, and the query count stays bounded for institutions with no canonical website. |
| `test_existing_catalogue_publication_and_archive_state_survive_the_import` | Pre-existing programme UUID/slug/publication status, university rows and archive counts are unchanged; public Discover is unchanged; every new offering returns 404; nothing is newly published. |
| `test_interrupted_import_leaves_nothing_behind_and_the_exact_plan_reapplies` | An injected mid-import failure leaves zero partial catalogue/document state and an unchanged original-row fingerprint; re-applying the *same* approved plan completes the exact planned addition. |

### 10.4 Queue fast-path equivalence (established, not assumed)

`discovery_stage()` returns one of `ready_for_review`, `discovery`,
`program_evidence_needed`, `website_evidence_needed`, `institution_evidence_needed`.
The queue groups only `discovery` / `evidence_collection` / `ready_for_review`,
collapsing the three `*_needed` stages into `evidence_collection`. Since an absent
canonical website always blocks approval, a website-less institution can never be
`ready_for_review`; therefore the fast path (no website → `discovery` when there are
no programmes, otherwise `evidence_collection`) is exactly equivalent to full
serialization. This is now asserted on real imported data rather than inferred.

### 10.5 Fresh test record (supersedes §8 temporary logs)

| Command (marked isolated stack, current source mounted) | Result |
| --- | --- |
| `python -m pytest -o addopts='' -q tests/test_program_import.py` | **17 passed** in 59.12 s |
| `python -m pytest -o addopts='' -q tests/test_admin.py tests/test_program_quality.py tests/test_ual_institution_review.py tests/test_duo_rio_adapter.py tests/test_monmaster_adapter.py tests/test_ingestion.py` | **152 passed** in 42.81 s |
| `python -m pytest -o addopts='' -q` (full backend) | **470 passed, 7 skipped** in 174.61 s |
| `alembic current` / `alembic heads` / `alembic check` | `9c24a7e6d180` / `9c24a7e6d180` / "No new upgrade operations detected" |
| `npm run test` | **41 passed**, 7 files, 3.18 s |
| `npm run typecheck`, `npm run lint`, `npm run build` | all clean |

Invocation used (reproducible; the isolated project, image override and private
env file already existed):

```bash
docker compose --env-file /tmp/ual-pages-test.env -p uni-shortlist-ual-pages \
  -f docker-compose.test.yml -f /tmp/ual-pages-test.yml --profile test run --rm \
  -v "$PWD/backend/app:/app/app:ro" -v "$PWD/backend/alembic:/app/alembic:ro" \
  test-runner sh -c "python -m app.db.safety verify && python -m pytest -o addopts='' -q"
```

The seven skips remain the explicit `RUN_LIVE_INGESTION_TESTS=1` opt-ins in
`tests/test_ingestion_live.py`. This run **is** on the final file state, including
the last queue fast path and its query-count assertions; the 465/7 figure is
superseded.

### 10.6 What remains

Only the protected operations:

- **Development programme import** of 9,344 candidates / 149 pending institutions
  from the frozen, checksum-verified snapshots under the saved, unapproved plan
  `plans/development.json` (confirmation `38ca6c48…`, backup `bba27871…).
- **Optional API-only redeploy** so the running image contains the importer and the
  review-performance code. This is a separate permission; the current deployed pilot
  is unaffected either way.

Both require explicit user approval. Until then development must remain at five
programmes, one published programme and 1,479 archived records.

---

## 11. EXECUTION RECORD — 2026-10-22, 09:45–10:10 UTC / 15:15–15:40 IST

> **Explicit user approval was granted for both operations (A import, B API redeploy) before any write.**
> This section records the bounded execution and the independently verified result.

### Authorization and pre-execution revalidation

The operation proceeded only after every gate re-passed immediately before the write:

| Gate | Result |
| --- | --- |
| Target database identity | `uni_shortlist` / `uni_shortlist` — **match** |
| Schema revision | `9c24a7e6d180` — **match**, no migration run |
| Plan confirmation digest recomputed | `38ca6c48b406b8908e6e450eb0da962f05c9e02c40c399edf8e1d4829ee69a2f` — **match** |
| Importer `code_hash()` vs plan | `75e159351e475196fd5211c623adf3b005ef3007117798f076eae2566df2801d` — **match** |
| Pre-import backup SHA256 | `bba27871fef9b42e7628746a465d4a18f21dcb5bc1aeb1b85e713e6a681381ff` — **match** |
| DUO snapshot manifest | `7552d042304b5a09c214cb4d9a0f68f7454e57b7fde6ce4a12932de6fd69d13c` — **match** |
| Mon Master snapshot manifest | `596ebe9336fedfba…` — **match** |
| Pre-existing counts | 5 programmes / 1 published / 1 institution / 30,328 directory / 1,479 archive / 66 facts / 14 documents — **match** |
| UAL programme + description | `2fffabd2-fd80-43d9-a6a8-6d0e9d6702c8`, slug `m-ster-en-comunicaci-n-social`, description 479 chars — **unchanged** |

No plan was regenerated or broadened. One operational prerequisite was required and performed:
the `db-admin` image was rebuilt from current source (it predated `program_import.py`), and
`APP_DATABASE_URL` was passed through from `.env` because `pipeline.py` imports `SessionLocal`
at module scope. `run_source(db=db)` always receives the admin session, so the runtime engine is
never opened and never writes.

### Operation A — bounded import

Single atomic transaction, advisory-locked, per-source `SELECT ... FOR` planning inside one
`engine.begin()`. Result:

| Source | Licence / version | Programme status | Institutions | Duration |
| --- | --- | --- | --- | --- |
| `duo_rio_masters` | CC BY 4.0, `2026-10-21T02:35:16.559393` | `partial` (expected holds/skips) | 41 created, 15 unchanged | 40.0 s |
| `fr_monmaster` | Licence Ouverte v2.0, `2025-12-04T08:00:00+00:00` | `partial` (expected holds) | 108 created, 855 unchanged | 744.35 s |

Both summaries reported `validation_errors: []`, `http_failures: []`, `programs_rejected: 0`,
`programs_review_required: 0`, `review: 0`, `conflicted: 0`. Warnings were exclusively the
pre-declared hold classes already counted in the plan (23 Dutch shared-board subunits,
9 French joint/double-award pathways, rows missing provider identity/offering UUID/title).

### Idempotent replay

The identical command was re-executed against the now-populated database:

```
duo_rio_masters  status=succeeded  programs_created=0  institutions_created=0  facts_created=0  documents=0
fr_monmaster     status=succeeded  programs_created=0  institutions_created=0  facts_created=0  documents=0
TOTAL programs_created = 0    TOTAL institutions_created = 0
```

Counts were unchanged after replay: 9,349 programmes / 150 institutions / 80,717 versions /
81,599 evidence / 119 documents.

### Operation B — API-only redeploy

Only the `api` service was rebuilt and replaced. `db`, `db-test`, `nginx` and `web` kept their
original start times and were not recreated. No migration ran (no entrypoint migration; the
Dockerfile `CMD` is plain `uvicorn`, `MIGRATION_TARGET` empty).

| | Before | After |
| --- | --- | --- |
| API image ID | `1211a2a67b55` | `9e5d86be4360…` |
| `program_import.py` in image | **absent** | **present** |
| `app/services/admin.py` hash | differed from workspace | **match** `7e145d641b25` |
| `app/services/catalog.py` hash | differed from workspace | **match** `9bb44ba6376e` |
| `app/services/program_evidence.py` hash | differed from workspace | **match** `5a357f89eaa2` |
| Deployed `code_hash()` | n/a | `75e159351e475196…` — equals workspace |

### Independently verified result (direct PostgreSQL + public API)

| Check | Required | Verified |
| --- | --- | --- |
| Total programmes | 9,349 | **9,349** |
| Published | 1 | **1** |
| Candidates | 9,348 | **9,348** |
| Any other publication status | 0 | **0** |
| Canonical institutions | 150 | **150** (149 new: FR 108 / NL 41) |
| Global directory references | 30,328 | **30,328** (223 countries) |
| Archived catalogue records | 1,479 | **1,479** |
| Approved institution reviews | 1 | **1** (Universidad de Almería only) |
| Pending institution reviews | — | **149 created for the 149 new institutions** |
| Verified facts | 8 | **8** (all pre-existing UAL; none new) |
| Facts / versions / evidence | — | 80,713 / 80,717 / 81,599 |
| Source documents | 119 | **119** (23 DUO + 82 FR + 14 pre-existing) |
| Programme identifiers | 9,349 | **9,349**, **0 duplicate** `(source_key, external_key)` |
| `program_fees` / `admission_requirements` / `program_intakes` | 0 / 0 / 0 | **0 / 0 / 0** |
| French 2025 historical labelling | historical | **7,843 / 7,843** carry `academic_campaign = {"session":"2025"}` |
| Dutch offering validity | source-faithful | 1,501 carry `offering_validity_period` |
| UAL UUIDs / slug / description | unchanged | `2fffabd2…` / `m-ster-en-comunicaci-n-social` / 479 chars, 7 facts, 8 versions, 8 evidence |
| Public Discover | original programme only | **`total_items: 1`** on API `:8000` **and** NGINX `:8080` |
| Candidate public access | 404 | **404** for sampled NL, FR and new candidates on both routes |
| Scheduler | disabled | `ENABLE_SCHEDULER=false`, no scheduler log lines |
| Idempotent replay | zero additions | **0 / 0** |

### Two observations recorded honestly

1. **504 slug values are shared by 1,883 candidate rows** (all French, all `candidate`,
   none published; the UAL slug occurs exactly once). This is structurally harmless: public
   detail routing is by **UUID**, and `_load_program()` additionally requires
   `publication_status == 'published'`, `is_active` **and** `institution_approved_clause()`.
   It is recorded here because **slug disambiguation must be handled during human review
   before any French programme is ever published**.
2. **13 pre-existing university-less pending reviews dated 2026-10-20** remain in
   `institution_reviews` (unrelated to this import; **0** were created during the import
   window). They predate the operation and were neither modified nor removed.

### Safety properties demonstrated on the real database

- No institution auto-approved: the sole `approved` review is the pre-existing UAL one.
- No fact auto-verified: the 8 `verified` facts are all pre-existing UAL facts.
- No programme auto-published: exactly 1 published, unchanged.
- No invented academic or commercial data: fees, requirements and intakes all remain 0.
- No duplicate identities: 0 duplicate `(source_key, external_key)` pairs.
- Existing catalogue, archive, evidence and users untouched (protected-row fingerprint
  checked twice inside the apply transaction — before and after).

## 12. Post-execution independent validity audit (2026-10-23)

A separate verification-only audit (no writes, no approvals, no publications) re-derived
the import from the frozen snapshots and audited every stored URL. Full report:
`docs/UNISHORTLIST_PROGRAMME_IMPORT_VALIDITY_AUDIT.md`.

- Re-parsed raw source bodies independently: DUO 2,752 raw → 2,194 selected → 1,501 stored; Mon Master 8,167 raw → 8,158 selected → 7,843 stored. **0 database rows absent from source; 0 field mismatches** on title, provider/UAI, country, degree level or status.
- All 149 new institutions clean: 0 cross-country name collisions, 0 duplicate canonical names, 0 identifier reuse, 0 mismatches against source-reported names.
- 316 of 419 distinct stored URLs checked with bounded, robots-respecting requests: 280 passed, 30 failed. **Every failure is infrastructure (DNSSEC/CA) or a stale URL already in the official DUO register — no fabricated or placeholder link.**
- Environment note: the host had rebooted, stopping the stack. With user approval the existing containers were started (`docker compose start`, no recreation/rebuild/migration); the `pgdata` volume was verified intact first and post-restart counts matched exactly.

Note: this section documents audit findings only. No corrective action was taken.
