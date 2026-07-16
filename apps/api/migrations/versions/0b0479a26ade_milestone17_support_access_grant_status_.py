"""milestone17 support access grant status enum

Revision ID: 0b0479a26ade
Revises: 43b00c344a03
Create Date: 2026-07-16 19:16:31.750924

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0b0479a26ade'
down_revision: str | None = '43b00c344a03'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# `SUPPORT_ACCESS_STATUSES` (modules.platform_admin.models) has existed
# since Milestone 15 but was never consulted anywhere, including by the
# column it was presumably meant to constrain — `status` has been a plain
# `String(20)` since Milestone 1, unlike every sibling status column in the
# codebase (finding_status, incident_status, tenant_integration_status,
# tenant_status, automation_mode) which are all real Postgres enums.
# `worker.tasks.expire_support_access_grants` has always written only
# `"pending"`/`"active"`/`"expired"`/`"revoked"`, so this cast is safe
# against existing data with no backfill needed.

_ENUM_NAME = "support_access_grant_status"
_ENUM_VALUES = ("pending", "active", "expired", "revoked")


def upgrade() -> None:
    status_enum = sa.Enum(*_ENUM_VALUES, name=_ENUM_NAME)
    status_enum.create(op.get_bind())
    op.execute(
        f"ALTER TABLE support_access_grants "
        f"ALTER COLUMN status TYPE {_ENUM_NAME} USING status::{_ENUM_NAME}"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE support_access_grants ALTER COLUMN status TYPE VARCHAR(20) USING status::text")
    sa.Enum(name=_ENUM_NAME).drop(op.get_bind())
