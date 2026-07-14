# Deployment guidance

This platform has no hard dependency on any single cloud provider —
Docker images for `api`, `worker`, and `web` run anywhere that can run
containers (ECS, Cloud Run, a plain VM with Docker, Kubernetes, etc.).

## Environment configuration

All configuration is via environment variables (see `.env.example` at the
repo root). In production, set every `REQUIRES EXTERNAL CREDENTIAL`
variable to a real value — the repo's defaults only work for local
development and will fail closed (the app refuses to start without
`APP_SECRET_KEY`, `DATABASE_URL`, `MIGRATION_DATABASE_URL`).

## Migrations

Run `alembic upgrade head` (using `MIGRATION_DATABASE_URL`, the
`app_migrator` role) as a **release step before** the new API version
receives traffic — not on every container boot, to avoid multiple
concurrent instances racing to apply the same migration.

```bash
cd apps/api
alembic upgrade head
```

### Rollback

Every migration in this repo implements `downgrade()`. To roll back the
most recent migration:

```bash
alembic downgrade -1
```

Rollback safety notes:
- Migrations that only add tables/columns/indexes/RLS policies are safe
  to roll back at any time (no data loss risk beyond the rolled-back
  schema objects themselves).
- Before rolling back a migration that drops or alters an existing
  column, take a fresh backup first (see below) — `downgrade()` can
  recreate the column but cannot restore data that was already deleted
  by the corresponding `upgrade()`.
- Never roll back across a boundary where application code already
  depends on the newer schema; roll back the application deployment
  first, then the migration.

## Database roles

Production must provision the same two roles as local development
(`infrastructure/docker/postgres/init-roles.sh` shows the exact SQL):

- `app_migrator` — `NOSUPERUSER BYPASSRLS`, owns the schema, used only by
  the migration step.
- `app_runtime` — `NOSUPERUSER NOBYPASSRLS`, used by the API and worker
  at request time, subject to every row-level security policy.

Never run the API or worker as `app_migrator` (or as the database
superuser) in production — doing so silently disables row-level security
for that connection.

## Connection pooling

The API's SQLAlchemy engine (`app/core/db.py`) pools up to
`pool_size + max_overflow` = 30 connections per API process by default.
Multiply by the number of API replicas to size PostgreSQL's
`max_connections` (or, preferably, put PgBouncer — in transaction pooling
mode — in front of Postgres once replica count grows past a handful, so
Postgres itself only sees a small, stable number of backend connections
regardless of API replica count). `SET LOCAL` (used for RLS context) is
compatible with PgBouncer's transaction pooling mode since it's scoped
to a single transaction.

## Encrypted connections

Set `sslmode=require` (or stricter, e.g. `verify-full` with a CA bundle)
in `DATABASE_URL` / `MIGRATION_DATABASE_URL` for any non-local
environment. Most managed Postgres providers (RDS, Cloud SQL, etc.)
enforce this by default.

## Backups

- Use your database provider's automated daily snapshot/backup feature
  (e.g. RDS automated backups, Cloud SQL automated backups) with
  point-in-time recovery (PITR) enabled via WAL archiving — this is the
  standard mechanism for "restore to any point in the last N days," not
  something this application implements itself.
- Retention: keep at least 30 days of PITR-capable backups in
  production; document the exact retention period your compliance
  posture requires (see `docs/security/` — UAE data-retention
  requirements need professional legal review before launch).

## Restore testing

Backups are only as good as the last time you proved you could restore
them. At minimum, quarterly:
1. Restore the latest automated snapshot into a scratch database.
2. Run `alembic upgrade head` against it if it's behind the current
   migration head (should be a no-op if the snapshot is current).
3. Run a read-only smoke test against a few tenant-scoped tables to
   confirm data integrity (row counts roughly match production,
   spot-check a known tenant's records).
4. Record the restore duration — this is your actual RTO (recovery time
   objective), not a documented target.

This process is **not automated** in Milestone 1 — it is operational
documentation for whoever runs this platform in production.

## Health checks

- `GET /healthz` — liveness (process is up). Use for container
  restart/orchestrator liveness probes.
- `GET /readyz` — readiness (process up **and** database reachable). Use
  for load-balancer/orchestrator readiness probes so traffic isn't
  routed to an instance that can't reach Postgres.

## CI/CD

See `.github/workflows/ci.yml` — lints and tests the backend (against a
real ephemeral Postgres + Redis) and the frontend (lint, typecheck, unit
tests, production build) on every push/PR. No deployment step is wired
up yet; add one for your chosen hosting target when ready (this is
intentionally left provider-agnostic per the "no cloud lock-in"
requirement).
