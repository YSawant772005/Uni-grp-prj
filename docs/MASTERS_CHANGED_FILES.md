# Files changed during the Master’s implementation

Inventory relative to the saved source checkpoint at the start of this implementation.
No Git command was used. Earlier unrelated workspace files were not changed.

For manual commit boundaries, see [the implementation report](MASTERS_IMPLEMENTATION_REPORT.md).

## Migration

- [backend/alembic/versions/85b2e4a6c910_catalogue_provenance_archive.py](../backend/alembic/versions/85b2e4a6c910_catalogue_provenance_archive.py)

## Backend

- [backend/app/core/scheduler.py](../backend/app/core/scheduler.py)
- [backend/app/db/catalogue_reset.py](../backend/app/db/catalogue_reset.py)
- [backend/app/ingestion/__init__.py](../backend/app/ingestion/__init__.py)
- [backend/app/ingestion/adapters/duo_rio.py](../backend/app/ingestion/adapters/duo_rio.py)
- [backend/app/ingestion/adapters/ipeds.py](../backend/app/ingestion/adapters/ipeds.py)
- [backend/app/ingestion/adapters/monmaster.py](../backend/app/ingestion/adapters/monmaster.py)
- [backend/app/ingestion/adapters/ror.py](../backend/app/ingestion/adapters/ror.py)
- [backend/app/ingestion/adapters/ual.py](../backend/app/ingestion/adapters/ual.py)
- [backend/app/ingestion/adapters/webpage.py](../backend/app/ingestion/adapters/webpage.py)
- [backend/app/ingestion/cache.py](../backend/app/ingestion/cache.py)
- [backend/app/ingestion/cli.py](../backend/app/ingestion/cli.py)
- [backend/app/ingestion/normalize.py](../backend/app/ingestion/normalize.py)
- [backend/app/ingestion/persist.py](../backend/app/ingestion/persist.py)
- [backend/app/ingestion/pipeline.py](../backend/app/ingestion/pipeline.py)
- [backend/app/ingestion/types.py](../backend/app/ingestion/types.py)
- [backend/app/main.py](../backend/app/main.py)
- [backend/app/models/__init__.py](../backend/app/models/__init__.py)
- [backend/app/models/archive.py](../backend/app/models/archive.py)
- [backend/app/models/identity.py](../backend/app/models/identity.py)
- [backend/app/routers/v1/admin.py](../backend/app/routers/v1/admin.py)
- [backend/app/routers/v1/health.py](../backend/app/routers/v1/health.py)
- [backend/app/routers/v1/recommendations.py](../backend/app/routers/v1/recommendations.py)
- [backend/app/services/admin.py](../backend/app/services/admin.py)
- [backend/app/services/archive.py](../backend/app/services/archive.py)
- [backend/app/services/catalog.py](../backend/app/services/catalog.py)
- [backend/app/services/costs.py](../backend/app/services/costs.py)
- [backend/app/services/eligibility.py](../backend/app/services/eligibility.py)
- [backend/app/services/fact_projection.py](../backend/app/services/fact_projection.py)
- [backend/app/services/library.py](../backend/app/services/library.py)
- [backend/app/services/program_evidence.py](../backend/app/services/program_evidence.py)
- [backend/app/services/recommendations.py](../backend/app/services/recommendations.py)
- [backend/app/services/review_readiness.py](../backend/app/services/review_readiness.py)
- [backend/app/services/source_urls.py](../backend/app/services/source_urls.py)

## Backend tests

- [backend/tests/test_admin.py](../backend/tests/test_admin.py)
- [backend/tests/test_catalogue_reset.py](../backend/tests/test_catalogue_reset.py)
- [backend/tests/test_ingestion.py](../backend/tests/test_ingestion.py)
- [backend/tests/test_ingestion_live.py](../backend/tests/test_ingestion_live.py)
- [backend/tests/test_masters_readiness.py](../backend/tests/test_masters_readiness.py)
- [backend/tests/test_refresh_reliability.py](../backend/tests/test_refresh_reliability.py)
- [backend/tests/test_reviewed_facts.py](../backend/tests/test_reviewed_facts.py)

## Frontend

- [frontend/src/features/admin/AdminHomeView.vue](../frontend/src/features/admin/AdminHomeView.vue)
- [frontend/src/features/admin/AuditView.vue](../frontend/src/features/admin/AuditView.vue)
- [frontend/src/features/admin/FactDetailView.vue](../frontend/src/features/admin/FactDetailView.vue)
- [frontend/src/features/admin/IdentityReviewView.vue](../frontend/src/features/admin/IdentityReviewView.vue)
- [frontend/src/features/admin/InstitutionReviewView.vue](../frontend/src/features/admin/InstitutionReviewView.vue)
- [frontend/src/features/admin/ProgramPublicationView.vue](../frontend/src/features/admin/ProgramPublicationView.vue)
- [frontend/src/features/admin/SourceDetailView.vue](../frontend/src/features/admin/SourceDetailView.vue)
- [frontend/src/features/program-detail/ProgramDetailView.vue](../frontend/src/features/program-detail/ProgramDetailView.vue)
- [frontend/src/services/api/admin.ts](../frontend/src/services/api/admin.ts)
- [frontend/src/tests/institution-review.test.ts](../frontend/src/tests/institution-review.test.ts)
- [frontend/src/types/api.ts](../frontend/src/types/api.ts)

## Operator and browser tools

- [scripts/db-restore-recovery.sh](../scripts/db-restore-recovery.sh)
- [scripts/prepare-masters-browser.py](../scripts/prepare-masters-browser.py)
- [scripts/verify-masters-browser.mjs](../scripts/verify-masters-browser.mjs)

## Documentation

- [docs/API_Contract.md](../docs/API_Contract.md)
- [docs/CATALOGUE_ARCHIVE_RESET_RUNBOOK.md](../docs/CATALOGUE_ARCHIVE_RESET_RUNBOOK.md)
- [docs/Database_Schema.md](../docs/Database_Schema.md)
- [docs/MASTERS_CHANGED_FILES.md](../docs/MASTERS_CHANGED_FILES.md)
- [docs/MASTERS_IMPLEMENTATION_REPORT.md](../docs/MASTERS_IMPLEMENTATION_REPORT.md)
- [docs/UNIVERSITY_SHORTLISTING_PROJECT_STATUS.md](../docs/UNIVERSITY_SHORTLISTING_PROJECT_STATUS.md)
