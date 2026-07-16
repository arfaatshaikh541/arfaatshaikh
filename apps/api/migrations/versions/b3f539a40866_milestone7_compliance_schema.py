"""milestone7 compliance schema

Revision ID: b3f539a40866
Revises: c4a8de62f1b3
Create Date: 2026-07-16 07:07:33.343777

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b3f539a40866'
down_revision: str | None = 'c4a8de62f1b3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'compliance_frameworks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=60), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_compliance_frameworks')),
    )
    op.create_index(op.f('ix_compliance_frameworks_key'), 'compliance_frameworks', ['key'], unique=True)

    op.create_table(
        'compliance_controls',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('framework_id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=80), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['framework_id'], ['compliance_frameworks.id'],
            name=op.f('fk_compliance_controls_framework_id_compliance_frameworks'), ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_compliance_controls')),
        sa.UniqueConstraint('framework_id', 'key', name='uq_compliance_controls_framework_key'),
    )
    op.create_index(
        op.f('ix_compliance_controls_framework_id'), 'compliance_controls', ['framework_id'], unique=False
    )

    op.create_table(
        'tenant_control_statuses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('control_id', sa.UUID(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('met', 'partial', 'not_met', 'not_applicable', name='control_status'),
            nullable=False,
        ),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('updated_by_user_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['control_id'], ['compliance_controls.id'],
            name=op.f('fk_tenant_control_statuses_control_id_compliance_controls'), ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['updated_by_user_id'], ['users.id'],
            name=op.f('fk_tenant_control_statuses_updated_by_user_id_users'), ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tenant_control_statuses')),
        sa.UniqueConstraint('tenant_id', 'control_id', name='uq_tenant_control_statuses_pair'),
    )
    op.create_index(
        op.f('ix_tenant_control_statuses_control_id'), 'tenant_control_statuses', ['control_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_tenant_control_statuses_tenant_id'), 'tenant_control_statuses', ['tenant_id'],
        unique=False,
    )

    op.create_table(
        'evidence_records',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('evidence_type', sa.Enum('document', 'url', 'note', name='evidence_type'), nullable=False),
        sa.Column('source_url', sa.String(length=2000), nullable=True),
        sa.Column(
            'target_type',
            sa.Enum('compliance_control', 'incident', name='evidence_target_type'),
            nullable=False,
        ),
        sa.Column('target_id', sa.UUID(), nullable=False),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'], ['users.id'],
            name=op.f('fk_evidence_records_created_by_user_id_users'), ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_evidence_records')),
    )
    op.create_index(op.f('ix_evidence_records_target_id'), 'evidence_records', ['target_id'], unique=False)
    op.create_index(
        op.f('ix_evidence_records_target_type'), 'evidence_records', ['target_type'], unique=False
    )
    op.create_index(op.f('ix_evidence_records_tenant_id'), 'evidence_records', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_evidence_records_tenant_id'), table_name='evidence_records')
    op.drop_index(op.f('ix_evidence_records_target_type'), table_name='evidence_records')
    op.drop_index(op.f('ix_evidence_records_target_id'), table_name='evidence_records')
    op.drop_table('evidence_records')
    op.execute('DROP TYPE IF EXISTS evidence_target_type')
    op.execute('DROP TYPE IF EXISTS evidence_type')

    op.drop_index(op.f('ix_tenant_control_statuses_tenant_id'), table_name='tenant_control_statuses')
    op.drop_index(op.f('ix_tenant_control_statuses_control_id'), table_name='tenant_control_statuses')
    op.drop_table('tenant_control_statuses')
    op.execute('DROP TYPE IF EXISTS control_status')

    op.drop_index(op.f('ix_compliance_controls_framework_id'), table_name='compliance_controls')
    op.drop_table('compliance_controls')

    op.drop_index(op.f('ix_compliance_frameworks_key'), table_name='compliance_frameworks')
    op.drop_table('compliance_frameworks')
