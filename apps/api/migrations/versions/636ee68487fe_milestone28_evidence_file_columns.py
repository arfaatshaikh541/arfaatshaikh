"""milestone28 evidence file columns

Revision ID: 636ee68487fe
Revises: 79ca74767833
Create Date: 2026-07-17 08:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '636ee68487fe'
down_revision: str | None = '79ca74767833'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("evidence_records", sa.Column("file_path", sa.String(length=600), nullable=True))
    op.add_column("evidence_records", sa.Column("file_name", sa.String(length=300), nullable=True))
    op.add_column("evidence_records", sa.Column("file_content_type", sa.String(length=200), nullable=True))
    op.add_column("evidence_records", sa.Column("file_size_bytes", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("evidence_records", "file_size_bytes")
    op.drop_column("evidence_records", "file_content_type")
    op.drop_column("evidence_records", "file_name")
    op.drop_column("evidence_records", "file_path")
