"""milestone15 support access grant requested duration

Revision ID: b967aed623bd
Revises: a33856780d74
Create Date: 2026-07-16 18:23:36.632428

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b967aed623bd'
down_revision: str | None = 'a33856780d74'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'support_access_grants', sa.Column('requested_duration_hours', sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('support_access_grants', 'requested_duration_hours')
