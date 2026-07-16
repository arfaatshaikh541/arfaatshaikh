"""milestone5 incidents row level security policies

Revision ID: c4a8de62f1b3
Revises: 9bb675113760
Create Date: 2026-07-16 04:58:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = 'c4a8de62f1b3'
down_revision: str | None = '9bb675113760'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All three tables are ordinary mutable tenant-owned rows — an incident's
# status/assignment mutate over its lifecycle, and the link tables are
# plain join rows — so a single tenant_id-scoped policy per table is
# sufficient, same pattern as Milestones 2-4. The incident *timeline*
# reuses audit_logs (already RLS-protected as append-only since
# Milestone 1) rather than adding another table here.
_SIMPLE_TENANT_TABLES = ["incidents", "incident_findings", "incident_assets"]


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


def downgrade() -> None:
    for table in _SIMPLE_TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
