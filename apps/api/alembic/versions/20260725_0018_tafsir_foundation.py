"""canonical tafsir foundation

Revision ID: 20260725_0018
Revises: 20260725_0017
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_0018"
down_revision = "20260725_0017"
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]


def upgrade():
    op.create_table("tafsir_authors",
        sa.Column("canonical_name", sa.String(300), nullable=False), sa.Column("arabic_name", sa.String(300), nullable=False),
        sa.Column("aliases_text", sa.Text(), nullable=True), sa.Column("birth_year_ah", sa.Integer(), nullable=True), sa.Column("death_year_ah", sa.Integer(), nullable=True),
        sa.Column("methodology_note", sa.Text(), nullable=True), sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("published", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False), *timestamps(),
        sa.ForeignKeyConstraint(["source_passage_id"],["source_passages.id"],ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("canonical_name"))
    op.create_table("tafsir_collections",
        sa.Column("collection_key", sa.String(120), nullable=False), sa.Column("arabic_title", sa.String(400), nullable=False), sa.Column("display_title", sa.String(400), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False), sa.Column("description", sa.Text(), nullable=True), sa.Column("published", sa.Boolean(), server_default="false", nullable=False), sa.Column("id", sa.Uuid(), nullable=False), *timestamps(),
        sa.ForeignKeyConstraint(["author_id"],["tafsir_authors.id"],ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("collection_key"))
    op.create_index("ix_tafsir_collections_author_id", "tafsir_collections", ["author_id"])
    op.create_table("tafsir_editions",
        sa.Column("collection_id", sa.Uuid(), nullable=False), sa.Column("source_edition_id", sa.Uuid(), nullable=False), sa.Column("edition_key", sa.String(120), nullable=False),
        sa.Column("publisher_name", sa.String(300), nullable=True), sa.Column("publication_year", sa.String(32), nullable=True), sa.Column("language", sa.String(16), server_default="ar", nullable=False),
        sa.Column("attribution_text", sa.Text(), nullable=False), sa.Column("published", sa.Boolean(), server_default="false", nullable=False), sa.Column("id", sa.Uuid(), nullable=False), *timestamps(),
        sa.ForeignKeyConstraint(["collection_id"],["tafsir_collections.id"],ondelete="RESTRICT"), sa.ForeignKeyConstraint(["source_edition_id"],["source_editions.id"],ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("edition_key"), sa.UniqueConstraint("collection_id","source_edition_id"))
    op.create_index("ix_tafsir_editions_collection_id", "tafsir_editions", ["collection_id"])
    op.create_table("tafsir_volumes",
        sa.Column("edition_id", sa.Uuid(), nullable=False), sa.Column("volume_number", sa.Integer(), nullable=False), sa.Column("title", sa.String(400), nullable=True),
        sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("published", sa.Boolean(), server_default="false", nullable=False), sa.Column("id", sa.Uuid(), nullable=False), *timestamps(),
        sa.CheckConstraint("volume_number > 0", name="ck_tafsir_volumes_number"), sa.ForeignKeyConstraint(["edition_id"],["tafsir_editions.id"],ondelete="RESTRICT"), sa.ForeignKeyConstraint(["source_passage_id"],["source_passages.id"],ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("edition_id","volume_number"))
    op.create_index("ix_tafsir_volumes_edition_id", "tafsir_volumes", ["edition_id"])
    op.create_table("tafsir_sections",
        sa.Column("edition_id", sa.Uuid(), nullable=False), sa.Column("volume_id", sa.Uuid(), nullable=True), sa.Column("section_key", sa.String(180), nullable=False),
        sa.Column("section_type", sa.String(32), nullable=False), sa.Column("title", sa.String(500), nullable=True), sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("published", sa.Boolean(), server_default="false", nullable=False), sa.Column("id", sa.Uuid(), nullable=False), *timestamps(),
        sa.CheckConstraint("section_type IN ('surah','ayah','ayah_range','introduction','appendix','editorial_note')", name="ck_tafsir_sections_type"),
        sa.ForeignKeyConstraint(["edition_id"],["tafsir_editions.id"],ondelete="RESTRICT"), sa.ForeignKeyConstraint(["volume_id"],["tafsir_volumes.id"],ondelete="RESTRICT"), sa.ForeignKeyConstraint(["source_passage_id"],["source_passages.id"],ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("edition_id","section_key"))
    op.create_index("ix_tafsir_sections_edition_id", "tafsir_sections", ["edition_id"])
    op.create_table("tafsir_entries",
        sa.Column("edition_id", sa.Uuid(), nullable=False), sa.Column("section_id", sa.Uuid(), nullable=True), sa.Column("canonical_reference", sa.String(200), nullable=False),
        sa.Column("surah_number", sa.Integer(), nullable=False), sa.Column("start_ayah_number", sa.Integer(), nullable=True), sa.Column("end_ayah_number", sa.Integer(), nullable=True),
        sa.Column("entry_type", sa.String(32), nullable=False), sa.Column("arabic_text", sa.Text(), nullable=False), sa.Column("text_sha256", sa.String(64), nullable=False),
        sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("published", sa.Boolean(), server_default="false", nullable=False), sa.Column("id", sa.Uuid(), nullable=False), *timestamps(),
        sa.CheckConstraint("surah_number BETWEEN 1 AND 114", name="ck_tafsir_entries_surah"), sa.CheckConstraint("start_ayah_number IS NULL OR start_ayah_number > 0", name="ck_tafsir_entries_start_ayah"), sa.CheckConstraint("end_ayah_number IS NULL OR end_ayah_number >= start_ayah_number", name="ck_tafsir_entries_end_ayah"),
        sa.ForeignKeyConstraint(["edition_id"],["tafsir_editions.id"],ondelete="RESTRICT"), sa.ForeignKeyConstraint(["section_id"],["tafsir_sections.id"],ondelete="RESTRICT"), sa.ForeignKeyConstraint(["source_passage_id"],["source_passages.id"],ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("edition_id","canonical_reference"))
    op.create_index("ix_tafsir_entries_edition_id", "tafsir_entries", ["edition_id"]); op.create_index("ix_tafsir_entries_section_id", "tafsir_entries", ["section_id"]); op.create_index("ix_tafsir_entries_surah_range", "tafsir_entries", ["surah_number","start_ayah_number","end_ayah_number"])
    op.create_table("tafsir_translation_editions",
        sa.Column("tafsir_edition_id", sa.Uuid(), nullable=False), sa.Column("source_edition_id", sa.Uuid(), nullable=False), sa.Column("translation_key", sa.String(120), nullable=False),
        sa.Column("language", sa.String(16), nullable=False), sa.Column("translator_name", sa.String(300), nullable=False), sa.Column("publisher_name", sa.String(300), nullable=True), sa.Column("attribution_text", sa.Text(), nullable=False), sa.Column("published", sa.Boolean(), server_default="false", nullable=False), sa.Column("id", sa.Uuid(), nullable=False), *timestamps(),
        sa.ForeignKeyConstraint(["tafsir_edition_id"],["tafsir_editions.id"],ondelete="RESTRICT"), sa.ForeignKeyConstraint(["source_edition_id"],["source_editions.id"],ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("translation_key"))
    op.create_index("ix_tafsir_translation_editions_tafsir_edition_id", "tafsir_translation_editions", ["tafsir_edition_id"])
    op.create_table("tafsir_translations",
        sa.Column("translation_edition_id", sa.Uuid(), nullable=False), sa.Column("tafsir_entry_id", sa.Uuid(), nullable=False), sa.Column("translated_text", sa.Text(), nullable=False), sa.Column("text_sha256", sa.String(64), nullable=False), sa.Column("source_passage_id", sa.Uuid(), nullable=False), sa.Column("published", sa.Boolean(), server_default="false", nullable=False), sa.Column("id", sa.Uuid(), nullable=False), *timestamps(),
        sa.ForeignKeyConstraint(["translation_edition_id"],["tafsir_translation_editions.id"],ondelete="RESTRICT"), sa.ForeignKeyConstraint(["tafsir_entry_id"],["tafsir_entries.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["source_passage_id"],["source_passages.id"],ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("translation_edition_id","tafsir_entry_id"))
    op.create_index("ix_tafsir_translations_translation_edition_id", "tafsir_translations", ["translation_edition_id"]); op.create_index("ix_tafsir_translations_tafsir_entry_id", "tafsir_translations", ["tafsir_entry_id"])


def downgrade():
    for table in ["tafsir_translations","tafsir_translation_editions","tafsir_entries","tafsir_sections","tafsir_volumes","tafsir_editions","tafsir_collections","tafsir_authors"]:
        op.drop_table(table)
