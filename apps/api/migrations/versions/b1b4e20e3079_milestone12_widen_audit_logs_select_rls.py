"""milestone12 widen audit logs select rls

Revision ID: b1b4e20e3079
Revises: 63298a015d28
Create Date: 2026-07-16 12:30:36.445830

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = 'b1b4e20e3079'
down_revision: str | None = '63298a015d28'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP POLICY audit_logs_select ON audit_logs")
    op.execute(
        """
        CREATE POLICY audit_logs_select ON audit_logs FOR SELECT
        USING (
            tenant_id = app_current_tenant_id()
            OR app_is_platform_admin()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY audit_logs_select ON audit_logs")
    op.execute(
        """
        CREATE POLICY audit_logs_select ON audit_logs FOR SELECT
        USING (
            tenant_id = app_current_tenant_id()
            OR (tenant_id IS NULL AND app_is_platform_admin())
        )
        """
    )
