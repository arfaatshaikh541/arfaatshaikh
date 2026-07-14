"""row level security policies

Revision ID: 57bf2768a62d
Revises: 1a62ff428104
Create Date: 2026-07-14 11:18:09.843418

Enables PostgreSQL row-level security on every tenant-owned table as a
defence-in-depth layer behind the application's own tenant-context
authorization (see app/dependencies/tenant.py). The API always runs as
the `app_runtime` role (NOSUPERUSER, NOBYPASSRLS); Alembic always runs as
`app_migrator` (BYPASSRLS), so these policies never block migrations.

Every policy allows access when either:
  (a) the row's tenant_id matches `app.current_tenant_id`, a Postgres
      session-local variable set by the API for the duration of each
      request (via `set_config(..., is_local=true)`), or
  (b) `app.is_platform_admin` is 'true' — set only for authenticated
      platform-admin requests, and only after backend authorization has
      already verified `users.is_platform_admin`.

`memberships` additionally allows a row through when its `user_id`
matches `app.current_user_id` — set for every authenticated request
regardless of tenant (see app/dependencies/auth.py). This is required
because "which tenants am I a member of" must be answerable *before* a
tenant has been selected (login, tenant-switch), i.e. before
`app.current_tenant_id` has anything meaningful in it. Scoping this
extra branch to "rows belonging to me" cannot expose another user's
memberships.

`invitations` is intentionally NOT row-level-secured: it is only ever
looked up by an unguessable, cryptographically random token hash (the
token itself is the authorization proof, e.g. accepting an invitation
happens before the invitee has any session at all), and this codebase
has no tenant-scoped "list invitations" read path. `sessions`,
`email_verification_tokens`, `password_reset_tokens`, and
`login_attempts` follow the same reasoning and were never added here.

`audit_logs` is read-restricted the same way as the other tenant-owned
tables, but INSERT is intentionally left unrestricted (`WITH CHECK
(true)`, via a separate FOR INSERT policy). Audit entries are written
from many code paths — including fully public, pre-authentication ones
like password reset and email verification — where no tenant has been
selected and `tenant_id` is legitimately NULL (a platform-level event).
`tenant_id` on an audit row is always assigned by trusted application
code, never taken from client input, so relaxing the INSERT check does
not weaken isolation; it only ensures the immutable audit trail can
never silently fail to record an event because of the very security
layer meant to protect it.

All three custom GUCs default to unset ('') when not explicitly set by
the API, which safely resolves to "no access" — fail closed, not fail
open.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "57bf2768a62d"
down_revision: str | None = "1a62ff428104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables whose access is governed purely by a `tenant_id` column.
_TENANT_ID_TABLES = [
    "tenant_settings",
    "tenant_domains",
    "memberships",
    "tenant_subscriptions",
    "tenant_feature_overrides",
    "tenant_add_ons",
    "usage_records",
    "support_access_logs",
    "feature_change_logs",
]

_IS_PLATFORM_ADMIN = "current_setting('app.is_platform_admin', true) = 'true'"
_CURRENT_TENANT = "current_setting('app.current_tenant_id', true)"
_CURRENT_USER = "current_setting('app.current_user_id', true)"


def _enable_and_policy(table: str, using_clause: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        f"USING ({using_clause})"
    )


def upgrade() -> None:
    for table in _TENANT_ID_TABLES:
        _enable_and_policy(
            table,
            f"(tenant_id = NULLIF({_CURRENT_TENANT}, '')::uuid) OR {_IS_PLATFORM_ADMIN}",
        )

    # Permissive policies combine with OR, so this adds "or it's my own
    # membership row" on top of the tenant_isolation policy just created.
    op.execute(
        "CREATE POLICY own_membership_rows ON memberships "
        f"USING (user_id = NULLIF({_CURRENT_USER}, '')::uuid)"
    )

    # audit_logs: reads are tenant-restricted like everything else above;
    # inserts are unrestricted (see module docstring).
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_select ON audit_logs FOR SELECT "
        f"USING ((tenant_id = NULLIF({_CURRENT_TENANT}, '')::uuid) OR {_IS_PLATFORM_ADMIN})"
    )
    op.execute("CREATE POLICY unrestricted_insert ON audit_logs FOR INSERT WITH CHECK (true)")

    # A tenant row is visible if it's the currently-active tenant, if the
    # caller has *any* active membership in it (needed to enumerate a
    # user's tenants at login and tenant-switch time, before one has been
    # selected as "active"), or to platform admins. Membership itself is
    # the real authorization boundary here — this table only carries
    # name/slug/status, not tenant-owned business data.
    _enable_and_policy(
        "tenants",
        f"(id = NULLIF({_CURRENT_TENANT}, '')::uuid) OR {_IS_PLATFORM_ADMIN} OR EXISTS ("
        f"SELECT 1 FROM memberships m WHERE m.tenant_id = tenants.id "
        f"AND m.user_id = NULLIF({_CURRENT_USER}, '')::uuid AND m.status = 'ACTIVE'"
        f")",
    )

    # Roles: tenant-scoped roles are visible to their own tenant, or to a
    # user who holds that exact role (needed at login/tenant-switch time,
    # before a tenant has been selected, to resolve "what is my role
    # called in each of my tenants" — the same chicken-and-egg as
    # `tenants` above). NULL-tenant rows are system role *templates* (not
    # directly assignable to a membership) and remain visible to everyone
    # so the platform-admin "create tenant" workflow can read them.
    _enable_and_policy(
        "roles",
        f"(tenant_id IS NULL) OR (tenant_id = NULLIF({_CURRENT_TENANT}, '')::uuid) OR {_IS_PLATFORM_ADMIN} OR EXISTS ("
        f"SELECT 1 FROM memberships m WHERE m.role_id = roles.id "
        f"AND m.user_id = NULLIF({_CURRENT_USER}, '')::uuid AND m.status = 'ACTIVE'"
        f")",
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS own_membership_rows ON memberships")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_select ON audit_logs")
    op.execute("DROP POLICY IF EXISTS unrestricted_insert ON audit_logs")
    op.execute("ALTER TABLE audit_logs NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY")
    for table in [*_TENANT_ID_TABLES, "tenants", "roles"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
