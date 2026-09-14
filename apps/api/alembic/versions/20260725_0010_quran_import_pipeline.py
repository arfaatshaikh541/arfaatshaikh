"""controlled quran import pipeline

Revision ID: 20260725_0010
Revises: 20260725_0009
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260725_0010"
down_revision = "20260725_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("quran_import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text_edition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manifest_version", sa.String(32), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("expected_surah_count", sa.Integer(), server_default="114", nullable=False),
        sa.Column("expected_ayah_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), server_default="draft", nullable=False),
        sa.Column("submitted_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('draft','validating','validated','review_pending','approved','rejected','published','failed')", name="ck_quran_import_batches_status"),
        sa.CheckConstraint("expected_ayah_count > 0", name="ck_quran_import_batches_expected_count"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["text_edition_id"], ["quran_text_editions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_quran_import_batches_edition_status", "quran_import_batches", ["text_edition_id", "status"])
    op.create_index(op.f("ix_quran_import_batches_text_edition_id"), "quran_import_batches", ["text_edition_id"])
    op.create_table("quran_import_ayahs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("surah_number", sa.Integer(), nullable=False),
        sa.Column("ayah_number", sa.Integer(), nullable=False),
        sa.Column("canonical_reference", sa.String(16), nullable=False),
        sa.Column("arabic_text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(64), nullable=False),
        sa.Column("source_passage_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metadata_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("validation_status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("validation_errors", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ayah_number > 0", name="ck_quran_import_ayahs_number"),
        sa.CheckConstraint("validation_status IN ('pending','valid','invalid')", name="ck_quran_import_ayahs_validation"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["quran_import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_batch_id", "canonical_reference"))
    op.create_index("ix_quran_import_ayahs_batch_surah", "quran_import_ayahs", ["import_batch_id", "surah_number", "ayah_number"])
    op.create_index(op.f("ix_quran_import_ayahs_import_batch_id"), "quran_import_ayahs", ["import_batch_id"])
    op.create_table("quran_import_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("decision IN ('approved','changes_requested','rejected')", name="ck_quran_import_reviews_decision"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["quran_import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_batch_id", "reviewer_user_id"))
    op.create_index("ix_quran_import_reviews_batch_created", "quran_import_reviews", ["import_batch_id", "created_at"])
    op.create_index(op.f("ix_quran_import_reviews_import_batch_id"), "quran_import_reviews", ["import_batch_id"])
    op.create_table("quran_import_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("from_status", sa.String(24), nullable=True),
        sa.Column("to_status", sa.String(24), nullable=True),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["quran_import_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_quran_import_events_batch_created", "quran_import_events", ["import_batch_id", "created_at"])
    op.create_index(op.f("ix_quran_import_events_import_batch_id"), "quran_import_events", ["import_batch_id"])
    op.execute("""
    CREATE OR REPLACE FUNCTION reject_quran_import_event_mutation() RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'quran import events are append-only';
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""
    CREATE TRIGGER trg_quran_import_events_immutable
    BEFORE UPDATE OR DELETE ON quran_import_events
    FOR EACH ROW EXECUTE FUNCTION reject_quran_import_event_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_quran_import_events_immutable ON quran_import_events")
    op.execute("DROP FUNCTION IF EXISTS reject_quran_import_event_mutation()")
    op.drop_index(op.f("ix_quran_import_events_import_batch_id"), table_name="quran_import_events")
    op.drop_index("ix_quran_import_events_batch_created", table_name="quran_import_events")
    op.drop_table("quran_import_events")
    op.drop_index(op.f("ix_quran_import_reviews_import_batch_id"), table_name="quran_import_reviews")
    op.drop_index("ix_quran_import_reviews_batch_created", table_name="quran_import_reviews")
    op.drop_table("quran_import_reviews")
    op.drop_index(op.f("ix_quran_import_ayahs_import_batch_id"), table_name="quran_import_ayahs")
    op.drop_index("ix_quran_import_ayahs_batch_surah", table_name="quran_import_ayahs")
    op.drop_table("quran_import_ayahs")
    op.drop_index(op.f("ix_quran_import_batches_text_edition_id"), table_name="quran_import_batches")
    op.drop_index("ix_quran_import_batches_edition_status", table_name="quran_import_batches")
    op.drop_table("quran_import_batches")
