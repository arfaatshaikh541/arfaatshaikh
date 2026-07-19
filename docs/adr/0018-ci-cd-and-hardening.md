# ADR-0018: CI/CD pipeline and RLS/route hardening

## Status
Accepted.

## Context
Unlike Milestones 3-7 (spelled out in the captured architecture) or
Milestone 9 (spelled out in ADR-0006's explicit deferral), no spec text
named Milestone 10 directly. Two independent ADRs did, though: ADR-0001
and ADR-0007 each ended their Consequences/Unresolved-risks sections with
"a CI check for this is a hardening item for Milestone 10, not yet
built" - one about RLS migration coverage, one about the RLS
context-ordering rule. `docs/project-status.md`'s own "Known limitations"
list carried a matching, more general item: "No CI/CD pipeline yet.
GitHub Actions workflows (lint/test/build/scan on push) have not been
created." A third, related unresolved risk (ADR-0014's route-shadowing
bug class, hit once by hand and only guarded by a single regression test
for that one instance) fit the same "hardening, explicitly named as
follow-up, not yet built" shape closely enough to include here rather
than leave it the sole remaining loose end of its kind.

## Decision

### GitHub Actions CI/CD pipeline (`.github/workflows/ci.yml`)
Five jobs, matching exactly the verification commands run by hand at the
end of every milestone in this project's history so far, so CI can never
silently diverge from what "done" has actually meant this whole time:
`api` (ruff, mypy, `alembic upgrade head`, `alembic check`, pytest -
against real `postgres`/`redis` service containers, using
`infrastructure/scripts/setup-local-db.sh` unmodified rather than a
CI-specific role/database setup, so CI and local dev can never drift
apart), `worker` (same shape), `connector-sdk` (no database needed),
`web` (ESLint, `tsc --noEmit`, `next build`), and `security-scan`
(`pip-audit` against each Python package's locked dependencies via `uv
export --no-emit-workspace`, `pnpm audit --audit-level high` for the
frontend - advisory (`continue-on-error: true`), not a merge gate, since
a scanner flagging a transitive CVE with no available fix yet shouldn't
block every PR by itself).

**What was verified, and what wasn't**: every individual command the
workflow runs was executed for real against real services (a real
Postgres role/database setup via the actual shared script, a real Redis
instance, real `pip-audit`/`pnpm audit` runs against this project's
actual locked dependencies - both came back clean) before being written
into the YAML. The *composed* workflow itself was never executed by
GitHub Actions - this sandbox has no reachable Docker daemon (the same
gap `docs/project-status.md`'s known-limitations list disclosed for
Docker Compose in Milestone 1), so a local `act`-based dry run wasn't
possible either. This is the same class of
disclosed gap as every other "verified the parts, not the whole" note in
this project (Google Places, the SSRF crawler, Stripe) - the first real
run of this workflow against a genuine GitHub Actions runner is the
remaining thing to confirm.

### RLS coverage check (`apps/api/tests/test_rls_coverage.py`) - closes ADR-0001's named gap
Rather than a hardcoded table list (which would stop covering new tables
the moment someone forgets to update it - exactly the problem being
solved), this introspects the real Postgres schema directly: every table
in `public` with a `tenant_id` column must have RLS enabled, forced, and
a policy whose `USING`/`WITH CHECK` clauses both actually reference
tenant matching and the `platform_bypass` escape hatch - not just "a
policy exists" (a `USING (true)` policy would pass a naive existence
check while protecting nothing). `platform_audit_logs` is the one
deliberate exception - its `tenant_id` is an informational nullable FK
("which tenant did this platform action target"), not a tenant-ownership
column; the table is intentionally platform-only, gated by application-
layer permission checks, never RLS. Both tests were verified to actually
catch a real regression, not just pass vacuously: temporarily running
`ALTER TABLE leads NO FORCE ROW LEVEL SECURITY` and replacing its policy
with `USING (true) WITH CHECK (true)` against the real test database
made both tests fail with exactly the expected message, then both passed
again once reverted.

### Why no schema-wide "zero rows with no context set" runtime test
The obvious complement to the structural check above - seed real data,
open a session with no tenant context, assert zero rows, for every
table - was considered and rejected: `conftest.py`'s `reset_database`
fixture truncates every tenant-owned table before each test (cascading
from `tenants`), so that check would pass on every table regardless of
whether RLS actually worked, since the tables are simply empty already.
The structural check above is the *stronger* guarantee here - the
policy clause `tenant_id = NULLIF(current_setting('app.current_tenant_id',
true), '') OR platform_bypass` is provably incapable of returning a row
to a context-less session by the logic of the SQL itself (`NULLIF(...)`
is NULL when unset, `tenant_id = NULL` is never TRUE, and the bypass GUC
defaults unset), not an empirical observation that could coincidentally
be right for the wrong reason. The genuine behavioral proof - real
cross-tenant data, a real context-less session, confirmed zero rows -
already exists for one representative table in
`test_tenant_isolation.py`; this file adds the schema-wide structural
coverage that test never claimed to provide.

### Route-shadowing regression test (`apps/api/tests/test_route_ordering.py`) - closes the ADR-0014 unresolved risk
The exact bug class that hit this codebase twice by hand (ADR-0014's
`/leads/bulk/status`, ADR-0016's `/integrations/{id}/push/bulk`) is now
guarded generically: the test introspects the real, fully-assembled
FastAPI app's route table (flattening FastAPI's `_IncludedRouter`
wrapper objects back to the real, registration-ordered `APIRoute` list -
this FastAPI version doesn't expose a flat list directly) and flags any
pair of routes, sharing an HTTP method, whose path templates differ in
exactly one segment where one has a literal and the other a parameter -
unless the literal one is registered first, the way Starlette's
matching (first registered match wins) requires for it to ever be
reachable. Verified against synthetic route pairs reproducing both the
known-bad order (correctly flagged) and the actual fixed order (correctly
passes) before being trusted against the real app.

## Consequences
- New: `.github/workflows/ci.yml`, `apps/api/tests/test_rls_coverage.py`
  (2 tests), `apps/api/tests/test_route_ordering.py` (1 test). No
  production code changed - this milestone is entirely tooling and test
  coverage.
- `docs/project-status.md`'s "No CI/CD pipeline yet" limitation is
  closed; the "RLS discipline is manual today" limitation is narrowed
  (the *coverage* half - every tenant-owned table actually has real RLS
  - is now automated; the *ordering* half - a future service function
  correctly calling `set_tenant_context` before its first query - is
  still a manual-discipline risk, since that's a call-site ordering
  property no schema-introspection test can verify).
- The route-shadowing test is generic, not a per-instance regression
  test - it will catch a *third* recurrence of ADR-0014/ADR-0016's bug
  class anywhere in the app, not just re-verify the two already-fixed
  instances.
- The CI workflow itself has not been run by GitHub Actions in this
  environment (see "What was verified, and what wasn't" above) -
  treat it as unverified-in-composition until its first real run.
