"""milestone24 mfa backup codes

Revision ID: 79ca74767833
Revises: 0b0479a26ade
Create Date: 2026-07-17 07:30:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '79ca74767833'
down_revision: str | None = '0b0479a26ade'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'mfa_backup_codes',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'], name=op.f('fk_mfa_backup_codes_user_id_users'), ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_mfa_backup_codes')),
    )
    op.create_index(
        op.f('ix_mfa_backup_codes_code_hash'), 'mfa_backup_codes', ['code_hash'], unique=True
    )
    op.create_index(
        op.f('ix_mfa_backup_codes_user_id'), 'mfa_backup_codes', ['user_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_mfa_backup_codes_user_id'), table_name='mfa_backup_codes')
    op.drop_index(op.f('ix_mfa_backup_codes_code_hash'), table_name='mfa_backup_codes')
    op.drop_table('mfa_backup_codes')
