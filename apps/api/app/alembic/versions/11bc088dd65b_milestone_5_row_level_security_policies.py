"""milestone 5 row level security policies

Revision ID: 11bc088dd65b
Revises: 4f265a2eb695
Create Date: 2026-07-14 18:28:10.262748

Every Milestone 5 table is accessed exclusively within an already
tenant-scoped request (`require_module("workflow_automation")` always
runs after `get_tenant_context`) or with `is_platform_admin=true`
explicitly set (the Celery beat workflow-step sweep in
`apps/worker/app/tasks/workflow_automation.py`), so the plain
tenant_id-match policy already used for every other module's tables is
sufficient here too — there is no public/unauthenticated entry point
into this module.
"""
from collections.abc import Sequence

from alembic import op

revision: str = '11bc088dd65b'
down_revision: str | None = '4f265a2eb695'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = [
    "workflows",
    "workflow_steps",
    "workflow_runs",
    "workflow_step_logs",
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
