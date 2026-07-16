"""milestone9 trust passport schema

Revision ID: 0966e5c58635
Revises: b99b7996c6f5
Create Date: 2026-07-16 07:56:54.280350

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0966e5c58635'
down_revision: str | None = 'b99b7996c6f5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'trust_passport_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('is_published', sa.Boolean(), nullable=False),
        sa.Column('public_slug', sa.String(length=60), nullable=True),
        sa.Column('headline', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('show_compliance_frameworks', sa.Boolean(), nullable=False),
        sa.Column('updated_by_user_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['updated_by_user_id'], ['users.id'],
            name=op.f('fk_trust_passport_settings_updated_by_user_id_users'), ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_trust_passport_settings')),
        sa.UniqueConstraint('tenant_id', name='uq_trust_passport_settings_tenant'),
    )
    op.create_index(
        op.f('ix_trust_passport_settings_public_slug'), 'trust_passport_settings', ['public_slug'],
        unique=True,
    )
    op.create_index(
        op.f('ix_trust_passport_settings_tenant_id'), 'trust_passport_settings', ['tenant_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_trust_passport_settings_tenant_id'), table_name='trust_passport_settings')
    op.drop_index(op.f('ix_trust_passport_settings_public_slug'), table_name='trust_passport_settings')
    op.drop_table('trust_passport_settings')
