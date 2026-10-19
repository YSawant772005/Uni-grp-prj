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
docker compose up --build    # db + api + web (vite dev on :5173) + nginx SPA on http://localhost:8080 (override host port with WEB_PORT in .env)
```

## Quick start (local dev)

```bash
# backend
cd backend
python -m venv .venv && .venv\Scripts\activate      # or source .venv/bin/activate
pip install -r requirements.txt
set DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/uni_shortlist
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
cd backend && pytest          # integration tests need DATABASE_URL (disposable DB!)
cd frontend && npm run test && npm run typecheck && npm run build

# end-to-end API journey through NGINX (requires: docker compose up -d; reads WEB_PORT from .env)
powershell -File scripts/integration-journey.ps1
```
