"""milestone3 findings table

Revision ID: 9ae26aa696dc
Revises: 93d56cc86846
Create Date: 2026-07-15 18:33:20.290648

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '9ae26aa696dc'
down_revision: str | None = '93d56cc86846'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'findings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('rule_key', sa.String(length=80), nullable=False),
        sa.Column('dedup_key', sa.String(length=160), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=40), nullable=False),
        sa.Column(
            'severity', sa.Enum('critical', 'high', 'medium', 'low', name='finding_severity'), nullable=False
        ),
        sa.Column(
            'status',
            sa.Enum(
                'open', 'assigned', 'remediated', 'resolved', 'accepted_risk', 'false_positive',
                name='finding_status',
            ),
            nullable=False,
        ),
        sa.Column('asset_id', sa.UUID(), nullable=False),
        sa.Column('assigned_to_user_id', sa.UUID(), nullable=True),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('first_observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('accepted_risk_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['asset_id'], ['assets.id'], name=op.f('fk_findings_asset_id_assets'), ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['assigned_to_user_id'], ['users.id'],
            name=op.f('fk_findings_assigned_to_user_id_users'), ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_findings')),
        sa.UniqueConstraint('tenant_id', 'dedup_key', name='uq_findings_tenant_dedup_key'),
    )
    op.create_index(op.f('ix_findings_asset_id'), 'findings', ['asset_id'], unique=False)
    op.create_index(op.f('ix_findings_rule_key'), 'findings', ['rule_key'], unique=False)
    op.create_index(op.f('ix_findings_status'), 'findings', ['status'], unique=False)
    op.create_index(op.f('ix_findings_tenant_id'), 'findings', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_findings_tenant_id'), table_name='findings')
    op.drop_index(op.f('ix_findings_status'), table_name='findings')
    op.drop_index(op.f('ix_findings_rule_key'), table_name='findings')
    op.drop_index(op.f('ix_findings_asset_id'), table_name='findings')
    op.drop_table('findings')
    op.execute('DROP TYPE IF EXISTS finding_status')
    op.execute('DROP TYPE IF EXISTS finding_severity')
