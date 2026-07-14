"""milestone 2 row level security policies

Revision ID: 45ce592d6cd5
Revises: 235868a48cb8
Create Date: 2026-07-14 12:28:05.671083

Every Milestone 2 table is accessed exclusively within an already
tenant-scoped request (`require_module("lead_capture" | "crm" | "tasks")`
always runs after `get_tenant_context`, which has already set
`app.current_tenant_id`) — none of these have the "must be readable
before a tenant is selected" problem that `memberships`/`tenants`/`roles`
had in Milestone 1. The one exception, public lead capture, resolves its
tenant from a public capture token *before* inserting anything, and
explicitly calls `set_rls_context` with that tenant's id first (see
`app/modules/leads/service.py::capture_public_lead`) — so the plain
tenant_id-match policy below is sufficient for every table here.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "45ce592d6cd5"
down_revision: str | None = "235868a48cb8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = [
    "service_categories",
    "services",
    "qualification_forms",
    "qualification_questions",
    "qualification_options",
    "qualification_answers",
    "custom_field_definitions",
    "custom_field_options",
    "lead_sources",
    "leads",
    "pipelines",
    "pipeline_stages",
    "lead_stage_history",
    "tags",
    "lead_tags",
    "notes",
    "tasks",
    "task_comments",
    "activities",
    "attachments",
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
