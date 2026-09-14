"""hadith translation, grading governance, and reading APIs

Revision ID: 20260725_0016
Revises: 20260725_0015
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_0016"
down_revision = "20260725_0015"
branch_labels = None
depends_on = None


def audit_columns():
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table("hadith_translation_editions",
        sa.Column("source_edition_id", sa.Uuid(), nullable=False), sa.Column("translation_key", sa.String(120), nullable=False),
        sa.Column("language", sa.String(16), nullable=False), sa.Column("translator_name", sa.String(300), nullable=False),
        sa.Column("publisher_name", sa.String(300)), sa.Column("attribution_text", sa.Text(), nullable=False),
        sa.Column("published", sa.Boolean(), server_default="false", nullable=False), *audit_columns(),
        sa.ForeignKeyConstraint(["source_edition_id"], ["source_editions.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("translation_key"), sa.UniqueConstraint("source_edition_id", "language", "translator_name"))

    op.create_table("hadith_translations",
        sa.Column("translation_edition_id", sa.Uuid(), nullable=False), sa.Column("narration_id", sa.Uuid(), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=False), sa.Column("text_sha256", sa.String(64), nullable=False),
        sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("published", sa.Boolean(), server_default="false", nullable=False), *audit_columns(),
        sa.ForeignKeyConstraint(["translation_edition_id"], ["hadith_translation_editions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["narration_id"], ["hadith_narrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("translation_edition_id", "narration_id"))
    op.create_index("ix_hadith_translations_translation_edition_id", "hadith_translations", ["translation_edition_id"])
    op.create_index("ix_hadith_translations_narration_id", "hadith_translations", ["narration_id"])

    op.create_table("hadith_translation_import_batches",
        sa.Column("translation_edition_id", sa.Uuid(), nullable=False), sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("expected_record_count", sa.Integer(), nullable=False), sa.Column("status", sa.String(24), server_default="draft", nullable=False),
        sa.Column("submitted_by_user_id", sa.Uuid(), nullable=False), sa.Column("validation_summary", sa.Text()), sa.Column("published_at", sa.DateTime(timezone=True)), *audit_columns(),
        sa.CheckConstraint("status IN ('draft','review_pending','approved','rejected','published','failed')", name="ck_hadith_translation_import_status"),
        sa.CheckConstraint("expected_record_count > 0", name="ck_hadith_translation_import_count"),
        sa.ForeignKeyConstraint(["translation_edition_id"], ["hadith_translation_editions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_hadith_translation_import_batches_translation_edition_id", "hadith_translation_import_batches", ["translation_edition_id"])

    op.create_table("hadith_translation_import_items",
        sa.Column("import_batch_id", sa.Uuid(), nullable=False), sa.Column("narration_id", sa.Uuid(), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=False), sa.Column("text_sha256", sa.String(64), nullable=False),
        sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("validation_status", sa.String(16), server_default="pending", nullable=False), *audit_columns(),
        sa.CheckConstraint("validation_status IN ('pending','valid','invalid')", name="ck_hadith_translation_item_validation"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["hadith_translation_import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["narration_id"], ["hadith_narrations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_batch_id", "narration_id"))
    op.create_index("ix_hadith_translation_import_items_import_batch_id", "hadith_translation_import_items", ["import_batch_id"])

    op.create_table("hadith_translation_import_reviews",
        sa.Column("import_batch_id", sa.Uuid(), nullable=False), sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False), sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("decision IN ('approved','rejected')", name="ck_hadith_translation_review_decision"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["hadith_translation_import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("import_batch_id"))

    op.create_table("hadith_grading_import_batches",
        sa.Column("collection_id", sa.Uuid(), nullable=False), sa.Column("source_edition_id", sa.Uuid(), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False), sa.Column("expected_record_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), server_default="draft", nullable=False), sa.Column("submitted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("validation_summary", sa.Text()), sa.Column("published_at", sa.DateTime(timezone=True)), *audit_columns(),
        sa.CheckConstraint("status IN ('draft','review_pending','approved','rejected','published','failed')", name="ck_hadith_grading_import_status"),
        sa.CheckConstraint("expected_record_count > 0", name="ck_hadith_grading_import_count"),
        sa.ForeignKeyConstraint(["collection_id"], ["hadith_collections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_edition_id"], ["source_editions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_hadith_grading_import_batches_collection_id", "hadith_grading_import_batches", ["collection_id"])

    op.create_table("hadith_grading_import_items",
        sa.Column("import_batch_id", sa.Uuid(), nullable=False), sa.Column("narration_id", sa.Uuid(), nullable=False),
        sa.Column("grader_name", sa.String(300), nullable=False), sa.Column("grading_label", sa.String(32), nullable=False),
        sa.Column("grading_text", sa.Text(), nullable=False), sa.Column("methodology_note", sa.Text()),
        sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("validation_status", sa.String(16), server_default="pending", nullable=False), *audit_columns(),
        sa.CheckConstraint("grading_label IN ('sahih','hasan','daif','mawdu','mixed','ungraded','other')", name="ck_hadith_grading_import_label"),
        sa.CheckConstraint("validation_status IN ('pending','valid','invalid')", name="ck_hadith_grading_item_validation"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["hadith_grading_import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["narration_id"], ["hadith_narrations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_batch_id", "narration_id", "grader_name", "grading_label", "source_passage_id"))
    op.create_index("ix_hadith_grading_import_items_import_batch_id", "hadith_grading_import_items", ["import_batch_id"])

    op.create_table("hadith_grading_import_reviews",
        sa.Column("import_batch_id", sa.Uuid(), nullable=False), sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False), sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("decision IN ('approved','rejected')", name="ck_hadith_grading_review_decision"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["hadith_grading_import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("import_batch_id"))


def downgrade() -> None:
    op.drop_table("hadith_grading_import_reviews")
    op.drop_index("ix_hadith_grading_import_items_import_batch_id", table_name="hadith_grading_import_items")
    op.drop_table("hadith_grading_import_items")
    op.drop_index("ix_hadith_grading_import_batches_collection_id", table_name="hadith_grading_import_batches")
    op.drop_table("hadith_grading_import_batches")
    op.drop_table("hadith_translation_import_reviews")
    op.drop_index("ix_hadith_translation_import_items_import_batch_id", table_name="hadith_translation_import_items")
    op.drop_table("hadith_translation_import_items")
    op.drop_index("ix_hadith_translation_import_batches_translation_edition_id", table_name="hadith_translation_import_batches")
    op.drop_table("hadith_translation_import_batches")
    op.drop_index("ix_hadith_translations_narration_id", table_name="hadith_translations")
    op.drop_index("ix_hadith_translations_translation_edition_id", table_name="hadith_translations")
    op.drop_table("hadith_translations")
    op.drop_table("hadith_translation_editions")
