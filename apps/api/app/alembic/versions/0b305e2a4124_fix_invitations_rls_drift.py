"""fix invitations rls drift

Revision ID: 0b305e2a4124
Revises: e784654321ba
Create Date: 2026-07-15 12:16:56.949056

Corrective, idempotent migration: `invitations` was always documented
and intended to be excluded from row-level security (see
`57bf2768a62d_row_level_security_policies.py`'s module docstring —
"is only ever looked up by an unguessable, cryptographically random
token hash... this codebase has no tenant-scoped 'list invitations'
read path"), matching the same reasoning already applied to
`sessions`, `password_reset_tokens`, `document_requests`,
`proposals.public_token`, and the Milestone 8 portal token tables.

No migration in this codebase's history ever enabled RLS on
`invitations` — yet it was found enabled (`FORCE ROW LEVEL SECURITY`
with a `tenant_isolation` policy) against a live database, which
silently broke every staff invitation-acceptance request: the lookup
in `identity.service.accept_invitation` runs before any tenant RLS
context can exist (the invitee has no session yet), so a forced,
tenant-scoped policy makes the query fail closed and return nothing
even for a genuine, unused, unexpired invitation — confirmed live via
a real invite -> accept round-trip that returned `404 not_found`
despite the row provably existing with a matching token hash. This
migration is the drift's actual root fix: it restores `invitations` to
the state every migration and every piece of documentation already
says it should be in, and is a safe no-op (`DROP POLICY IF EXISTS`,
`DISABLE ROW LEVEL SECURITY` are both idempotent) anywhere the drift
never occurred.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0b305e2a4124"
down_revision: str | None = "e784654321ba"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON invitations")
    op.execute("ALTER TABLE invitations NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invitations DISABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # Deliberately not restoring RLS on invitations — that state was a
    # drift/bug, never an intended configuration, so there is nothing
    # correct to roll back to.
    pass
