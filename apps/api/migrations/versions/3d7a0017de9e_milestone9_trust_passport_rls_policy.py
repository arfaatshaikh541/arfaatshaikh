"""milestone9 trust passport row level security policies

Revision ID: 3d7a0017de9e
Revises: 0966e5c58635
Create Date: 2026-07-16 07:59:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = '3d7a0017de9e'
down_revision: str | None = '0966e5c58635'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Not the standard _SIMPLE_TENANT_TABLES shape (see Milestone 1's
# `memberships` policy for the precedent this mirrors): SELECT is widened
# so an anonymous request — no `app.current_tenant_id` set at all — can
# still look this row up by its public_slug when is_published is true.
# Once found, the route resolves the row's own tenant_id and calls
# `set_tenant_context` before running any further queries for that
# request, so nothing downstream is ever broadened beyond that one
# tenant. INSERT/UPDATE/DELETE stay strictly tenant-scoped — publishing
# or editing a trust passport always requires being authenticated into
# that exact tenant.


def upgrade() -> None:
    op.execute("ALTER TABLE trust_passport_settings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE trust_passport_settings FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY trust_passport_settings_select ON trust_passport_settings FOR SELECT
        USING (
            tenant_id = app_current_tenant_id()
            OR is_published = true
        )
        """
    )
    op.execute(
        """
        CREATE POLICY trust_passport_settings_insert ON trust_passport_settings FOR INSERT
        WITH CHECK (tenant_id = app_current_tenant_id())
        """
    )
    op.execute(
        """
        CREATE POLICY trust_passport_settings_update ON trust_passport_settings FOR UPDATE
        USING (tenant_id = app_current_tenant_id())
        WITH CHECK (tenant_id = app_current_tenant_id())
        """
    )
    op.execute(
        """
        CREATE POLICY trust_passport_settings_delete ON trust_passport_settings FOR DELETE
        USING (tenant_id = app_current_tenant_id())
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS trust_passport_settings_delete ON trust_passport_settings")
    op.execute("DROP POLICY IF EXISTS trust_passport_settings_update ON trust_passport_settings")
    op.execute("DROP POLICY IF EXISTS trust_passport_settings_insert ON trust_passport_settings")
    op.execute("DROP POLICY IF EXISTS trust_passport_settings_select ON trust_passport_settings")
    op.execute("ALTER TABLE trust_passport_settings NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE trust_passport_settings DISABLE ROW LEVEL SECURITY")
