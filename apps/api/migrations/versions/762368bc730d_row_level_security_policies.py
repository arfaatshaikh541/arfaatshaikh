"""row level security policies

Revision ID: 762368bc730d
Revises: 4e8562700b40
Create Date: 2026-07-15 12:22:30.973607

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = '762368bc730d'
down_revision: str | None = '4e8562700b40'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables where a single "tenant_id = current tenant" policy covers every
# command. These are straightforwardly tenant-owned with no pre-tenant-
# context access pattern.
_SIMPLE_TENANT_TABLES = [
    "tenant_settings",
    "tenant_security_profiles",
    "tenant_domains",
    "tenant_subscriptions",
    "tenant_add_ons",
    "tenant_feature_overrides",
    "usage_records",
    "integration_credentials",
    "support_access_grants",
    "trial_grants",
]

# Helper SQL functions wrap `current_setting(..., true)` so every policy
# gets NULL for "not set" — never the empty string. Postgres quirk: a
# custom (undeclared) GUC set via `set_config(name, value, true)` (i.e.
# SET LOCAL semantics) leaves a placeholder behind once the transaction
# that first touched it ends; `current_setting(name, true)` on a *later*
# transaction on the same backend/connection then returns '' rather than
# NULL. A bare `::uuid` cast on '' raises `invalid_text_representation`
# instead of evaluating to NULL, which would incorrectly deny access (or,
# worse, error out) on every request after the first one on a pooled
# connection. `nullif(..., '')` normalises both "never set" and
# "set-then-reverted" to true NULL before the cast.
_HELPER_FUNCTIONS = """
CREATE FUNCTION app_current_tenant_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.current_tenant_id', true), '')::uuid
$$;

CREATE FUNCTION app_current_user_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.current_user_id', true), '')::uuid
$$;

CREATE FUNCTION app_is_platform_admin() RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT coalesce(nullif(current_setting('app.is_platform_admin', true), ''), 'false')::boolean
$$;
"""

_DROP_HELPER_FUNCTIONS = """
DROP FUNCTION IF EXISTS app_is_platform_admin();
DROP FUNCTION IF EXISTS app_current_user_id();
DROP FUNCTION IF EXISTS app_current_tenant_id();
"""


def upgrade() -> None:
    op.execute(_HELPER_FUNCTIONS)

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

    # memberships: SELECT is additionally visible to the authenticated user
    # for their OWN rows (needed to list "which workspaces am I in" before
    # a tenant is selected, e.g. at login). Writes are always strictly
    # tenant-scoped — the "OR self" clause never applies to INSERT/UPDATE/
    # DELETE, so a user can never use their own identity to write into a
    # foreign tenant's membership table.
    op.execute("ALTER TABLE memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memberships FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY memberships_select ON memberships FOR SELECT
        USING (
            tenant_id = app_current_tenant_id()
            OR user_id = app_current_user_id()
        )
        """
    )
    op.execute(
        """
        CREATE POLICY memberships_insert ON memberships FOR INSERT
        WITH CHECK (tenant_id = app_current_tenant_id())
        """
    )
    op.execute(
        """
        CREATE POLICY memberships_update ON memberships FOR UPDATE
        USING (tenant_id = app_current_tenant_id())
        WITH CHECK (tenant_id = app_current_tenant_id())
        """
    )
    op.execute(
        """
        CREATE POLICY memberships_delete ON memberships FOR DELETE
        USING (tenant_id = app_current_tenant_id())
        """
    )

    # audit_logs: append-only. No UPDATE/DELETE policy is defined at all,
    # which under FORCE RLS denies those commands to every role (including
    # the table owner) — this is the database-level backstop for "audit
    # records are append-only" (Rule 25/26), not just an application
    # convention. INSERT permits tenant_id IS NULL because platform-level
    # events (login/logout before a tenant is selected) are recorded with
    # no tenant context at all. SELECT restricts NULL-tenant rows to
    # platform admins.
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_logs_insert ON audit_logs FOR INSERT
        WITH CHECK (
            tenant_id IS NULL
            OR tenant_id = app_current_tenant_id()
        )
        """
    )
    op.execute(
        """
        CREATE POLICY audit_logs_select ON audit_logs FOR SELECT
        USING (
            tenant_id = app_current_tenant_id()
            OR (tenant_id IS NULL AND app_is_platform_admin())
        )
        """
    )

    # invitations intentionally has NO RLS: it is looked up by a unique,
    # high-entropy bearer token BEFORE any tenant context exists (the
    # accept-invitation flow), the same access-control model already used
    # for password_reset_tokens and email_verification_tokens. The token
    # itself — not tenant_id — is the authorization boundary for that read;
    # tenant-scoped writes (creating an invitation) already require
    # `integrations.manage`/`users.manage` and a resolved TenantContext at
    # the application layer.


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_logs_select ON audit_logs")
    op.execute("DROP POLICY IF EXISTS audit_logs_insert ON audit_logs")
    op.execute("ALTER TABLE audit_logs NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS memberships_delete ON memberships")
    op.execute("DROP POLICY IF EXISTS memberships_update ON memberships")
    op.execute("DROP POLICY IF EXISTS memberships_insert ON memberships")
    op.execute("DROP POLICY IF EXISTS memberships_select ON memberships")
    op.execute("ALTER TABLE memberships NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memberships DISABLE ROW LEVEL SECURITY")

    for table in _SIMPLE_TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute(_DROP_HELPER_FUNCTIONS)
