"""Milestone 10 hardening: an automated guard against the exact risk
ADR-0001 and ADR-0007 both named as "a hardening item for Milestone 10,
not yet built" - that RLS discipline in this codebase is enforced by
manual review, not by anything automated, so a future tenant-owned table
could ship without RLS (or with a broken policy) and nothing would catch
it before it reached production.

Rather than a hardcoded table list (which would silently stop covering
new tables the moment someone forgets to update it - exactly the
"manual discipline" problem this test exists to remove), every check
here introspects the real Postgres schema directly: any table in the
`public` schema with a `tenant_id` column is treated as tenant-owned and
must have RLS enabled, forced, and a policy whose `USING`/`WITH CHECK`
clauses both actually enforce tenant matching (not just "a policy
exists" - a `USING (true)` policy would pass a naive existence check
while providing no real protection at all).

Deliberately structural, not behavioral, for coverage across every
table: `conftest.py`'s `reset_database` fixture truncates every
tenant-owned table before each test runs (cascading from `tenants`), so
a runtime "does a context-less session see zero rows" check would pass
vacuously here - the tables are empty regardless of whether RLS works.
Verifying the actual policy clause text is the stronger guarantee
anyway: `tenant_id = NULLIF(current_setting('app.current_tenant_id',
true), '') OR platform_bypass` is structurally incapable of returning
any row to a session with neither GUC set (`NULLIF(...)` is NULL,
`tenant_id = NULL` is never TRUE, and the bypass GUC defaults unset) -
that's a proof from the SQL itself, not an empirical observation that
could be coincidentally right. The *behavioral* proof - real
cross-tenant data, a real context-less session, confirmed zero rows -
already exists for a representative table in
`test_tenant_isolation.py::test_row_level_security_denies_cross_tenant_access_at_the_database_layer`;
this file complements it with the schema-wide structural coverage that
test was never meant to provide.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.helpers import migrator_asyncpg_url

pytestmark = pytest.mark.asyncio

# `platform_audit_logs.tenant_id` is a nullable, informational FK
# ("which tenant did this platform action target"), not a
# tenant-ownership column - this table is deliberately platform-only,
# visible exclusively to platform admins via application-layer
# permission checks (see app.modules.audit.models.PlatformAuditLog's
# own docstring split from the tenant-scoped AuditLog). It is the one
# legitimate, deliberate exception to "a tenant_id column means RLS is
# required" - every other table with a tenant_id column in this schema
# is genuinely tenant-owned.
_DELIBERATELY_NOT_RLS_PROTECTED = {"platform_audit_logs"}


async def _tenant_owned_tables_and_rls_state() -> list[dict]:
    engine = create_async_engine(migrator_asyncpg_url())
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT
                        c.relname AS table_name,
                        c.relrowsecurity AS rls_enabled,
                        c.relforcerowsecurity AS rls_forced,
                        (
                            SELECT count(*) FROM pg_policies p
                            WHERE p.schemaname = 'public' AND p.tablename = c.relname
                        ) AS policy_count
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relkind = 'r'
                      AND EXISTS (
                          SELECT 1 FROM information_schema.columns col
                          WHERE col.table_schema = 'public'
                            AND col.table_name = c.relname
                            AND col.column_name = 'tenant_id'
                      )
                    ORDER BY c.relname
                    """
                )
            )
            rows = [dict(row._mapping) for row in result]
    finally:
        await engine.dispose()
    return rows


async def _policy_clauses_for_table(table_name: str) -> list[tuple[str, str, str]]:
    """Returns (policyname, qual, with_check) for every policy on
    `table_name` - both clauses matter: `USING` alone would let a session
    with no context read nothing (good) but a missing `WITH CHECK` would
    let it *write* a row claiming any tenant_id it likes."""
    engine = create_async_engine(migrator_asyncpg_url())
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    "SELECT policyname, qual, with_check FROM pg_policies "
                    "WHERE schemaname = 'public' AND tablename = :table_name"
                ),
                {"table_name": table_name},
            )
            rows = [(r[0], r[1], r[2]) for r in result]
    finally:
        await engine.dispose()
    return rows


async def test_every_tenant_owned_table_has_rls_enabled_and_forced():
    tables = await _tenant_owned_tables_and_rls_state()
    assert tables, "expected at least one tenant-owned table - did introspection break?"

    failures = []
    for row in tables:
        name = row["table_name"]
        if name in _DELIBERATELY_NOT_RLS_PROTECTED:
            continue
        if not row["rls_enabled"]:
            failures.append(f"{name}: RLS is not ENABLEd")
        if not row["rls_forced"]:
            failures.append(f"{name}: RLS is not FORCEd (table owner could bypass it)")
        if row["policy_count"] < 1:
            failures.append(f"{name}: no RLS policy exists")

    assert not failures, (
        "Tenant-owned table(s) missing real RLS protection - every table with a "
        "tenant_id column needs ENABLE ROW LEVEL SECURITY + FORCE ROW LEVEL SECURITY "
        "+ a tenant_isolation policy in its migration (see docs/adr/0001):\n"
        + "\n".join(failures)
    )


async def test_every_rls_policy_actually_enforces_tenant_matching():
    """Guards against a policy that exists but doesn't protect anything -
    e.g. `CREATE POLICY ... USING (true)` would satisfy "a policy exists"
    while granting every session unrestricted access. Both `USING` (gates
    reads/updates/deletes) and `WITH CHECK` (gates inserts/the new row of
    an update) must reference both the tenant-matching comparison and the
    platform_bypass escape hatch - the exact clause ADR-0007 established
    and every migration since has copied verbatim."""
    tables = await _tenant_owned_tables_and_rls_state()
    failures = []

    for row in tables:
        name = row["table_name"]
        if name in _DELIBERATELY_NOT_RLS_PROTECTED:
            continue
        policies = await _policy_clauses_for_table(name)
        if not policies:
            continue  # already reported by the other test

        for policy_name, qual, with_check in policies:
            for clause_name, clause in (("USING", qual), ("WITH CHECK", with_check)):
                if clause is None:
                    failures.append(f"{name}.{policy_name}: {clause_name} clause is empty")
                    continue
                if "current_setting('app.current_tenant_id'" not in clause:
                    failures.append(
                        f"{name}.{policy_name}: {clause_name} clause does not reference "
                        f"app.current_tenant_id - got: {clause}"
                    )
                if "current_setting('app.platform_bypass'" not in clause:
                    failures.append(
                        f"{name}.{policy_name}: {clause_name} clause does not reference "
                        f"app.platform_bypass - got: {clause}"
                    )

    assert not failures, "RLS polic(ies) exist but don't actually enforce tenant isolation:\n" + "\n".join(
        failures
    )
