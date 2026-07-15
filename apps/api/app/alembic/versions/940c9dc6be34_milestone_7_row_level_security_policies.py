"""milestone 7 row level security policies

Revision ID: 940c9dc6be34
Revises: d71e840aed0d
Create Date: 2026-07-15 05:15:37.358938

`document_requests` is intentionally NOT row-level-secured, the same
reasoning already documented for `proposals` in the Milestone 6 RLS
migration and, before that, for `tenant_capture_tokens`: the public
upload page (`GET /public/documents/{token}`,
`POST /public/documents/{token}/upload`) must resolve the owning tenant
from `document_requests.public_token` before any tenant context exists —
see `app.modules.documents.service.get_request_by_token`, which calls
`set_rls_context` immediately afterward. Every authenticated read/write
path in `DocumentRequestRepository` filters explicitly by `tenant_id` in
the query itself. `documents` (the uploaded files) carries no public
token and is row-level-secured normally, as are all four `onboarding_*`
tables.
"""
from collections.abc import Sequence

from alembic import op

revision: str = '940c9dc6be34'
down_revision: str | None = 'd71e840aed0d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = [
    "documents",
    "onboarding_templates",
    "onboarding_template_steps",
    "onboarding_cases",
    "onboarding_case_steps",
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
