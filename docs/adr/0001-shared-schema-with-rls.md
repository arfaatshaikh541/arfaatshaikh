# ADR-0001: Single shared PostgreSQL schema with Row Level Security

## Status
Accepted (Milestone 1 approval item #1).

## Context
GRIDKEEP needs strong tenant isolation. The alternatives were: schema-per-
tenant, database-per-tenant, or a single shared schema with tenant_id
columns plus enforcement.

## Decision
Use one shared schema. Every tenant-owned table carries a `tenant_id`
column. Isolation is enforced at two independent layers:
1. Application layer: repositories always filter by a server-derived
   `tenant_id`.
2. Database layer: PostgreSQL Row Level Security policies key off a
   `app.current_tenant_id` session variable, set per-transaction by
   `app.core.db.set_tenant_context`. The runtime application role
   (`gridkeep_app`) has `NOBYPASSRLS`; only the migration role
   (`gridkeep_migrator`) bypasses RLS, and it is never used to serve
   requests.

## Consequences
- Migrations are simpler (one schema, standard Alembic workflow).
- Cross-tenant analytics/reporting (for platform admin) are possible via
  an explicit, audited `set_platform_bypass` escape hatch rather than a
  cross-schema join.
- A single noisy tenant can, in principle, cause lock contention on
  shared tables - mitigated in later milestones by per-tenant concurrency
  limits on background jobs (Milestone 2) and connection pool tuning.
- Requires discipline: every new tenant-owned table must get an RLS
  migration (a CI check for this is a hardening item for Milestone 10,
  not yet built).

## Verified
Cross-tenant read/write attempts were tested directly against the
`gridkeep_app` role, bypassing the API entirely (see
`tests/test_tenant_isolation.py::test_row_level_security_denies_cross_tenant_access_at_the_database_layer`).
