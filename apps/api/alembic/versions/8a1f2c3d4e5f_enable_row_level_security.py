"""enable row level security on all tenant-owned tables

Revision ID: 8a1f2c3d4e5f
Revises: 5be9811cd917
Create Date: 2026-07-17 11:00:00.000000

Defense-in-depth tenant isolation: every tenant-owned table gets RLS
enabled + a policy that only allows access to rows whose tenant_id
matches the `app.current_tenant_id` session variable set per-transaction
by `app.core.db.set_tenant_context`, OR when the `app.platform_bypass`
session variable is explicitly set to 'true' by an audited platform-admin
service. Application-layer tenant filtering in repositories remains
mandatory - this is a second, independent layer, not a replacement.

`roles` and `role_permissions` additionally allow rows where tenant_id
IS NULL to be *read* (platform-defined roles/grants, global reference
data) but never *written* by the ordinary app role, since tenant_id IS
NULL is deliberately excluded from the WITH CHECK clause.

`NULLIF(current_setting(...), '')` guards against a real PostgreSQL
gotcha: once a custom GUC like `app.current_tenant_id` has been SET LOCAL
at least once on a session, later transactions on a pooled connection that
never call SET LOCAL again see it revert to '' (empty string), not NULL -
`current_setting(..., true)` only returns NULL for a GUC that has *never*
been set on that connection. Casting '' straight to ::uuid throws a hard
error instead of the intended safe-default-deny; NULLIF converts '' to
NULL first so the comparison is simply false (deny) instead of erroring.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "8a1f2c3d4e5f"
down_revision: str | Sequence[str] | None = "5be9811cd917"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables where tenant_id is NOT NULL - standard tenant isolation policy.
STRICT_TENANT_TABLES = [
    "tenant_settings",
    "memberships",
    "invitations",
    "tenant_subscriptions",
    "tenant_add_ons",
    "feature_overrides",
    "usage_records",
    "credit_wallets",
    "credit_transactions",
    "credit_reservations",
    "audit_logs",
    "support_access_grants",
]

# Tables where tenant_id is nullable (platform-scoped rows have tenant_id
# IS NULL and are readable tenant-wide as global reference data, but never
# insertable/updatable by the ordinary tenant-scoped app role).
NULLABLE_TENANT_TABLES = [
    "roles",
    "role_permissions",
]

CURRENT_TENANT_UUID = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
PLATFORM_BYPASS = "current_setting('app.platform_bypass', true) = 'true'"

USING_CLAUSE_STRICT = f"tenant_id = {CURRENT_TENANT_UUID} OR {PLATFORM_BYPASS}"
CHECK_CLAUSE_STRICT = USING_CLAUSE_STRICT

USING_CLAUSE_NULLABLE = f"tenant_id = {CURRENT_TENANT_UUID} OR tenant_id IS NULL OR {PLATFORM_BYPASS}"
CHECK_CLAUSE_NULLABLE = f"tenant_id = {CURRENT_TENANT_UUID} OR {PLATFORM_BYPASS}"


def upgrade() -> None:
    for table in STRICT_TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({USING_CLAUSE_STRICT}) WITH CHECK ({CHECK_CLAUSE_STRICT})"
        )

    for table in NULLABLE_TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({USING_CLAUSE_NULLABLE}) WITH CHECK ({CHECK_CLAUSE_NULLABLE})"
        )


def downgrade() -> None:
    for table in STRICT_TENANT_TABLES + NULLABLE_TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
