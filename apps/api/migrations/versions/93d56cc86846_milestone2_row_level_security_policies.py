"""milestone2 row level security policies

Revision ID: 93d56cc86846
Revises: 2f1fafad959a
Create Date: 2026-07-15 17:26:20.038227

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = '93d56cc86846'
down_revision: str | None = '2f1fafad959a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same pattern as Milestone 1's _SIMPLE_TENANT_TABLES — a single
# "tenant_id = app_current_tenant_id()" policy covers every command.
# `integration_catalog` and `asset_types` are deliberately excluded: they
# are platform-wide catalogues (like `modules`/`features`/
# `subscription_plans` in Milestone 1), not tenant-owned data.
_SIMPLE_TENANT_TABLES = [
    "tenant_integrations",
    "integration_health",
    "integration_sync_runs",
    "assets",
    "asset_identifiers",
    "asset_relationships",
    "asset_owners",
    "asset_tags",
]


def upgrade() -> None:
    for table in _SIMPLE_TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id = app_current_tenant_id())
            WITH CHECK (tenant_id = app_current_tenant_id())
            """
        )

    # asset_changes: append-only, same rationale as audit_logs in
    # Milestone 1 — no UPDATE/DELETE policy at all, which under FORCE RLS
    # denies those commands to every role including the table owner. A
    # change-tracking ledger that could be edited after the fact would be
    # worthless as evidence of "what actually changed and when".
    op.execute("ALTER TABLE asset_changes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE asset_changes FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY asset_changes_insert ON asset_changes FOR INSERT
        WITH CHECK (tenant_id = app_current_tenant_id())
        """
    )
    op.execute(
        """
        CREATE POLICY asset_changes_select ON asset_changes FOR SELECT
        USING (tenant_id = app_current_tenant_id())
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS asset_changes_select ON asset_changes")
    op.execute("DROP POLICY IF EXISTS asset_changes_insert ON asset_changes")
    op.execute("ALTER TABLE asset_changes NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE asset_changes DISABLE ROW LEVEL SECURITY")

    for table in _SIMPLE_TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
