"""harden tenant and append-only security boundaries

Revision ID: 20260725_0004
Revises: 20260725_0003
Create Date: 2026-07-25
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260725_0004"
down_revision: str | None = "20260725_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("roles", "memberships", "support_access_grants", "audit_events", "security_events")


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION prevent_event_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'append-only event tables cannot be updated or deleted';
        END;
        $$
        """
    )
    for table in ("audit_events", "security_events"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_event_mutation()"
        )

    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY roles_tenant_policy ON roles
        USING (organisation_id = NULLIF(current_setting('app.current_organisation_id', true), '')::uuid)
        WITH CHECK (organisation_id = NULLIF(current_setting('app.current_organisation_id', true), '')::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY memberships_access_policy ON memberships
        USING (
          user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
          OR organisation_id = NULLIF(current_setting('app.current_organisation_id', true), '')::uuid
        )
        WITH CHECK (organisation_id = NULLIF(current_setting('app.current_organisation_id', true), '')::uuid)
        """
    )
    for table in ("support_access_grants", "audit_events", "security_events"):
        op.execute(
            f"CREATE POLICY {table}_tenant_policy ON {table} "
            "USING (organisation_id = NULLIF(current_setting('app.current_organisation_id', true), '')::uuid) "
            "WITH CHECK (organisation_id = NULLIF(current_setting('app.current_organisation_id', true), '')::uuid)"
        )


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_policy ON {table}")
        if table == "memberships":
            op.execute("DROP POLICY IF EXISTS memberships_access_policy ON memberships")
        if table == "roles":
            op.execute("DROP POLICY IF EXISTS roles_tenant_policy ON roles")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for table in ("security_events", "audit_events"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS prevent_event_mutation()")
