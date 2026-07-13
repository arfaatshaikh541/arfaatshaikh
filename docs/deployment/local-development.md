# Local Development

## Prerequisites

- Docker + Docker Compose v2
- Node.js 20+ and pnpm 9+ (only needed if running the frontend outside Docker)
- Python 3.12+ and `uv` or `pip` (only needed if running the API outside Docker)

## Quick Start (Docker Compose)

```bash
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local

docker compose -f infrastructure/docker/docker-compose.yml up --build
```

This starts:

| Service   | Port  | Notes |
|-----------|-------|-------|
| web       | 3000  | Next.js dev server |
| api       | 8000  | FastAPI, docs at `/api/docs` (disabled in production) |
| worker    | —     | Celery worker, no exposed port |
| postgres  | 5432  | `leadflow` / `leadflow` / `leadflow` |
| redis     | 6379  | broker + result backend |
| mailhog   | 8025  | web UI to inspect outbound dev emails; SMTP on 1025 |

## Migrations

```bash
docker compose -f infrastructure/docker/docker-compose.yml exec api \
  alembic upgrade head
# or, from apps/api with a local venv:
alembic upgrade head
```

`infrastructure/scripts/migrate.sh` wraps this for CI/deploy use.

## Seed Data

```bash
docker compose -f infrastructure/docker/docker-compose.yml exec api \
  python -m app.seed
```

Creates:
- Platform super admin: `superadmin@leadflow-demo.io` / `SuperAdmin!2026`
- Tenant **Rafana Advisory Demo** (`rafana-advisory-demo`) with Owner,
  Manager and Sales Agent demo users (see `docs/product/` for full demo
  credentials list). All demo data is clearly prefixed `[DEMO]` and uses
  fictional details.

`infrastructure/scripts/seed.sh` wraps this for repeatable use.

## Running Tests

```bash
# Backend
docker compose -f infrastructure/docker/docker-compose.yml exec api \
  pytest

# Frontend
cd apps/web && pnpm test
```

Backend tests use a separate `leadflow_test` database created and torn
down automatically per test session (see `apps/api/tests/conftest.py`); they
never run against the dev database.

## Running Without Docker

Backend:
```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:
```bash
cd apps/web
pnpm install
pnpm dev
```

Worker (imports `app.*` from `apps/api` directly - install both):
```bash
cd apps/api && source .venv/bin/activate  # reuse the API's venv
pip install -e ../worker
cd ../worker
celery -A worker.celery_app worker --loglevel=info
```

## Environment Variables

See `apps/api/.env.example` and `apps/web/.env.example` for the full list.
Nothing sensitive ships with a real default — `SECRET_KEY`,
`REFRESH_TOKEN_SECRET`, and `FIELD_ENCRYPTION_KEY` must be set explicitly;
the app refuses to start with the placeholder example values outside of
`ENVIRONMENT=local`.
