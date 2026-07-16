"""milestone5 incidents schema

Revision ID: 9bb675113760
Revises: b7e451f0d3aa
Create Date: 2026-07-16 04:51:53.657993

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '9bb675113760'
down_revision: str | None = 'b7e451f0d3aa'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'incidents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column(
            'severity', sa.Enum('critical', 'high', 'medium', 'low', name='incident_severity'), nullable=False
        ),
        sa.Column(
            'status',
            sa.Enum(
                'declared', 'investigating', 'contained', 'resolved', 'closed', name='incident_status'
            ),
            nullable=False,
        ),
        sa.Column('declared_by_user_id', sa.UUID(), nullable=True),
        sa.Column('assigned_to_user_id', sa.UUID(), nullable=True),
        sa.Column('declared_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closure_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['assigned_to_user_id'], ['users.id'],
            name=op.f('fk_incidents_assigned_to_user_id_users'), ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['declared_by_user_id'], ['users.id'],
            name=op.f('fk_incidents_declared_by_user_id_users'), ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_incidents')),
    )
    op.create_index(op.f('ix_incidents_status'), 'incidents', ['status'], unique=False)
    op.create_index(op.f('ix_incidents_tenant_id'), 'incidents', ['tenant_id'], unique=False)

    op.create_table(
        'incident_assets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('incident_id', sa.UUID(), nullable=False),
        sa.Column('asset_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['asset_id'], ['assets.id'], name=op.f('fk_incident_assets_asset_id_assets'), ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['incident_id'], ['incidents.id'],
            name=op.f('fk_incident_assets_incident_id_incidents'), ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_incident_assets')),
        sa.UniqueConstraint('tenant_id', 'incident_id', 'asset_id', name='uq_incident_assets_pair'),
    )
    op.create_index(op.f('ix_incident_assets_asset_id'), 'incident_assets', ['asset_id'], unique=False)
    op.create_index(op.f('ix_incident_assets_incident_id'), 'incident_assets', ['incident_id'], unique=False)
    op.create_index(op.f('ix_incident_assets_tenant_id'), 'incident_assets', ['tenant_id'], unique=False)

    op.create_table(
        'incident_findings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('incident_id', sa.UUID(), nullable=False),
        sa.Column('finding_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['finding_id'], ['findings.id'],
            name=op.f('fk_incident_findings_finding_id_findings'), ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['incident_id'], ['incidents.id'],
            name=op.f('fk_incident_findings_incident_id_incidents'), ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_incident_findings')),
        sa.UniqueConstraint('tenant_id', 'incident_id', 'finding_id', name='uq_incident_findings_pair'),
    )
    op.create_index(op.f('ix_incident_findings_finding_id'), 'incident_findings', ['finding_id'], unique=False)
    op.create_index(
        op.f('ix_incident_findings_incident_id'), 'incident_findings', ['incident_id'], unique=False
    )
    op.create_index(op.f('ix_incident_findings_tenant_id'), 'incident_findings', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_incident_findings_tenant_id'), table_name='incident_findings')
    op.drop_index(op.f('ix_incident_findings_incident_id'), table_name='incident_findings')
    op.drop_index(op.f('ix_incident_findings_finding_id'), table_name='incident_findings')
    op.drop_table('incident_findings')

    op.drop_index(op.f('ix_incident_assets_tenant_id'), table_name='incident_assets')
    op.drop_index(op.f('ix_incident_assets_incident_id'), table_name='incident_assets')
    op.drop_index(op.f('ix_incident_assets_asset_id'), table_name='incident_assets')
    op.drop_table('incident_assets')

    op.drop_index(op.f('ix_incidents_tenant_id'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_status'), table_name='incidents')
    op.drop_table('incidents')
    op.execute('DROP TYPE IF EXISTS incident_status')
    op.execute('DROP TYPE IF EXISTS incident_severity')
