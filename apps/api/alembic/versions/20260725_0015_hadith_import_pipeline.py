"""controlled hadith import and publication pipeline

Revision ID: 20260725_0015
Revises: 20260725_0014
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_0015"
down_revision = "20260725_0014"
branch_labels = None
depends_on = None


def audit_columns():
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table("hadith_import_batches",
        sa.Column("collection_id", sa.Uuid(), nullable=False), sa.Column("manifest_version", sa.String(32), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False), sa.Column("expected_book_count", sa.Integer(), nullable=False),
        sa.Column("expected_chapter_count", sa.Integer(), nullable=False), sa.Column("expected_narration_count", sa.Integer(), nullable=False),
        sa.Column("require_complete_isnad", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(32), server_default="draft", nullable=False), sa.Column("submitted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("validation_summary", sa.Text()), sa.Column("validated_at", sa.DateTime(timezone=True)), sa.Column("published_at", sa.DateTime(timezone=True)),
        *audit_columns(),
        sa.CheckConstraint("status IN ('draft','validating','validated','review_pending','approved','changes_requested','rejected','published','failed')", name="ck_hadith_import_batches_status"),
        sa.CheckConstraint("expected_narration_count > 0", name="ck_hadith_import_batches_expected_count"),
        sa.ForeignKeyConstraint(["collection_id"], ["hadith_collections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_hadith_import_batches_collection_id", "hadith_import_batches", ["collection_id"])
    op.create_index("ix_hadith_import_batches_collection_status", "hadith_import_batches", ["collection_id", "status"])

    op.create_table("hadith_import_narrations",
        sa.Column("import_batch_id", sa.Uuid(), nullable=False), sa.Column("book_number", sa.Integer(), nullable=False),
        sa.Column("book_arabic_title", sa.String(300), nullable=False), sa.Column("book_display_title", sa.String(300), nullable=False),
        sa.Column("book_source_passage_id", sa.Uuid(), nullable=False), sa.Column("chapter_number", sa.Integer()),
        sa.Column("chapter_arabic_title", sa.String(500)), sa.Column("chapter_display_title", sa.String(500)), sa.Column("chapter_source_passage_id", sa.Uuid()),
        sa.Column("collection_hadith_number", sa.Integer(), nullable=False), sa.Column("canonical_reference", sa.String(160), nullable=False),
        sa.Column("arabic_matn", sa.Text(), nullable=False), sa.Column("matn_sha256", sa.String(64), nullable=False),
        sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("validation_status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("validation_errors", sa.Text()), *audit_columns(),
        sa.CheckConstraint("collection_hadith_number > 0", name="ck_hadith_import_narrations_number"),
        sa.CheckConstraint("validation_status IN ('pending','valid','invalid','duplicate')", name="ck_hadith_import_narrations_validation"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["hadith_import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["book_source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["chapter_source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("import_batch_id", "collection_hadith_number"))
    op.create_index("ix_hadith_import_narrations_import_batch_id", "hadith_import_narrations", ["import_batch_id"])
    op.create_index("ix_hadith_import_narrations_batch_order", "hadith_import_narrations", ["import_batch_id", "book_number", "chapter_number", "collection_hadith_number"])

    op.create_table("hadith_import_isnad_nodes",
        sa.Column("import_narration_id", sa.Uuid(), nullable=False), sa.Column("narrator_id", sa.Uuid()),
        sa.Column("position", sa.Integer(), nullable=False), sa.Column("transmitted_name", sa.String(300), nullable=False),
        sa.Column("transmission_term", sa.String(120)), sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("position > 0", name="ck_hadith_import_isnad_position"),
        sa.ForeignKeyConstraint(["import_narration_id"], ["hadith_import_narrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["narrator_id"], ["hadith_narrators.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("import_narration_id", "position"))
    op.create_index("ix_hadith_import_isnad_nodes_import_narration_id", "hadith_import_isnad_nodes", ["import_narration_id"])

    op.create_table("hadith_duplicate_candidates",
        sa.Column("import_narration_id", sa.Uuid(), nullable=False), sa.Column("existing_narration_id", sa.Uuid(), nullable=False),
        sa.Column("match_type", sa.String(32), nullable=False), sa.Column("similarity_basis", sa.Text(), nullable=False),
        sa.Column("resolution", sa.String(32), server_default="pending", nullable=False), sa.Column("resolved_by_user_id", sa.Uuid()),
        sa.Column("resolution_rationale", sa.Text()), *audit_columns(),
        sa.CheckConstraint("match_type IN ('exact_reference','exact_matn','possible_matn')", name="ck_hadith_duplicate_match_type"),
        sa.CheckConstraint("resolution IN ('pending','not_duplicate','confirmed_duplicate','replace_existing')", name="ck_hadith_duplicate_resolution"),
        sa.ForeignKeyConstraint(["import_narration_id"], ["hadith_import_narrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["existing_narration_id"], ["hadith_narrations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("import_narration_id", "existing_narration_id"))
    op.create_index("ix_hadith_duplicate_candidates_import_narration_id", "hadith_duplicate_candidates", ["import_narration_id"])

    op.create_table("hadith_import_review_assignments",
        sa.Column("import_batch_id", sa.Uuid(), nullable=False), sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("review_domain", sa.String(32), nullable=False), sa.Column("status", sa.String(16), server_default="open", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)), *audit_columns(),
        sa.CheckConstraint("review_domain IN ('hadith_text','isnad','source_provenance')", name="ck_hadith_import_review_domain"),
        sa.CheckConstraint("status IN ('open','completed','cancelled')", name="ck_hadith_import_review_assignment_status"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["hadith_import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("import_batch_id", "reviewer_user_id", "review_domain"))
    op.create_index("ix_hadith_import_review_assignments_import_batch_id", "hadith_import_review_assignments", ["import_batch_id"])
    op.create_index("ix_hadith_import_review_assignments_reviewer_user_id", "hadith_import_review_assignments", ["reviewer_user_id"])

    op.create_table("hadith_import_reviews",
        sa.Column("assignment_id", sa.Uuid(), nullable=False), sa.Column("import_batch_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False), sa.Column("review_domain", sa.String(32), nullable=False),
        sa.Column("decision", sa.String(24), nullable=False), sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("decision IN ('approved','changes_requested','rejected')", name="ck_hadith_import_reviews_decision"),
        sa.ForeignKeyConstraint(["assignment_id"], ["hadith_import_review_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["hadith_import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("assignment_id"))
    op.create_index("ix_hadith_import_reviews_import_batch_id", "hadith_import_reviews", ["import_batch_id"])

    op.create_table("hadith_import_events",
        sa.Column("import_batch_id", sa.Uuid(), nullable=False), sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False), sa.Column("from_status", sa.String(32)), sa.Column("to_status", sa.String(32)),
        sa.Column("details", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["import_batch_id"], ["hadith_import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_hadith_import_events_import_batch_id", "hadith_import_events", ["import_batch_id"])
    op.create_index("ix_hadith_import_events_batch_created", "hadith_import_events", ["import_batch_id", "created_at"])
    op.execute("""
    CREATE OR REPLACE FUNCTION prevent_hadith_import_event_mutation() RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION 'hadith import events are append-only';
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""
    CREATE TRIGGER hadith_import_events_append_only
    BEFORE UPDATE OR DELETE ON hadith_import_events
    FOR EACH ROW EXECUTE FUNCTION prevent_hadith_import_event_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS hadith_import_events_append_only ON hadith_import_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_hadith_import_event_mutation")
    op.drop_index("ix_hadith_import_events_batch_created", table_name="hadith_import_events")
    op.drop_index("ix_hadith_import_events_import_batch_id", table_name="hadith_import_events")
    op.drop_table("hadith_import_events")
    op.drop_index("ix_hadith_import_reviews_import_batch_id", table_name="hadith_import_reviews")
    op.drop_table("hadith_import_reviews")
    op.drop_index("ix_hadith_import_review_assignments_reviewer_user_id", table_name="hadith_import_review_assignments")
    op.drop_index("ix_hadith_import_review_assignments_import_batch_id", table_name="hadith_import_review_assignments")
    op.drop_table("hadith_import_review_assignments")
    op.drop_index("ix_hadith_duplicate_candidates_import_narration_id", table_name="hadith_duplicate_candidates")
    op.drop_table("hadith_duplicate_candidates")
    op.drop_index("ix_hadith_import_isnad_nodes_import_narration_id", table_name="hadith_import_isnad_nodes")
    op.drop_table("hadith_import_isnad_nodes")
    op.drop_index("ix_hadith_import_narrations_batch_order", table_name="hadith_import_narrations")
    op.drop_index("ix_hadith_import_narrations_import_batch_id", table_name="hadith_import_narrations")
    op.drop_table("hadith_import_narrations")
    op.drop_index("ix_hadith_import_batches_collection_status", table_name="hadith_import_batches")
    op.drop_index("ix_hadith_import_batches_collection_id", table_name="hadith_import_batches")
    op.drop_table("hadith_import_batches")
