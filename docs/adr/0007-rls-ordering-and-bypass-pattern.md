# ADR-0007: RLS tenant-context ordering rule, and the `platform_bypass` escape hatch

## Status
Accepted (discovered and fixed during Milestone 1 implementation).

## Context
While building and testing the RLS-backed tenant isolation from
ADR-0001, three real bugs surfaced from the same root cause: a
tenant-owned (RLS-protected) table was queried *before*
`set_tenant_context` (or, for lookups where the tenant isn't known yet,
`set_platform_bypass`) had been called on that session/transaction. On a
freshly opened connection this reads as zero rows (silently wrong); on a
connection reused from the pool with a stale GUC from a prior request, it
can read as either zero rows or - worse - a different tenant's rows,
depending on what that prior request happened to set.

Concretely:
1. `get_tenant_context` (`app/dependencies.py`) checked the caller's
   `Membership` row before calling `set_tenant_context`.
2. `switch_active_tenant` (`app/modules/tenancy/services.py`) checked
   membership in the *target* tenant before scoping to it.
3. Invitation-accept and support-access-grant lookups key off a globally
   unique opaque token/id, so there is no tenant to scope to *until after*
   the row is found - RLS as originally written made these lookups always
   return nothing.
4. A duplicated `get_db` dependency (one in `app/dependencies.py`, one in
   `app/core/db.py`) meant a single HTTP request could end up using two
   *different* database sessions/connections: one that had
   `set_tenant_context` applied (inside the auth dependency chain) and a
   separate one for the route body's own queries, which never got the
   GUC set at all.

## Decision
- **Ordering rule**: `set_tenant_context` (or `set_platform_bypass`) must
  be the first thing that happens in any service function, before any
  query against an RLS-protected table - never after a "does this row
  exist" check on that same protected table.
- **Single `get_db`**: there is exactly one `get_db` dependency
  (`app.core.db.get_db`), imported everywhere - `app/dependencies.py` no
  longer defines its own copy. FastAPI's dependency caching then
  guarantees one `AsyncSession` per request, shared by the whole
  dependency graph and the route body.
- **`set_platform_bypass` is for narrowly-scoped, unique-key lookups
  only**: invitation-accept-by-token, support-access-grant-by-id, and
  "list my own memberships across tenants" (login's auto-tenant-selection,
  the tenant-switcher UI) all call it, each justified in a code comment
  at the call site, and each still filtered to a single row or to
  `user_id == the authenticated caller`- never a bulk, attacker-influenced
  cross-tenant scan.
- The RLS policy expression also had to change from
  `tenant_id = current_setting('app.current_tenant_id', true)::uuid` to
  `tenant_id = NULLIF(current_setting(...), '')::uuid` - PostgreSQL
  reverts a custom GUC to `''` (not NULL) once it has been `SET LOCAL`
  at least once on a connection and the transaction ends, and casting
  `''::uuid` throws a hard error instead of the intended safe-default-deny.

## Consequences
- `tests/test_tenant_isolation.py` and the tenancy/permission test suite
  now pass reliably (they did not before this fix - see the session
  transcript for the exact failures this uncovered).
- Every new service function that touches an RLS-protected table must be
  reviewed against this ordering rule; this is a manual discipline today,
  not a linted/enforced one (a hardening item for Milestone 10).
