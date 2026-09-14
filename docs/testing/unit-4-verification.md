# Unit 4 verification

This report records commands actually executed for the organisations, RBAC, tenant-isolation and audit-event implementation. It does not claim live PostgreSQL, Redis, Docker or browser verification unless those commands ran successfully.

## Executed checks

- `python -m compileall -q app tests alembic`: passed.
- Focused metadata, tenancy-contract, database-metadata and configuration tests: **8 passed in 0.20s**.
- `alembic upgrade head --sql` using validated development settings: passed and generated 291 lines of PostgreSQL SQL through revision `20260725_0003`.
- The generated SQL includes the composite `fk_memberships_role_organisation` foreign key, preventing a membership from referencing a role owned by another organisation.

## Not executed successfully

- Ruff linting: the `ruff` executable is not installed in this sandbox.
- Live PostgreSQL migration and rollback: no PostgreSQL service or Docker daemon is available.
- End-to-end authenticated API flows: runtime dependencies and backing services are incomplete in this sandbox.
- PostgreSQL RLS behavior: policies are intentionally deferred to the final Milestone 1 hardening unit, when live database verification can be performed.
