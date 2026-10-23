# University Shortlisting Tool

Evidence-first shortlisting tool for Indian Master's applicants.
Specs in `docs/` are the source of truth (`API_Contract.md`, `Database_Schema.md`, `UI_Flow_and_Routes.md`, `rules.md`).
Progress is tracked only in `docs/UNIVERSITY_SHORTLISTING_PROJECT_STATUS.md`.

## Stack

- Frontend: Vue 3 + TypeScript + Vite + Pinia + Vue Router
- Backend: Python 3.11 + FastAPI + SQLAlchemy 2 + Alembic
- Database: PostgreSQL 16+
- Serving: Docker Compose + NGINX

## Quick start (Docker)

```bash
cp .env.example .env         # edit secrets
docker compose up -d db
docker compose --profile db-admin run --rm -e MIGRATION_TARGET=development db-admin alembic upgrade head   # explicit schema change
docker compose --profile db-admin run --rm -e SEED_TARGET=development db-admin python -m app.db.seed  # explicit demo seed
docker compose up --build    # db + api + web (vite dev on :5173) + nginx SPA on http://localhost:8080 (override host port with WEB_PORT in .env)
```

The API container does not migrate or seed on startup. Its readiness endpoint
reports `schema: not_initialized` until the explicit migration step succeeds.
On a fresh PostgreSQL volume, the init hook creates the least-privilege
`uni_shortlist_app` role from `APP_DB_USER`/`APP_DB_PASSWORD`; the API uses
`APP_DATABASE_URL` for both runtime URL settings. The admin `DATABASE_URL` is
available only to the opt-in `db-admin` service for explicit migration and seed
commands; it is not passed into the long-running API process.
Adding this hook does not change an existing PostgreSQL volume. For an existing
volume that has not been transitioned, take and verify a backup, then review
`scripts/provision-runtime-role.sql` and obtain database-owner approval before
executing it. Set `APP_DATABASE_URL` in the ignored `.env` before restarting the
API. Normal startup never provisions roles or changes existing data.

## Quick start (local dev)

```bash
# backend
cd backend
python -m venv .venv && .venv\Scripts\activate      # or source .venv/bin/activate
pip install -r requirements.txt
set DATABASE_URL=postgresql+psycopg://uni_shortlist:your_local_secret@localhost:5433/uni_shortlist
set APP_DATABASE_URL=postgresql+psycopg://uni_shortlist_app:your_runtime_secret@localhost:5433/uni_shortlist
set MIGRATION_TARGET=development
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
npm install
npm run dev                   # http://localhost:5173, proxies /api to :8000
```

Auth: JWT access + refresh tokens issued as HttpOnly, SameSite=Lax cookies (see `backend/app/core/security.py`).

## Real-data ingestion

The catalogue is filled from registered, permissively licensed public sources by
the ingestion engine in `backend/app/ingestion/`. Nothing is ever invented: a
value that a source does not publish stays unknown.

```bash
cd backend
python -m app.ingestion.cli sources                  # registered connectors + licence/status
python -m app.ingestion.cli run ror --dry-run --limit 50   # validate without writing
python -m app.ingestion.cli run ipeds_hd            # real import
python -m app.ingestion.cli run-all
python -m app.ingestion.cli due --enqueue            # queue refreshes whose interval elapsed
python -m app.ingestion.cli verify                  # query PostgreSQL for actual counts
```

Admins can also queue a refresh with `POST /api/v1/admin/ingestion/run?source_key=<key>`;
the APScheduler worker (`ENABLE_SCHEDULER=true`) picks it up.

## Tests

```bash
# Create/load unique test-only and recovery-only secrets in ignored .env.test.
if [ ! -f .env.test ]; then umask 077; printf 'TEST_DB_PASSWORD=%s\nRECOVERY_DB_PASSWORD=%s\n' "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" > .env.test; fi
set -a; . ./.env.test; set +a
docker compose -f docker-compose.yml -f docker-compose.test.yml --profile test up -d db-test
docker compose -f docker-compose.yml -f docker-compose.test.yml --profile test run --rm test-migrate
docker compose -f docker-compose.yml -f docker-compose.test.yml --profile test run --rm test-seed
docker compose -f docker-compose.yml -f docker-compose.test.yml --profile test run --rm test-runner

# Isolated end-to-end journey through its own NGINX/API/PostgreSQL stack:
docker compose -f docker-compose.yml -f docker-compose.test.yml --profile test up -d api-test nginx-test
# In PowerShell:
# $env:UNISHORTLIST_TEST_MODE='1'; $env:TEST_API_BASE_URL='http://127.0.0.1:8081'
powershell -File scripts/integration-journey.ps1

cd frontend && npm run test && npm run typecheck && npm run build
```

Pytest refuses startup unless `TEST_DATABASE_URL` and `DATABASE_URL` are the
same explicit test URL, test intent is set, and the live database reports the
expected database, role, service and test-only marker. The test stack owns a
separate named volume and private network; it does not mount `pgdata` or publish
PostgreSQL. Test migrations and truncation are guarded against that live marker.
Never set these variables to the development or production database.

## Database backup and recovery

`bash scripts/db-backup.sh` verifies the running development database identity
in a read-only transaction, then writes a logical `pg_dump` and metadata under
`~/.local/share/uni-shortlist/backups` (outside the Compose data volume). Backup
files are mode-restricted and ignored by Git. Supply `RECOVERY_DB_PASSWORD` as
a separate untracked secret, then restore and verify a backup in a disposable
PostgreSQL recovery container with:

```bash
set -a; . ./.env.test; set +a
bash scripts/db-restore-recovery.sh ~/.local/share/uni-shortlist/backups/uni_shortlist_TIMESTAMP.dump
```

The recovery service uses private networking and tmpfs storage. The restore
script checks its database, role and recovery marker before restoring, then
compares the Alembic revision and aggregate counts recorded in backup metadata.
It never targets the development database. Remove the isolated recovery
container after the check with
`docker compose -p uni-shortlist-recovery -f docker-compose.recovery.yml --profile recovery down`;
its tmpfs data is discarded with that container.

Stop the test containers without deleting their persistent isolated test volume:
`docker compose -f docker-compose.yml -f docker-compose.test.yml --profile test down`.
