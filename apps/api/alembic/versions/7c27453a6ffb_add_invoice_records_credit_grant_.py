"""add invoice_records credit_grant_applied_at

Revision ID: 7c27453a6ffb
Revises: ceb351a49d48
Create Date: 2026-07-19 18:30:11.800791

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c27453a6ffb"
down_revision: str | Sequence[str] | None = "ceb351a49d48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "invoice_records",
        sa.Column("credit_grant_applied_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("invoice_records", "credit_grant_applied_at")
