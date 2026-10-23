# Catalogue archive/reset operation

## Authorization and verified baseline

The user first authorized rehearsals only on the marked
`uni-shortlist-masters-recovery` database, then explicitly approved the exact
development migration and archived reset below. That operation committed on
2026-10-21. Future operations require their own exact approval. No scheduling,
seeding, ingestion, fact verification, institution approval or program publication
was part of this operation.

Development was independently read and compared with the restored backup on
2026-10-21: database `uni_shortlist`, runtime role `uni_shortlist_app`, revision
`7a3d9f2c1e60`, 19 universities, 79 programs, 415 facts/versions/evidence records,
2 users, 1 profile, 13 jobs and 3 audit events. Every application table's content
fingerprint matched the independent restore proof. Scheduler remains disabled.

## Independent recoverability

The complete custom-format PostgreSQL backup is outside the PostgreSQL volume:

- Repository-private `.db-backups/uni_shortlist_20261021T132903Z.dump` (mode 600).
- SHA-256: `6a7228f2ffcc8ad74cde90a6c6ce97b93d521cfc46610c8474122f6c9a7b6b12`.
- Adjacent `.meta` records the original schema revision; `.restore-proof.json`
  records hashes and counts of all restored application tables.
- An independent `uni-shortlist-masters-recoverability` tmpfs database retains
  the original `7a3d9f2c1e60` schema and complete original catalogue.

These private artifacts contain user data. They are ignored workspace artifacts,
not source files to commit. Preserve them for historical recovery.

## Archive design

Migration `85b2e4a6c910` adds `catalogue_reset_operations` and
`catalogue_archive_records`, with immutable operation metadata and immutable JSONB
row snapshots. Snapshots retain original primary identifiers, original source and
review associations, timestamps, content hashes and reset operation ID. They have
no foreign keys into the deletable catalogue. The archive includes catalogue rows,
facts, versions, evidence, source/document/retrieval context, ingestion context,
institution and source identity reviews, immutable events and audit records.

Existing live review rows gain an archive operation reference and can detach from
deleted universities. Immutable identity/review events and all existing audits
remain live. Active queues exclude archived reviews. Admin audit/archive endpoints
allow interpretation of original associations after deletion. No replacement
approval system or public destructive HTTP endpoint is introduced.

The reset CLI locks inspected application tables within one transaction, compares
all contents with the approved plan, verifies archive payloads before deletion,
checks exact deletion counts and protected row hashes, and rolls back on failure.
It refuses queued/running ingestion, protected student program associations,
unsupported polymorphic links, protected reference links and changed plans.
An identical completed operation ID is an idempotent no-op. Archive downgrade is
refused after archive records exist.

## Exact approved and executed development operation

1. Rebuild and deploy the verified, backward compatible application services.
   Do not recreate PostgreSQL or change its volume.
2. Apply **only** the new migration from current `7a3d9f2c1e60` to
   `85b2e4a6c910` using the guarded development `db-admin` target.
3. Execute the already rehearsed private plan `.db-backups/catalogue-reset.plan.json`:
   - Operation ID: `a0839f88-9fd0-4a57-9499-d86f6d4540b7`.
   - Confirmation SHA-256:
     `d29d0f53568aa5e3e3216957b07caab42bd9adfd2e388066aba3e904fd29bea5`.
   - Archive 1,479 independent records before removing active catalogue rows.
   - Remove 19 universities, 79 programs, 6 campuses, 47 institution identifier
     claims, 70 program identifier claims, 18 fees, 28 admission requirements,
     9 intakes and 3 scholarship program links.
   - Remove 385 catalogue facts and their 385 versions/385 evidence rows.
   - Preserve 30 reference facts and associated versions/evidence: 27 city,
     1 scholarship and 2 subject/country outcome facts. The two outcome records
     have no program/university association and must survive.
   - Preserve both users, roles, the profile, settings, countries/cities, fields,
     scholarships, funding, FX, source registry/documents/retrieval history,
     jobs/job items, all 3 audit events and immutable review events.
   - Retain 13 archived institution review rows and the approved UAL identity
     review, with original university associations recoverable in archive rows.
4. Verify schema, foreign keys, protected hashes, empty active catalogue and
   empty public catalogue; verify archived decisions are readable in admin.

The plan is bound to the exact backup and full table contents. If development
changes, execution must refuse; take/restore a fresh backup and obtain approval
of a newly rehearsed exact plan. Do not edit the confirmation to bypass drift.

The concrete execution interface, with the private backup directory mounted at
the same `/private` path used during rehearsal, is:

```text
python -m app.db.catalogue_reset execute --target development \
  --plan /private/catalogue-reset.plan.json \
  --confirm d29d0f53568aa5e3e3216957b07caab42bd9adfd2e388066aba3e904fd29bea5
```

## Rehearsal evidence

On the explicitly approved marked recovery target:

- Original backup restored and full table fingerprints matched.
- Migration `85b2e4a6c910` applied; Alembic schema check found no model drift.
- Injected post-reset failure rolled back the complete transaction: original
  full table hashes matched and no archive operation remained.
- Exact final plan executed successfully: 0 active universities/programs,
  1,479 archived rows; repeated execution returned `already_applied`.
- Original approved UAL source review, its immutable event and all three audit
  events remain interpretable through original archived identifiers/associations.
- Users, roles, profile, configuration and unrelated reference contents match
  pre-reset hashes; 30 reference facts/versions/evidence remain.
- Independently restored original backup remains available separately.

The older rehearsal report in the private directory has a different preliminary
operation ID. The final plan ID and confirmation above identify the final CLI
rehearsal and the completed development operation. Development now has 0 active
universities/programs and 1,479 archived records; every archive hash and the
protected reference contents were independently rechecked through the runtime role.
