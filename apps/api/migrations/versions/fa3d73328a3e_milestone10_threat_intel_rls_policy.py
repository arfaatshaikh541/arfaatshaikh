"""milestone10 threat intelligence row level security policy

Revision ID: fa3d73328a3e
Revises: 89cea01d094a
Create Date: 2026-07-16 08:22:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = 'fa3d73328a3e'
down_revision: str | None = '89cea01d094a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# threat_indicators is an ordinary tenant-owned row (mutable — last_seen_at
# and confidence get refreshed on re-sync), so the standard single
# tenant-isolation policy is sufficient — no widened/public SELECT the
# way Milestone 9's trust_passport_settings needed.
_SIMPLE_TENANT_TABLES = ["threat_indicators"]


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
