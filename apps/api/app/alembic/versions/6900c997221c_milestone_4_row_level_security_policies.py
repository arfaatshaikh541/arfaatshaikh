"""milestone 4 row level security policies

Revision ID: 6900c997221c
Revises: 25ca81e21512
Create Date: 2026-07-14 18:00:54.729824

Every Milestone 4 table is accessed exclusively within an already
tenant-scoped request (`require_module("booking")` always runs after
`get_tenant_context`) or with `is_platform_admin=true` explicitly set
(the Celery beat appointment-reminder sweep). The one exception, public
booking, resolves its tenant from the same capture token public lead
capture uses and explicitly calls `set_rls_context` immediately after —
see `app/modules/booking/service.py::book_public_appointment` — so the
plain tenant_id-match policy already used for every other module's
tables is sufficient here too.
"""
from collections.abc import Sequence

from alembic import op

revision: str = '6900c997221c'
down_revision: str | None = '25ca81e21512'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = [
    "appointment_types",
    "staff_availability",
    "availability_exceptions",
    "appointments",
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
