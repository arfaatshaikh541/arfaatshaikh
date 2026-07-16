"""milestone13 mfa challenge tokens

Revision ID: a33856780d74
Revises: b1b4e20e3079
Create Date: 2026-07-16 17:12:10.477270

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a33856780d74'
down_revision: str | None = 'b1b4e20e3079'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'mfa_challenge_tokens',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'], name=op.f('fk_mfa_challenge_tokens_user_id_users'), ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_mfa_challenge_tokens')),
    )
    op.create_index(
        op.f('ix_mfa_challenge_tokens_token_hash'), 'mfa_challenge_tokens', ['token_hash'], unique=True
    )
    op.create_index(
        op.f('ix_mfa_challenge_tokens_user_id'), 'mfa_challenge_tokens', ['user_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_mfa_challenge_tokens_user_id'), table_name='mfa_challenge_tokens')
    op.drop_index(op.f('ix_mfa_challenge_tokens_token_hash'), table_name='mfa_challenge_tokens')
    op.drop_table('mfa_challenge_tokens')
