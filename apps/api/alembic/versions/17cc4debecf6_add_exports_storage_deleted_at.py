"""add exports storage_deleted_at

Revision ID: 17cc4debecf6
Revises: 7c27453a6ffb
Create Date: 2026-07-19 18:47:49.785095

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "17cc4debecf6"
down_revision: str | Sequence[str] | None = "7c27453a6ffb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "exports", sa.Column("storage_deleted_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("exports", "storage_deleted_at")
