"""controlled tafsir import pipeline

Revision ID: 20260725_0019
Revises: 20260725_0018
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260725_0019"
down_revision = "20260725_0018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("tafsir_import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("edition_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tafsir_editions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("manifest_version", sa.String(32), nullable=False), sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("expected_volume_count", sa.Integer(), nullable=False), sa.Column("expected_section_count", sa.Integer(), nullable=False), sa.Column("expected_entry_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("submitted_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("validation_summary", sa.Text()), sa.Column("validated_at", sa.DateTime(timezone=True)), sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('draft','validating','failed','review_pending','approved','changes_requested','rejected','published')", name="ck_tafsir_import_batches_status"),
        sa.CheckConstraint("expected_entry_count > 0", name="ck_tafsir_import_batches_count"))
    op.create_index("ix_tafsir_import_batches_edition_id", "tafsir_import_batches", ["edition_id"])
    op.create_table("tafsir_import_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tafsir_import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("volume_number", sa.Integer()), sa.Column("volume_title", sa.String(400)), sa.Column("volume_source_passage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_passages.id", ondelete="RESTRICT")),
        sa.Column("section_key", sa.String(180)), sa.Column("section_type", sa.String(32)), sa.Column("section_title", sa.String(500)), sa.Column("section_sort_order", sa.Integer(), nullable=False, server_default="0"), sa.Column("section_source_passage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_passages.id", ondelete="RESTRICT")),
        sa.Column("canonical_reference", sa.String(200), nullable=False), sa.Column("surah_number", sa.Integer(), nullable=False), sa.Column("start_ayah_number", sa.Integer()), sa.Column("end_ayah_number", sa.Integer()), sa.Column("entry_type", sa.String(32), nullable=False),
        sa.Column("arabic_text", sa.Text(), nullable=False), sa.Column("text_sha256", sa.String(64), nullable=False), sa.Column("source_passage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("validation_status", sa.String(16), nullable=False, server_default="pending"), sa.Column("validation_errors", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("import_batch_id", "canonical_reference"), sa.CheckConstraint("validation_status IN ('pending','valid','invalid')", name="ck_tafsir_import_entries_validation"))
    op.create_index("ix_tafsir_import_entries_import_batch_id", "tafsir_import_entries", ["import_batch_id"])
    op.create_index("ix_tafsir_import_entries_batch_order", "tafsir_import_entries", ["import_batch_id","volume_number","section_sort_order","surah_number","start_ayah_number"])
    op.create_table("tafsir_import_review_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tafsir_import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("review_domain", sa.String(32), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="open"), sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("import_batch_id","reviewer_user_id","review_domain"), sa.CheckConstraint("review_domain IN ('tafsir_text','source_provenance','arabic_language')", name="ck_tafsir_import_review_domain"), sa.CheckConstraint("status IN ('open','completed','cancelled')", name="ck_tafsir_import_assignment_status"))
    op.create_index("ix_tafsir_import_review_assignments_import_batch_id", "tafsir_import_review_assignments", ["import_batch_id"])
    op.create_index("ix_tafsir_import_review_assignments_reviewer_user_id", "tafsir_import_review_assignments", ["reviewer_user_id"])
    op.create_table("tafsir_import_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("assignment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tafsir_import_review_assignments.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tafsir_import_batches.id", ondelete="CASCADE"), nullable=False), sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("review_domain", sa.String(32), nullable=False), sa.Column("decision", sa.String(24), nullable=False), sa.Column("rationale", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("decision IN ('approved','changes_requested','rejected')", name="ck_tafsir_import_review_decision"))
    op.create_index("ix_tafsir_import_reviews_import_batch_id", "tafsir_import_reviews", ["import_batch_id"])
    op.create_table("tafsir_import_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tafsir_import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("event_type", sa.String(80), nullable=False), sa.Column("from_status", sa.String(32)), sa.Column("to_status", sa.String(32)), sa.Column("details", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_tafsir_import_events_batch_created", "tafsir_import_events", ["import_batch_id","created_at"])
    op.create_table("tafsir_translation_import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("translation_edition_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tafsir_translation_editions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False), sa.Column("expected_translation_count", sa.Integer(), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("submitted_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("validation_summary", sa.Text()), sa.Column("validated_at", sa.DateTime(timezone=True)), sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('draft','validating','failed','review_pending','approved','changes_requested','rejected','published')", name="ck_tafsir_translation_import_status"), sa.CheckConstraint("expected_translation_count > 0", name="ck_tafsir_translation_import_count"))
    op.create_index("ix_tafsir_translation_import_batches_translation_edition_id", "tafsir_translation_import_batches", ["translation_edition_id"])
    op.create_table("tafsir_translation_import_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tafsir_translation_import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tafsir_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tafsir_entries.id", ondelete="RESTRICT"), nullable=False), sa.Column("translated_text", sa.Text(), nullable=False), sa.Column("text_sha256", sa.String(64), nullable=False), sa.Column("source_passage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("import_batch_id", "tafsir_entry_id"))
    op.create_index("ix_tafsir_translation_import_items_import_batch_id", "tafsir_translation_import_items", ["import_batch_id"])
    op.create_index("ix_tafsir_translation_import_items_tafsir_entry_id", "tafsir_translation_import_items", ["tafsir_entry_id"])
    op.create_table("tafsir_translation_import_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tafsir_translation_import_batches.id", ondelete="CASCADE"), nullable=False), sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decision", sa.String(24), nullable=False), sa.Column("rationale", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("import_batch_id", "reviewer_user_id"), sa.CheckConstraint("decision IN ('approved','changes_requested','rejected')", name="ck_tafsir_translation_review_decision"))
    op.create_index("ix_tafsir_translation_import_reviews_import_batch_id", "tafsir_translation_import_reviews", ["import_batch_id"])
    op.execute("""CREATE FUNCTION prevent_tafsir_import_event_mutation() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'tafsir import events are append-only'; END; $$ LANGUAGE plpgsql;""")
    op.execute("""CREATE TRIGGER tafsir_import_events_append_only BEFORE UPDATE OR DELETE ON tafsir_import_events FOR EACH ROW EXECUTE FUNCTION prevent_tafsir_import_event_mutation();""")


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS tafsir_import_events_append_only ON tafsir_import_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_tafsir_import_event_mutation")
    for table in ["tafsir_translation_import_reviews","tafsir_translation_import_items","tafsir_translation_import_batches","tafsir_import_events","tafsir_import_reviews","tafsir_import_review_assignments","tafsir_import_entries","tafsir_import_batches"]:
        op.drop_table(table)
