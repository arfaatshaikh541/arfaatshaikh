# Client Operations Platform

A multi-tenant, modular-monolith SaaS platform for UAE professional-service
businesses (audit, accounting, tax, business setup, corporate services,
consultancies) — lead capture through client operations, sold as configurable
subscription plans rather than bespoke per-customer builds.

See `docs/architecture/` for the full architecture document and the running
project status. This repository is under active milestone-based development;
see `docs/product/project-status.md` for what is built, what is verified, and
what is next.

## Repository layout

```
apps/
  web/            Next.js App Router frontend (TypeScript)
  api/             FastAPI backend (modular monolith)
  worker/           Celery worker + beat (background jobs)
packages/
  ui/              Shared React components
  shared-types/       Shared TS types/enums
  config/           Shared lint/tsconfig/tailwind config
infrastructure/
  docker/           docker-compose.yml, Dockerfiles, Postgres init scripts
  scripts/           migrate/seed/wait-for-it helper scripts
  deployment/         CI/deployment docs
docs/               Architecture, API, database, deployment, security, product, operations docs
```

## Local development

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
2. Start the stack:
   ```bash
   docker compose -f infrastructure/docker/docker-compose.yml up --build
   ```
   This brings up PostgreSQL, Redis, MinIO (S3-compatible storage),
   MailHog (local email capture), the FastAPI backend, the Celery worker,
   and the Next.js frontend.
3. Run migrations:
   ```bash
   ./infrastructure/scripts/migrate.sh
   ```
4. Seed development data (platform admin + demo tenant):
   ```bash
   ./infrastructure/scripts/seed.sh
   ```
5. Open:
   - Web app: http://localhost:3000
   - API docs (dev only): http://localhost:8000/docs
   - MailHog inbox: http://localhost:8025
   - MinIO console: http://localhost:9001

Seeded credentials (development only — see `apps/api/app/db/seed/run.py`):
- Platform admin: `platform-admin@dev.internal` / `ChangeMe!12345`
- Demo tenant `Rafana Advisory Demo` (Growth plan): Tenant Owner
  `owner@rafana-demo.internal` / `ChangeMe!12345`

## Tests

```bash
# Backend
docker compose -f infrastructure/docker/docker-compose.yml exec api pytest

# Frontend
npm run web:lint
npm run web:typecheck
npm run web:build
```

## Documentation

- `docs/architecture/` — architecture overview, ADRs, entity diagrams
- `docs/database/` — ER diagrams, migration/rollback/backup/restore guidance
- `docs/security/` — threat model, OWASP checklist
- `docs/product/project-status.md` — running status: milestone, completed
  work, acceptance criteria, test results, known limitations, next action
