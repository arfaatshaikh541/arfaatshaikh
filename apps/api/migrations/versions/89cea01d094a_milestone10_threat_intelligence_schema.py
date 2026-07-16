"""milestone10 threat intelligence schema

Revision ID: 89cea01d094a
Revises: 3d7a0017de9e
Create Date: 2026-07-16 08:19:49.330921

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '89cea01d094a'
down_revision: str | None = '3d7a0017de9e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'threat_indicators',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('tenant_integration_id', sa.UUID(), nullable=True),
        sa.Column('external_id', sa.String(length=200), nullable=False),
        sa.Column('indicator_type', sa.String(length=40), nullable=False),
        sa.Column('value', sa.String(length=500), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('source', sa.String(length=80), nullable=False),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['tenant_integration_id'], ['tenant_integrations.id'],
            name=op.f('fk_threat_indicators_tenant_integration_id_tenant_integrations'), ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_threat_indicators')),
        sa.UniqueConstraint('tenant_id', 'external_id', name='uq_threat_indicators_tenant_external_id'),
    )
    op.create_index(op.f('ix_threat_indicators_tenant_id'), 'threat_indicators', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_threat_indicators_value'), 'threat_indicators', ['value'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_threat_indicators_value'), table_name='threat_indicators')
    op.drop_index(op.f('ix_threat_indicators_tenant_id'), table_name='threat_indicators')
    op.drop_table('threat_indicators')
