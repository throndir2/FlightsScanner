# Development guide

How to run, test, and work on FlightsScanner locally. See [design.md](./design.md) for the
big picture and [architecture.md](./architecture.md) for the service topology.

## 1. Prerequisites

- **Docker** + **Docker Compose v2** (the only hard requirement to run the full stack).
- For working outside containers (optional):
  - **Node.js 20+** and **npm** for the frontend.
  - **Python 3.12+** for the backend.

## 2. One-command local stack

```bash
cp .env.example .env          # fill in any blanks; defaults work for local
docker compose up --build
```

This starts six services (see [`docker-compose.yml`](../docker-compose.yml)):

| Service | URL / port |
| --- | --- |
| Frontend (Next.js) | http://localhost:3000 |
| Backend (FastAPI) | http://localhost:8000 ( `/docs` for Swagger ) |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |
| Celery worker | (no port) |
| Celery beat | (no port) |

Tear down (keep data): `docker compose down`.
Tear down (wipe volumes): `docker compose down -v`.

## 3. Project layout

```
FlightsScanner/
├── docs/                  # design docs (you are here)
├── backend/               # FastAPI + Celery (Python)
│   └── app/{api,core,models,schemas,services,utils,workers}
├── frontend/              # Next.js (TypeScript)
│   └── src/{app,components,lib,types}
├── docker-compose.yml
├── .github/workflows/ci.yml
├── .env.example
└── README.md
```

A fuller module breakdown is in [architecture.md](./architecture.md#3-backend-module-layout).

## 4. Backend (without Docker)

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt

# Run the API (expects Postgres + Redis reachable; use docker compose for those)
uvicorn app.main:app --reload --port 8000

# Run a Celery worker
celery -A app.workers.celery_app worker --loglevel=info

# Run Beat (periodic scheduler)
celery -A app.workers.celery_app beat --loglevel=info
```

### Database migrations (Alembic)

In Docker, the schema is created automatically on first run via the create_all bootstrap
([`app/prestart.py`](../backend/app/prestart.py)) — no manual step needed. For schema
changes (and production), use Alembic:

```bash
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Migrations use the **sync** database URL; see
[caching-strategy.md](./caching-strategy.md#7-sync-vs-async) and
[database-schema.md](./database-schema.md#6-schema-bootstrap--migrations).

## 5. Frontend (without Docker)

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

Set `NEXT_PUBLIC_API_BASE_URL` (defaults to `http://localhost:8000`) and the NextAuth env
vars in `frontend/.env.local` (see `.env.example`).

## 6. Testing & linting

| Scope | Command |
| --- | --- |
| Backend tests | `cd backend && pytest` |
| Backend lint | `cd backend && ruff check . && ruff format --check .` |
| Backend types | `cd backend && mypy app` |
| Frontend lint | `cd frontend && npm run lint` |
| Frontend types | `cd frontend && npm run typecheck` |

CI runs the same checks on every push/PR — see
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

The most important unit tests cover the pure date logic
([`tests/test_date_logic.py`](../backend/tests/test_date_logic.py)) and the cache-decision
logic ([`tests/test_tasks.py`](../backend/tests/test_tasks.py)).

## 7. Common tasks

| I want to… | Do this |
| --- | --- |
| See API docs | open http://localhost:8000/docs |
| Inspect Redis | `docker compose exec redis redis-cli` then `KEYS price:*` |
| Inspect Postgres | `docker compose exec postgres psql -U flights -d flights` |
| Trigger a refresh manually | `docker compose exec worker python -m app.workers.dev_enqueue <alert_id>` |
| Reset everything | `docker compose down -v && docker compose up --build` |

## 8. Conventions

- **Python:** Ruff for lint+format, type hints required on public functions, `snake_case`.
- **TypeScript:** ESLint + Prettier (via `next lint`), `PascalCase` components,
  `camelCase` functions, colocated component styles via Tailwind.
- **Commits:** conventional-commit style (`feat:`, `fix:`, `docs:`…) recommended.
- **Config:** every new setting goes through `app/core/config.py` (backend) or
  `NEXT_PUBLIC_*` / NextAuth env (frontend), and is documented in `.env.example`.
- **Keep `utils/date_logic.py` pure** — no I/O, so it stays fast and testable.

## 9. Environment variables

See [`.env.example`](../.env.example) for the full annotated list. Highlights:

| Variable | Used by | Purpose |
| --- | --- | --- |
| `POSTGRES_*` | backend, worker, db | DB name/user/password/host. |
| `DATABASE_URL` / `DATABASE_URL_SYNC` | backend, worker | async vs sync DSNs. |
| `REDIS_URL` | backend, worker | broker + cache. |
| `CACHE_TTL_SECONDS` | worker | price cache TTL (default 14400 = 4h). |
| `PROVIDER_DAILY_QUOTA` | worker | per-provider daily call cap. |
| `FLIGHT_PROVIDER` | worker | `mock` (default) or `amadeus`. |
| `SECRET_KEY` | backend | token signing. |
| `NEXTAUTH_SECRET` / `NEXTAUTH_URL` | frontend | NextAuth session. |
| `NEXT_PUBLIC_API_BASE_URL` | frontend | backend base URL. |
