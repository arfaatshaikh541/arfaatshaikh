# GRIDKEEP Cyber OS

**Discover everything. Protect continuously. Respond automatically. Recover confidently. Prove your security.**

A multi-tenant cybersecurity operating system for organisations without deep in-house security
expertise — the control plane, orchestration layer, asset graph, risk engine, automation engine,
incident-response centre, evidence platform, compliance system, and executive command centre sitting
on top of your existing security tools.

This is **Milestone 19: Grant-Gated Incidents Drill-Down** — see
[`docs/project-status.md`](docs/project-status.md) for what's built, what's tested, and what's
known-incomplete.

## Repository layout

```
apps/
  web/      Next.js 14 App Router frontend
  api/      FastAPI modular-monolith backend
  worker/   Celery background worker
packages/
  ui/                    shared component library
  security-contracts/    shared permission/role/module vocabulary (TS + Python)
  config/                shared TS/Tailwind config
  connector-sdk/         provider-neutral connector SDK (Python) + 5 mock connectors
  shared-types/          placeholder — Milestone 2+ housekeeping
infrastructure/
  docker/     Dockerfiles
  scripts/    bootstrap/migrate/seed/wait-for helper scripts
docs/
  project-status.md   running status doc — read this first
```

## Local development

### Prerequisites

- Node.js 20+, pnpm 10+
- Python 3.11+
- PostgreSQL 16, Redis 7 (either via Docker Compose below, or installed locally)

### Option A — Docker Compose

```bash
docker compose up
```

Brings up Postgres, Redis, MinIO (object storage), Mailhog (mail capture), the API (auto-migrates and
seeds the platform catalogue on start), the worker, Celery Beat, and the web app.

> **Note:** this compose file has been syntax-validated (`docker compose config`) but not run
> end-to-end in the environment this was built in (no Docker daemon available there) — see
> `docs/project-status.md`'s Known Limitations. Please verify it end-to-end before relying on it.

### Option B — run services directly

```bash
# 1. Backend
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -e "../../packages/connector-sdk"   # connector SDK + mock connectors
pip install -e ".[dev]"
alembic upgrade head
python -m seed.bootstrap   # platform catalogue (incl. integration/asset-type catalogues) — safe everywhere
python -m seed.demo        # FICTIONAL demo tenant — local/dev only, refuses to run in production
uvicorn main:app --reload

# 2. Worker (separate shell, same venv — apps/worker reuses apps/api's dependencies)
cd apps/api && source .venv/bin/activate
cd ../  # apps/, so the `worker` package resolves
celery -A worker.celery_app worker --loglevel=info -Q default,sync,ingest,correlate,actions,reports
# and, for scheduled tasks:
celery -A worker.celery_app beat --loglevel=info

# 3. Frontend (separate shell)
pnpm install
pnpm --filter @gridkeep/web dev
```

Set `DATABASE_URL` / `DATABASE_MIGRATION_URL` / `REDIS_URL` env vars if not using the defaults in
`apps/api/core/config.py` (which point at `localhost`).

### Demo login

After `python -m seed.demo`, sign in at `http://localhost:3000/login` with any of:

| Email | Role | Password |
|---|---|---|
| `amara.owner@northstar-advisory-demo.gridkeep.example` | Tenant Owner | `Gridkeep-Demo-2026!` |
| `farid.secadmin@northstar-advisory-demo.gridkeep.example` | Security Administrator | `Gridkeep-Demo-2026!` |
| `priya.itadmin@northstar-advisory-demo.gridkeep.example` | IT Administrator | `Gridkeep-Demo-2026!` |
| `daniyar.analyst@northstar-advisory-demo.gridkeep.example` | Security Analyst | `Gridkeep-Demo-2026!` |
| `layla.exec@northstar-advisory-demo.gridkeep.example` | Executive Viewer | `Gridkeep-Demo-2026!` |

All fictional. Do not reuse this password anywhere real.

## Tests

```bash
# Backend — requires a `gridkeep_test` Postgres database (see apps/api/tests/conftest.py)
cd apps/api && source .venv/bin/activate
pytest -q
ruff check .

# Frontend
pnpm --filter @gridkeep/web exec eslint .
pnpm --filter @gridkeep/web exec tsc --noEmit
pnpm --filter @gridkeep/web exec vitest run
pnpm --filter @gridkeep/web build
```

## Documentation

- [`docs/project-status.md`](docs/project-status.md) — current milestone, acceptance criteria, test
  results, architecture decisions, known limitations
