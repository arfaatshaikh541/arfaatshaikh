"""milestone 3 row level security policies

Revision ID: 9fa62b59def2
Revises: c8f73ca17737
Create Date: 2026-07-14 13:28:51.414234

Every Milestone 3 table is accessed exclusively within an already
tenant-scoped request or worker-set context (`require_module("crm" |
"communications")` always runs after `get_tenant_context`; the Celery
beat tasks in `apps/worker/app/tasks/communications.py` explicitly call
`set_rls_context` before touching anything) — so the plain
tenant_id-match policy already used for every Milestone 1/2 table is
sufficient here too.
"""
from collections.abc import Sequence

from alembic import op

revision: str = '9fa62b59def2'
down_revision: str | None = 'c8f73ca17737'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = [
    "scoring_rules",
    "scoring_settings",
    "lead_score_logs",
    "assignment_rules",
    "assignment_rule_round_robin_state",
    "email_templates",
    "email_delivery_logs",
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
