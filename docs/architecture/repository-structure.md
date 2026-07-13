# Repository Structure

```
apps/
  api/                          FastAPI backend
    app/
      core/                     config, security, permissions catalog, logging
      db/                       SQLAlchemy engine/session, base model
      models/                   SQLAlchemy ORM models (one module per aggregate)
      schemas/                  Pydantic request/response schemas
      repositories/             tenant-scoped DB access, no business logic
      services/                 business logic, orchestrates repositories
      api/
        deps.py                 shared FastAPI dependencies (auth, tenant, permission)
        routes/                 one router module per resource
      workers_client/           thin helpers to enqueue Celery tasks from the API
      main.py                   app factory, middleware, router mounting
    alembic/                    migrations
    tests/                      pytest suite (unit + integration + isolation + authz)
    pyproject.toml
    Dockerfile

  worker/                       Celery worker (shares app.* package with api via editable install)
    app -> ../api/app           (installed as a dependency, see worker/pyproject.toml)
    worker/
      celery_app.py
      tasks/
    Dockerfile

  web/                          Next.js App Router frontend
    src/
      app/                      routes: (public), (auth), (tenant), (platform)
      components/
      lib/                      API client, query client, auth helpers
      hooks/
    package.json
    Dockerfile

packages/
  shared-types/                 TS types/zod schemas shared by web (and future admin apps)
  config/                       shared tsconfig/eslint/tailwind presets
  ui/                           shared React components (Button, Input, Table, etc.)

infrastructure/
  docker/
    docker-compose.yml
    postgres/
    mailhog/ (uses official image, no custom build)
  scripts/
    migrate.sh
    seed.sh

docs/
  architecture/
  api/
  deployment/
  security/
  product/

.github/workflows/ci.yml
```

## Backend Layering Rule

`routes -> services -> repositories -> models`. A route never imports a
model or the DB session directly for a write; it calls a service. A
service never writes raw SQL/ORM queries; it calls a repository. This is
what makes the tenant-isolation guarantee auditable: every DB touch for a
tenant-owned table happens inside `app/repositories/*`, so a reviewer only
has to check that folder for correct `tenant_id` scoping.

## Why `worker` depends on `api`'s app package

Rather than duplicate models/services, the worker installs `apps/api` as a
local editable dependency (see `apps/worker/pyproject.toml`) and imports
`app.services...` / `app.db...` directly. This avoids drift between what
the API believes the schema is and what the worker believes it is.
