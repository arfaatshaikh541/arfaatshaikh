"""milestone15 widen support access grants select rls

Revision ID: 43b00c344a03
Revises: b967aed623bd
Create Date: 2026-07-16 18:23:51.997317

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = '43b00c344a03'
down_revision: str | None = 'b967aed623bd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# `support_access_grants` was created under the plain _SIMPLE_TENANT_TABLES
# shape (one combined policy for every command) — fine while every grant
# activated immediately and no one ever needed to look across tenants. A
# genuine second approver needs to discover PENDING grants regardless of
# which tenant they target, so SELECT is widened here the same way
# Milestone 9's trust_passport_settings and Milestone 12's audit_logs
# already were. INSERT/UPDATE/DELETE stay strictly tenant-scoped —
# creating, approving, or revoking a grant always requires the acting
# session to be scoped to that exact tenant (see
# modules.platform_admin.service's use of set_tenant_context).


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS support_access_grants_tenant_isolation ON support_access_grants")
    op.execute(
        """
        CREATE POLICY support_access_grants_select ON support_access_grants FOR SELECT
        USING (
            tenant_id = app_current_tenant_id()
            OR app_is_platform_admin()
        )
        """
    )
    op.execute(
        """
        CREATE POLICY support_access_grants_insert ON support_access_grants FOR INSERT
        WITH CHECK (tenant_id = app_current_tenant_id())
        """
    )
    op.execute(
        """
        CREATE POLICY support_access_grants_update ON support_access_grants FOR UPDATE
        USING (tenant_id = app_current_tenant_id())
        WITH CHECK (tenant_id = app_current_tenant_id())
        """
    )
    op.execute(
        """
        CREATE POLICY support_access_grants_delete ON support_access_grants FOR DELETE
        USING (tenant_id = app_current_tenant_id())
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS support_access_grants_delete ON support_access_grants")
    op.execute("DROP POLICY IF EXISTS support_access_grants_update ON support_access_grants")
    op.execute("DROP POLICY IF EXISTS support_access_grants_insert ON support_access_grants")
    op.execute("DROP POLICY IF EXISTS support_access_grants_select ON support_access_grants")
    op.execute(
        """
        CREATE POLICY support_access_grants_tenant_isolation ON support_access_grants
        USING (tenant_id = app_current_tenant_id())
        WITH CHECK (tenant_id = app_current_tenant_id())
        """
    )
