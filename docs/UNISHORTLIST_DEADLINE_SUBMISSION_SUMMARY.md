# UniShortlist — submission status and next delivery

**Status at 22 October 2026.** Counts below distinguish the deployed application from an isolated import rehearsal. They are not projections of future approvals.

## What the application does today

UniShortlist helps students discover, save, compare and shortlist Master's programmes using source evidence and explicit review controls. Its administrative workflow keeps institution identity, university approval, programme facts and programme publication separate. Missing academic information is shown as unavailable rather than guessed.

The application uses FastAPI, PostgreSQL, SQLAlchemy and Alembic, with a Vue 3 frontend and Docker Compose/NGINX deployment. Authentication, reviewer permissions, evidence history, source management, ingestion jobs, programme review and student workflows are implemented.

## Deployed coverage

| Coverage measure | Current development application |
| --- | ---: |
| Global institution reference records | **30,328** |
| Country/territory codes represented by references | **223** |
| Approved canonical universities | **1** |
| Authentic Master's programmes in the active catalogue | **5** |
| Programmes with reviewed official individual webpages | **5** |
| Published programmes visible to students | **1** |
| Unpublished programme candidates | **4** |
| Preserved historical catalogue archive records | **1,479** |

The global reference directory uses the official **ROR v2.15** release. It supports identity discovery and searchable reference information. **It is not a comprehensive worldwide Master's programme catalogue and does not mean 30,328 universities have been approved.**

## Completed end-to-end pilot

The Universidad de Almería pilot demonstrates the complete evidence and publication workflow:

1. Retrieve authentic named Master's plans from the university's official catalogue.
2. Resolve the institution using authoritative ROR identity and a reviewed source association.
3. Review institution name and website evidence, then approve the institution.
4. Retrieve programme-specific official webpages with matching titles and plan identifiers.
5. Persist source documents and candidate facts; verify URLs through human review.
6. Publish a programme through a separate decision.
7. Display it in student Discover and programme details with a reviewed description, source attribution and honest missing-data indicators.

**Máster en Comunicación Social** is published. The other four programmes remain unpublished candidates even though their official links have been verified. This separation is intentional.

The public programme has a verified source page and a reviewed summary. Duration, teaching language, tuition, admissions requirements, intake dates, deadlines and programme outcomes remain unavailable. A verified page is not a claim that all academic details or admission eligibility have been confirmed.

## International programme expansion: validated, not yet deployed

The next high-volume addition has been rehearsed against an isolated restored copy of the database:

| Official source | Additional programme offerings | Additional pending institutions | Applicability |
| --- | ---: | ---: | --- |
| Netherlands DUO/RIO | **1,501** | **41** | Registry validity preserved; 1,484 unexpired and 17 future offerings, not admissions-open claims |
| French Mon Master | **7,843** | **108** | Explicitly **historical 2025** catalogue |
| Total | **9,344** | **149** | All unpublished candidates |

These records were genuinely persisted in the isolated rehearsal and a repeated import created no additional programmes, facts or evidence. Existing UAL records, public description, publication decisions, directory and archive were preserved. Ambiguous Dutch provider/subunit identities, French archive matches, unsupported joint awards and invalid-length titles were excluded rather than guessed or merged.

**The additional 9,344 offerings are not in development.** No programme bulk-development import has been authorized. The final review-queue optimization still needs its automated regression rerun before an exact development operation is presented for approval. New institutions and programmes would remain unapproved and unpublished after import; further evidence and human review are required before student publication.

## Reliability and evidence

