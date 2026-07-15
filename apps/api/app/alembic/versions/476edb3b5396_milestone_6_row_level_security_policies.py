"""milestone 6 row level security policies

Revision ID: 476edb3b5396
Revises: e084e0d7c566
Create Date: 2026-07-15 04:34:11.084333

`proposals` is intentionally NOT row-level-secured, the same reasoning
already used for `tenant_capture_tokens` (which also carries a tenant_id
but has an authenticated, tenant-scoped read path and is still excluded):
the public acceptance page (`GET /public/proposals/{token}`) must resolve
the owning tenant from `proposals.public_token` before any tenant context
exists at all — see `app.modules.proposals.service.get_proposal_by_token`,
which calls `set_rls_context` immediately afterward, mirroring
`tenancy.service.resolve_tenant_by_capture_token`. Every authenticated
read/write path in `ProposalRepository` filters explicitly by `tenant_id`
in the query itself, the same application-level boundary
`tenant_capture_tokens` relies on. `proposal_templates`,
`proposal_template_line_items`, and `proposal_line_items` carry no public
token and are row-level-secured normally.
"""
from collections.abc import Sequence

from alembic import op

revision: str = '476edb3b5396'
down_revision: str | None = 'e084e0d7c566'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = [
    "proposal_templates",
    "proposal_template_line_items",
    "proposal_line_items",
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
