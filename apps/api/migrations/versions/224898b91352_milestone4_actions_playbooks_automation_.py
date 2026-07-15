"""milestone4 actions playbooks automation settings

Revision ID: 224898b91352
Revises: a3f8c1d92e77
Create Date: 2026-07-15 19:27:32.127065

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '224898b91352'
down_revision: str | None = 'a3f8c1d92e77'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'playbooks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('rule_key', sa.String(length=80), nullable=False),
        sa.Column('action_key', sa.String(length=80), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'], ['users.id'],
            name=op.f('fk_playbooks_created_by_user_id_users'), ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_playbooks')),
    )
    op.create_index(op.f('ix_playbooks_rule_key'), 'playbooks', ['rule_key'], unique=False)
    op.create_index(op.f('ix_playbooks_tenant_id'), 'playbooks', ['tenant_id'], unique=False)

    op.create_table(
        'tenant_automation_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column(
            'mode',
            sa.Enum('observe', 'guided', 'balanced', 'autopilot', 'lockdown', name='automation_mode'),
            nullable=False,
        ),
        sa.Column('updated_by_user_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['updated_by_user_id'], ['users.id'],
            name=op.f('fk_tenant_automation_settings_updated_by_user_id_users'), ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tenant_automation_settings')),
        sa.UniqueConstraint('tenant_id', name='uq_tenant_automation_settings_tenant'),
    )
    op.create_index(
        op.f('ix_tenant_automation_settings_tenant_id'), 'tenant_automation_settings', ['tenant_id'], unique=False
    )

    op.create_table(
        'action_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('action_key', sa.String(length=80), nullable=False),
        sa.Column('provider_id', sa.String(length=80), nullable=False),
        sa.Column('safety_class', sa.Integer(), nullable=False),
        sa.Column('tenant_integration_id', sa.UUID(), nullable=False),
        sa.Column('asset_id', sa.UUID(), nullable=False),
        sa.Column('finding_id', sa.UUID(), nullable=True),
        sa.Column('playbook_id', sa.UUID(), nullable=True),
        sa.Column('trigger', sa.Enum('manual', 'playbook', name='action_trigger'), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'pending_approval', 'approved', 'rejected', 'running', 'succeeded', 'failed',
                name='action_run_status',
            ),
            nullable=False,
        ),
        sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('requested_by_user_id', sa.UUID(), nullable=True),
        sa.Column('approved_by_user_id', sa.UUID(), nullable=True),
        sa.Column('result_message', sa.Text(), nullable=True),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['approved_by_user_id'], ['users.id'],
            name=op.f('fk_action_runs_approved_by_user_id_users'), ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['asset_id'], ['assets.id'], name=op.f('fk_action_runs_asset_id_assets'), ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['finding_id'], ['findings.id'],
            name=op.f('fk_action_runs_finding_id_findings'), ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['playbook_id'], ['playbooks.id'],
            name=op.f('fk_action_runs_playbook_id_playbooks'), ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['requested_by_user_id'], ['users.id'],
            name=op.f('fk_action_runs_requested_by_user_id_users'), ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_integration_id'], ['tenant_integrations.id'],
            name=op.f('fk_action_runs_tenant_integration_id_tenant_integrations'), ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_action_runs')),
    )
    op.create_index(op.f('ix_action_runs_asset_id'), 'action_runs', ['asset_id'], unique=False)
    op.create_index(op.f('ix_action_runs_finding_id'), 'action_runs', ['finding_id'], unique=False)
    op.create_index(op.f('ix_action_runs_status'), 'action_runs', ['status'], unique=False)
    op.create_index(op.f('ix_action_runs_tenant_id'), 'action_runs', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_action_runs_tenant_id'), table_name='action_runs')
    op.drop_index(op.f('ix_action_runs_status'), table_name='action_runs')
    op.drop_index(op.f('ix_action_runs_finding_id'), table_name='action_runs')
    op.drop_index(op.f('ix_action_runs_asset_id'), table_name='action_runs')
    op.drop_table('action_runs')
    op.execute('DROP TYPE IF EXISTS action_run_status')
    op.execute('DROP TYPE IF EXISTS action_trigger')

    op.drop_index(op.f('ix_tenant_automation_settings_tenant_id'), table_name='tenant_automation_settings')
    op.drop_table('tenant_automation_settings')
    op.execute('DROP TYPE IF EXISTS automation_mode')

    op.drop_index(op.f('ix_playbooks_tenant_id'), table_name='playbooks')
    op.drop_index(op.f('ix_playbooks_rule_key'), table_name='playbooks')
    op.drop_table('playbooks')
