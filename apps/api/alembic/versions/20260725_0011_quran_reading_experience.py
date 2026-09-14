"""quran reading experience

Revision ID: 20260725_0011
Revises: 20260725_0010
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_0011"
down_revision = "20260725_0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("quran_bookmarks",
        sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("ayah_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.String(500), nullable=True), sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ayah_id"],["quran_ayahs.id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id","ayah_id"))
    op.create_index("ix_quran_bookmarks_user_created","quran_bookmarks",["user_id","created_at"])
    op.create_index(op.f("ix_quran_bookmarks_user_id"),"quran_bookmarks",["user_id"])
    op.create_table("quran_reading_progress",
        sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("ayah_id", sa.Uuid(), nullable=False),
        sa.Column("translation_edition_id", sa.Uuid(), nullable=True), sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ayah_id"],["quran_ayahs.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["translation_edition_id"],["quran_translation_editions.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id"))
    op.create_index(op.f("ix_quran_reading_progress_user_id"),"quran_reading_progress",["user_id"])


def downgrade():
    op.drop_table("quran_reading_progress")
    op.drop_table("quran_bookmarks")
