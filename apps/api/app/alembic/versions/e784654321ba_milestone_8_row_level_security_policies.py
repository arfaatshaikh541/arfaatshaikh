"""milestone 8 row level security policies

Revision ID: e784654321ba
Revises: a8d00229e9e1
Create Date: 2026-07-15 05:50:39.727908

`deadlines` and `portal_accounts` are ordinary tenant-owned tables and
are row-level-secured normally. `portal_invitations`, `portal_sessions`,
and `portal_password_reset_tokens` are intentionally NOT row-level-secured
— the same reasoning already documented for `invitations`/`sessions`/
`password_reset_tokens`: each is looked up only by an unguessable token
hash, before any tenant/portal context exists (a client isn't
authenticated yet when accepting an invitation or logging in, and a
password-reset link is used by someone who, by definition, can't log in
first). Each of these three tables carries its own `tenant_id` column
(the same technique `Invitation.tenant_id` already uses) precisely so
that, once resolved by token, the application can establish RLS context
before touching the row-level-secured `portal_accounts` table — see the
`PortalSession`/`PortalPasswordResetToken` model docstrings.
"""
from collections.abc import Sequence

from alembic import op

revision: str = 'e784654321ba'
down_revision: str | None = 'a8d00229e9e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = [
    "deadlines",
    "portal_accounts",
]

_IS_PLATFORM_ADMIN = "current_setting('app.is_platform_admin', true) = 'true'"
_CURRENT_TENANT = "current_setting('app.current_tenant_id', true)"


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ((tenant_id = NULLIF({_CURRENT_TENANT}, '')::uuid) OR {_IS_PLATFORM_ADMIN})"
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
