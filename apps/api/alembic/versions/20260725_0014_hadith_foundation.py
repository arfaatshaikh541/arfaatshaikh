"""canonical hadith corpus foundation

Revision ID: 20260725_0014
Revises: 20260725_0013
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_0014"
down_revision = "20260725_0013"
branch_labels = None
depends_on = None


def audit_columns():
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table("hadith_collections",
        sa.Column("source_edition_id", sa.Uuid(), nullable=False), sa.Column("collection_key", sa.String(120), nullable=False),
        sa.Column("arabic_title", sa.String(300), nullable=False), sa.Column("display_title", sa.String(300), nullable=False),
        sa.Column("compiler_name", sa.String(300), nullable=False), sa.Column("language", sa.String(16), server_default="ar", nullable=False),
        sa.Column("published", sa.Boolean(), server_default="false", nullable=False), *audit_columns(),
        sa.ForeignKeyConstraint(["source_edition_id"], ["source_editions.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("collection_key"))
    op.create_table("hadith_narrators",
        sa.Column("canonical_name", sa.String(300), nullable=False), sa.Column("arabic_name", sa.String(300), nullable=False),
        sa.Column("disambiguation_note", sa.Text()), sa.Column("source_passage_id", sa.Uuid()), *audit_columns(),
        sa.ForeignKeyConstraint(["source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("canonical_name"))
    op.create_table("hadith_books",
        sa.Column("collection_id", sa.Uuid(), nullable=False), sa.Column("book_number", sa.Integer(), nullable=False),
        sa.Column("arabic_title", sa.String(300), nullable=False), sa.Column("display_title", sa.String(300), nullable=False),
        sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("published", sa.Boolean(), server_default="false", nullable=False), *audit_columns(),
        sa.CheckConstraint("book_number > 0", name="ck_hadith_books_number"),
        sa.ForeignKeyConstraint(["collection_id"], ["hadith_collections.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("collection_id", "book_number"))
    op.create_index("ix_hadith_books_collection_id", "hadith_books", ["collection_id"])
    op.create_table("hadith_narrator_aliases",
        sa.Column("narrator_id", sa.Uuid(), nullable=False), sa.Column("alias", sa.String(300), nullable=False), sa.Column("language", sa.String(16), nullable=False), sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["narrator_id"], ["hadith_narrators.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("narrator_id", "alias"))
    op.create_index("ix_hadith_narrator_aliases_narrator_id", "hadith_narrator_aliases", ["narrator_id"])
    op.create_table("hadith_chapters",
        sa.Column("book_id", sa.Uuid(), nullable=False), sa.Column("chapter_number", sa.Integer(), nullable=False), sa.Column("arabic_title", sa.String(500), nullable=False),
        sa.Column("display_title", sa.String(500), nullable=False), sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("published", sa.Boolean(), server_default="false", nullable=False), *audit_columns(),
        sa.CheckConstraint("chapter_number > 0", name="ck_hadith_chapters_number"), sa.ForeignKeyConstraint(["book_id"], ["hadith_books.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("book_id", "chapter_number"))
    op.create_index("ix_hadith_chapters_book_id", "hadith_chapters", ["book_id"])
    op.create_table("hadith_narrations",
        sa.Column("collection_id", sa.Uuid(), nullable=False), sa.Column("book_id", sa.Uuid(), nullable=False), sa.Column("chapter_id", sa.Uuid()),
        sa.Column("collection_hadith_number", sa.Integer(), nullable=False), sa.Column("canonical_reference", sa.String(160), nullable=False), sa.Column("arabic_matn", sa.Text(), nullable=False),
        sa.Column("matn_sha256", sa.String(64), nullable=False), sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("published", sa.Boolean(), server_default="false", nullable=False), *audit_columns(),
        sa.CheckConstraint("collection_hadith_number > 0", name="ck_hadith_narrations_number"),
        sa.ForeignKeyConstraint(["collection_id"], ["hadith_collections.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["book_id"], ["hadith_books.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["chapter_id"], ["hadith_chapters.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("collection_id", "canonical_reference", name="uq_hadith_narrations_collection_reference"), sa.UniqueConstraint("collection_id", "collection_hadith_number", name="uq_hadith_narrations_collection_number"))
    op.create_index("ix_hadith_narrations_reference", "hadith_narrations", ["canonical_reference"])
    op.create_index("ix_hadith_narrations_collection_id", "hadith_narrations", ["collection_id"])
    op.create_index("ix_hadith_narrations_book_id", "hadith_narrations", ["book_id"])
    op.create_index("ix_hadith_narrations_chapter_id", "hadith_narrations", ["chapter_id"])
    op.create_table("hadith_isnad_nodes",
        sa.Column("narration_id", sa.Uuid(), nullable=False), sa.Column("narrator_id", sa.Uuid()), sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("transmitted_name", sa.String(300), nullable=False), sa.Column("transmission_term", sa.String(120)), sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("position > 0", name="ck_hadith_isnad_nodes_position"), sa.ForeignKeyConstraint(["narration_id"], ["hadith_narrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["narrator_id"], ["hadith_narrators.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("narration_id", "position"))
    op.create_index("ix_hadith_isnad_nodes_narration_id", "hadith_isnad_nodes", ["narration_id"])
    op.create_table("hadith_gradings",
        sa.Column("narration_id", sa.Uuid(), nullable=False), sa.Column("grader_name", sa.String(300), nullable=False), sa.Column("grading_label", sa.String(32), nullable=False),
        sa.Column("grading_text", sa.Text(), nullable=False), sa.Column("methodology_note", sa.Text()), sa.Column("source_passage_id", sa.Uuid(), nullable=False),
        sa.Column("published", sa.Boolean(), server_default="false", nullable=False), *audit_columns(),
        sa.CheckConstraint("grading_label IN ('sahih','hasan','daif','mawdu','mixed','ungraded','other')", name="ck_hadith_gradings_label"),
        sa.ForeignKeyConstraint(["narration_id"], ["hadith_narrations.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["source_passage_id"], ["source_passages.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("narration_id", "grader_name", "grading_label", "source_passage_id"))
    op.create_index("ix_hadith_gradings_narration_id", "hadith_gradings", ["narration_id"])


def downgrade() -> None:
    op.drop_index("ix_hadith_gradings_narration_id", table_name="hadith_gradings")
    op.drop_table("hadith_gradings")
    op.drop_index("ix_hadith_isnad_nodes_narration_id", table_name="hadith_isnad_nodes")
    op.drop_table("hadith_isnad_nodes")
    op.drop_index("ix_hadith_narrations_chapter_id", table_name="hadith_narrations")
    op.drop_index("ix_hadith_narrations_book_id", table_name="hadith_narrations")
    op.drop_index("ix_hadith_narrations_collection_id", table_name="hadith_narrations")
    op.drop_index("ix_hadith_narrations_reference", table_name="hadith_narrations")
    op.drop_table("hadith_narrations")
    op.drop_index("ix_hadith_chapters_book_id", table_name="hadith_chapters")
    op.drop_table("hadith_chapters")
    op.drop_index("ix_hadith_narrator_aliases_narrator_id", table_name="hadith_narrator_aliases")
    op.drop_table("hadith_narrator_aliases")
    op.drop_index("ix_hadith_books_collection_id", table_name="hadith_books")
    op.drop_table("hadith_books")
    op.drop_table("hadith_narrators")
    op.drop_table("hadith_collections")
