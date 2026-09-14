# World of Islam M20 Deep Fix Report (v3)

## Root causes fixed

1. Python dependency resolution conflict
   - `redis==6.4.0` conflicted with `celery[redis]==5.5.3`.
   - Pinned `redis==5.2.1`.

2. pnpm workspace Docker build
   - The web image previously installed only the web package manifest and omitted workspace package metadata.
   - Docker build now copies and installs the complete workspace before building Next.js.

3. Next.js layout hierarchy
   - Root `<html>` and `<body>` ownership was corrected.
   - Nested locale layout no longer creates a second document root.
   - Standalone output and monorepo output tracing were configured.

4. Fatal PostgreSQL migration 0024
   - `prevent_assistant_audit_mutation()` contained invalid PL/pgSQL: `END $$`.
   - Corrected to `END; $$`.
   - This was a deterministic migration failure and could not be fixed by changing passwords or deleting volumes.

## Validation completed

- Python syntax compilation: passed for API, worker, and all 81 Alembic migrations.
- Alembic revision graph: one root, one head, all 81 revisions connected, no missing revisions.
- Alembic PostgreSQL offline compilation: all 81 migrations compile through head `20260726_0081`.
- Static migration object audit: no duplicate tables, indexes, or relation names detected.
- Static foreign-key ordering audit: no foreign key references a table before its creation.
- Docker Compose YAML parsing: valid.
- TypeScript/TSX syntax audit: passed in prior package validation.

## Environment limitation

This execution environment has no Docker daemon and cannot access npm/PyPI registries. Therefore a live Docker Compose startup could not be executed here. The repository-level errors reproducible from the supplied source were fixed and the complete migration chain was compiled using Alembic's PostgreSQL dialect.

## Required clean start

Use a fresh extracted folder. From the project root:

```powershell
Copy-Item .env.example .env
docker compose down -v --remove-orphans
docker builder prune -a -f
docker compose build --no-cache --progress=plain
docker compose up
```

Deleting volumes is required because an earlier failed migration may have left a partial local database state.
