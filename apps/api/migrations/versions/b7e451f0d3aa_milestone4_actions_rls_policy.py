"""milestone4 actions row level security policies

Revision ID: b7e451f0d3aa
Revises: 224898b91352
Create Date: 2026-07-15 19:35:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = 'b7e451f0d3aa'
down_revision: str | None = '224898b91352'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same single-policy pattern as Milestones 2 and 3 — all three tables are
# ordinary mutable tenant-owned rows (an ActionRun's status/result mutate
# over its lifecycle, a Playbook can be edited/disabled, an automation
# setting is a single row per tenant that's updated in place), not
# append-only ledgers.
_SIMPLE_TENANT_TABLES = ["playbooks", "tenant_automation_settings", "action_runs"]


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
