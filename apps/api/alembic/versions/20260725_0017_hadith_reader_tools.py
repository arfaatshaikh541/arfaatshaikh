"""hadith reader tools

Revision ID: 20260725_0017
Revises: 20260725_0016
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_0017"
down_revision = "20260725_0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("hadith_bookmarks",
        sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("narration_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True), sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["narration_id"],["hadith_narrations.id"],ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id","narration_id"))
    op.create_index("ix_hadith_bookmarks_user_id", "hadith_bookmarks", ["user_id"])
    op.create_index("ix_hadith_bookmarks_narration_id", "hadith_bookmarks", ["narration_id"])
    op.create_table("hadith_reading_history",
        sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("narration_id", sa.Uuid(), nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=False), sa.Column("read_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["narration_id"],["hadith_narrations.id"],ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id","narration_id"))
    op.create_index("ix_hadith_reading_history_user_id", "hadith_reading_history", ["user_id"])
    op.create_index("ix_hadith_reading_history_narration_id", "hadith_reading_history", ["narration_id"])
    op.create_index("ix_hadith_history_user_last_read", "hadith_reading_history", ["user_id","last_read_at"])
    op.create_table("hadith_citation_exports",
        sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("narration_id", sa.Uuid(), nullable=False), sa.Column("format", sa.String(20), nullable=False), sa.Column("payload_sha256", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("format IN ('json','csv','plain_text')", name="ck_hadith_citation_exports_format"), sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["narration_id"],["hadith_narrations.id"],ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_hadith_citation_exports_user_id", "hadith_citation_exports", ["user_id"])
    op.create_index("ix_hadith_citation_exports_narration_id", "hadith_citation_exports", ["narration_id"])


def downgrade():
    op.drop_table("hadith_citation_exports")
    op.drop_table("hadith_reading_history")
    op.drop_table("hadith_bookmarks")