- The deployed global-directory baseline reported **452 backend tests passing, seven opt-in live tests skipped**, and **41 frontend tests passing**.
- Saved logs for the subsequent programme work showed **465 backend tests passing, seven skipped**. That figure was superseded on 2026-10-22: a fresh full isolated run on the final file state (including the last queue optimization and its query-count assertions) reports **470 backend tests passing, seven skipped**, plus 5 new importer regressions. Frontend remains **41 passing** with clean typecheck, lint and build. The importer and review-performance code are **not deployed**.
- The international import was rehearsed with actual official source snapshots, exact identifiers, isolated persistence, repeated-import checks and original-record fingerprints.
- Read-only checks for this handover independently confirmed current development and recovery counts, schema revision, running services, public Discover and the reviewed programme description. No new test suite, ingestion or deployment was run for the handover.
- Development remains on Alembic **`9c24a7e6d180`**, with scheduling disabled. Runtime database access uses a separate restricted role. Backups and independent archival provenance are preserved.

## Limitations and immediate next delivery

Worldwide institution identity coverage is broad; reviewed programme coverage is currently a small pilot. The rehearsed French source is historical. Most selected international offerings still lack verified individual university pages and essential academic facts. Directory membership, source identifiers and registry validity must not be presented as current admission availability or verified tuition.

The next delivery should:

1. Run final isolated regressions on the last queue change.
2. Revalidate the frozen source selection, backup and exact import plan.
3. Obtain explicit approval for the bounded development import and any API deployment.
4. If approved, add the validated candidates and publish a database-backed coverage report.
5. Continue institution/page evidence review, then academic enrichment and additional official national sources.

The working pilot and reference directory can be demonstrated today. The international dataset can be demonstrated as a successful isolated import rehearsal. Comprehensive current global Master's discovery, admissions, fees, scholarships and outcomes remain future coverage work.

Technical continuation details: [interrupted recovery](UNISHORTLIST_INTERRUPTED_WORK_RECOVERY.md), [complete handover](UNISHORTLIST_COMPLETE_PROJECT_HANDOVER.md), [execution plan](UNISHORTLIST_GLOBAL_PROGRAMME_EXECUTION_PLAN.md), [source matrix](UNISHORTLIST_SOURCE_COVERAGE_MATRIX.md).

---

## 2026-10-22 UPDATE — INTERNATIONAL IMPORT AND DEPLOYMENT COMPLETE

Full execution record: [interrupted recovery §11](UNISHORTLIST_INTERRUPTED_WORK_RECOVERY.md).

**Both approved operations executed.** The frozen, licence-verified official snapshots were
imported under the pre-approved plan, then the API service alone was redeployed with the
validated code. No migration, no scheduler activation, no Git command.

### Deployed state (independently verified via direct PostgreSQL and the public API)

- **9,349 programmes** — 1 published (the original UAL Master), **9,348 unpublished candidates**.
- **150 canonical institutions** — 149 new, **all pending human review**; the only approved
  institution remains Universidad de Almería.
- **30,328 global ROR directory references** across 223 countries — unchanged, reference only.
- **1,479 archived catalogue records** — unchanged.
- **81,599 evidence rows** across **119 source documents**.
- **7,843 French offerings correctly labelled historical** (`academic_campaign = {"session":"2025"}`);
  **1,501 Dutch offerings** carry official `offering_validity_period`.
- **0 duplicate programme identifiers**; **0** auto-approvals; **0** auto-verified facts;
  **0** auto-publications; fees/requirements/intakes remain **0 / 0 / 0**.
- **Public Discover still exposes only the original published programme**
  (`total_items: 1`) on both the API and NGINX routes; sampled candidates return HTTP 404.
- **Scheduler remains disabled.**
- **Idempotent replay produced zero additions.**

### Coverage claim (be precise)

This is **1,501 Dutch + 7,843 historical French + 5 Spanish Master's offerings** from three
official sources. It is **not** worldwide coverage, and the 30,328 ROR rows are institution
references, not Master's programmes.

### Test baseline

- Backend: **470 passed, 7 opt-in skips** (final file state, isolated stack).
- Frontend: **41 passed**; typecheck, lint and build clean.
- Alembic: single head `9c24a7e6d180`; no new operations.

### Remaining human work

Review 149 pending institutions and 9,344 candidates; reconcile 23 Dutch held providers and
2 French archived UAI identities; handle slug disambiguation before any French publication;
add verified course pages and academic information; extend coverage beyond NL/FR/UAL.
