"""Create platform metadata foundation.

Revision ID: 20260725_0001
Revises: None
Create Date: 2026-07-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_metadata",
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_platform_metadata"),
        sa.UniqueConstraint("key", name="uq_platform_metadata_key"),
    )
    op.create_index("ix_platform_metadata_key", "platform_metadata", ["key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_platform_metadata_key", table_name="platform_metadata")
    op.drop_table("platform_metadata")
