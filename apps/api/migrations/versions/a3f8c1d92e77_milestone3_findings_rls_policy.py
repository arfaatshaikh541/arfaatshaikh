"""milestone3 findings row level security policy

Revision ID: a3f8c1d92e77
Revises: 9ae26aa696dc
Create Date: 2026-07-15 18:40:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = 'a3f8c1d92e77'
down_revision: str | None = '9ae26aa696dc'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same single-policy pattern as Milestone 2's _SIMPLE_TENANT_TABLES —
# findings are ordinary mutable tenant-owned rows (status/assignment
# change over the finding's lifecycle), not an append-only ledger like
# asset_changes/audit_logs, so one tenant_id-scoped policy covering every
# command is sufficient.


def upgrade() -> None:
    op.execute("ALTER TABLE findings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE findings FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY findings_tenant_isolation ON findings
        USING (tenant_id = app_current_tenant_id())
        WITH CHECK (tenant_id = app_current_tenant_id())
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS findings_tenant_isolation ON findings")
    op.execute("ALTER TABLE findings NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE findings DISABLE ROW LEVEL SECURITY")
