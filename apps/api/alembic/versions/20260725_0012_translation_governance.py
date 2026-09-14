"""translation governance and reader preferences

Revision ID: 20260725_0012
Revises: 20260725_0011
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_0012"
down_revision = "20260725_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("quran_translation_import_batches",
        sa.Column("translation_edition_id", sa.Uuid(), nullable=False), sa.Column("manifest_version", sa.String(32), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False), sa.Column("expected_ayah_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), server_default="draft", nullable=False), sa.Column("submitted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("validation_summary", sa.Text(), nullable=True), sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("expected_ayah_count > 0", name="ck_quran_translation_import_batches_expected_count"),
        sa.CheckConstraint("status IN ('draft','validated','review_pending','approved','rejected','published','failed')", name="ck_quran_translation_import_batches_status"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"],["users.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["translation_edition_id"],["quran_translation_editions.id"],ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_quran_translation_import_batches_edition_status", "quran_translation_import_batches", ["translation_edition_id","status"])
    op.create_table("quran_translation_import_ayahs",
        sa.Column("import_batch_id", sa.Uuid(), nullable=False), sa.Column("ayah_id", sa.Uuid(), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=False), sa.Column("text_sha256", sa.String(64), nullable=False),
        sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("validation_status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("validation_errors", sa.Text(), nullable=True), sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("validation_status IN ('pending','valid','invalid')", name="ck_quran_translation_import_ayahs_validation"),
        sa.ForeignKeyConstraint(["ayah_id"],["quran_ayahs.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["import_batch_id"],["quran_translation_import_batches.id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_passage_id"],["source_passages.id"],ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_batch_id","ayah_id"))
    op.create_table("quran_translation_import_reviews",
        sa.Column("import_batch_id", sa.Uuid(), nullable=False), sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(24), nullable=False), sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("decision IN ('approved','changes_requested','rejected')", name="ck_quran_translation_import_reviews_decision"),
        sa.ForeignKeyConstraint(["import_batch_id"],["quran_translation_import_batches.id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"],["users.id"],ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_batch_id","reviewer_user_id"))
    op.create_table("quran_reader_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("translation_edition_id", sa.Uuid(), nullable=True),
        sa.Column("show_translation", sa.Boolean(), server_default="true", nullable=False), sa.Column("arabic_font_scale", sa.Integer(), server_default="100", nullable=False),
        sa.Column("theme", sa.String(16), server_default="system", nullable=False), sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("arabic_font_scale BETWEEN 80 AND 200", name="ck_quran_reader_preferences_font_scale"),
        sa.CheckConstraint("theme IN ('system','light','dark','sepia')", name="ck_quran_reader_preferences_theme"),
        sa.ForeignKeyConstraint(["translation_edition_id"],["quran_translation_editions.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id"))
    op.create_index(op.f("ix_quran_reader_preferences_user_id"), "quran_reader_preferences", ["user_id"])


def downgrade():
    op.drop_table("quran_reader_preferences")
    op.drop_table("quran_translation_import_reviews")
    op.drop_table("quran_translation_import_ayahs")
    op.drop_table("quran_translation_import_batches")
