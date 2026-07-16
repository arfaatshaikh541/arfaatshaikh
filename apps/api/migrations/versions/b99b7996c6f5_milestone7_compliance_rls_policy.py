"""milestone7 compliance row level security policies

Revision ID: b99b7996c6f5
Revises: b3f539a40866
Create Date: 2026-07-16 07:15:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = 'b99b7996c6f5'
down_revision: str | None = 'b3f539a40866'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# compliance_frameworks and compliance_controls are platform-wide
# catalogue tables (same role as asset_types) — every tenant reads the
# same rows, so they deliberately get NO RLS policy, same as asset_types.
_SIMPLE_TENANT_TABLES = ["tenant_control_statuses", "evidence_records"]


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
