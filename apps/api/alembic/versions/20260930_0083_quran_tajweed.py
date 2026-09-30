"""Tajweed rule catalogue and per-ayah rule spans (quran.ws corpus, CC-BY-4.0)."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260930_0083"
down_revision = "20260929_0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    now = sa.text("now()")
    op.create_table(
        "quran_tajweed_rules",
        sa.Column("rule_id", sa.String(120), primary_key=True),
        sa.Column("topic_id", sa.String(80), nullable=False),
        sa.Column("topic_label_ar", sa.String(200), nullable=False),
        sa.Column("hukum_id", sa.String(120), nullable=False),
        sa.Column("label_ar", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
    )
    op.create_table(
        "quran_ayah_tajweed",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ayah_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quran_ayahs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("marked_text", sa.Text(), nullable=False),
        sa.Column("spans_json", sa.Text(), nullable=False),
        sa.Column("corpus_version", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("quran_ayah_tajweed")
    op.drop_table("quran_tajweed_rules")
