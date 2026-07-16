"""milestone11 attack surface domain verification token

Revision ID: 63298a015d28
Revises: fa3d73328a3e
Create Date: 2026-07-16 11:27:19.253702

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '63298a015d28'
down_revision: str | None = 'fa3d73328a3e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('tenant_domains', sa.Column('verification_token', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('tenant_domains', 'verification_token')
