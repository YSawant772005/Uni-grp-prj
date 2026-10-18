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
docker compose up --build    # db + api + web (vite dev) on http://localhost:8080 (nginx)
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

## Tests

```bash
cd backend && pytest          # integration tests need DATABASE_URL (disposable DB!)
cd frontend && npm run test && npm run type-check && npm run build
```
