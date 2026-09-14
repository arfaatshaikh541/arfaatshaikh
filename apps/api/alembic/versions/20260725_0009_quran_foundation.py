"""quran canonical foundation

Revision ID: 20260725_0009
Revises: 20260725_0008
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260725_0009"
down_revision = "20260725_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("quran_text_editions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_edition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("edition_key", sa.String(120), nullable=False),
        sa.Column("script_style", sa.String(24), nullable=False),
        sa.Column("recitation_system", sa.String(80), nullable=True),
        sa.Column("canonical", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("published", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("script_style IN ('uthmani','imlaei','other')", name="ck_quran_text_editions_script_style"),
        sa.ForeignKeyConstraint(["source_edition_id"],["source_editions.id"],ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("edition_key"), sa.UniqueConstraint("source_edition_id"))
    op.create_table("quran_surahs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("surah_number", sa.Integer(), nullable=False),
        sa.Column("arabic_name", sa.String(120), nullable=False), sa.Column("transliterated_name", sa.String(160), nullable=False), sa.Column("english_name", sa.String(160), nullable=False),
        sa.Column("ayah_count", sa.Integer(), nullable=False), sa.Column("revelation_classification", sa.String(24), server_default="unreviewed", nullable=False),
        sa.Column("revelation_order", sa.Integer(), nullable=True), sa.Column("metadata_source_passage_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("surah_number BETWEEN 1 AND 114", name="ck_quran_surahs_number"), sa.CheckConstraint("ayah_count > 0", name="ck_quran_surahs_ayah_count"),
        sa.CheckConstraint("revelation_classification IN ('makki','madani','disputed','unreviewed')", name="ck_quran_surahs_revelation"),
        sa.ForeignKeyConstraint(["metadata_source_passage_id"],["source_passages.id"],ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("surah_number"))
    op.create_table("quran_ayahs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("text_edition_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("surah_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ayah_number", sa.Integer(), nullable=False), sa.Column("canonical_reference", sa.String(16), nullable=False), sa.Column("arabic_text", sa.Text(), nullable=False), sa.Column("text_sha256", sa.String(64), nullable=False),
        sa.Column("source_passage_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("juz_number", sa.Integer(), nullable=True), sa.Column("hizb_number", sa.Integer(), nullable=True), sa.Column("rub_number", sa.Integer(), nullable=True), sa.Column("page_number", sa.Integer(), nullable=True), sa.Column("ruku_number", sa.Integer(), nullable=True),
        sa.Column("sajdah_type", sa.String(24), nullable=True), sa.Column("bismillah_status", sa.String(24), server_default="not_applicable", nullable=False), sa.Column("published", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ayah_number > 0", name="ck_quran_ayahs_number"), sa.ForeignKeyConstraint(["source_passage_id"],["source_passages.id"],ondelete="RESTRICT"), sa.ForeignKeyConstraint(["surah_id"],["quran_surahs.id"],ondelete="RESTRICT"), sa.ForeignKeyConstraint(["text_edition_id"],["quran_text_editions.id"],ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("text_edition_id","canonical_reference", name="uq_quran_ayahs_edition_reference"), sa.UniqueConstraint("text_edition_id","surah_id","ayah_number", name="uq_quran_ayahs_edition_surah_ayah"))
    op.create_index("ix_quran_ayahs_reference","quran_ayahs",["canonical_reference"])
    op.create_index(op.f("ix_quran_ayahs_surah_id"),"quran_ayahs",["surah_id"])
    op.create_index(op.f("ix_quran_ayahs_text_edition_id"),"quran_ayahs",["text_edition_id"])
    op.create_table("quran_translation_editions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("source_edition_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("translation_key", sa.String(120), nullable=False), sa.Column("language", sa.String(16), nullable=False), sa.Column("translator_name", sa.String(300), nullable=False), sa.Column("display_name", sa.String(300), nullable=False), sa.Column("published", sa.Boolean(),server_default="false",nullable=False), sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False), sa.ForeignKeyConstraint(["source_edition_id"],["source_editions.id"],ondelete="RESTRICT"),sa.PrimaryKeyConstraint("id"),sa.UniqueConstraint("source_edition_id"),sa.UniqueConstraint("translation_key"))
    op.create_table("quran_ayah_translations",
        sa.Column("id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("translation_edition_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("ayah_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("translated_text",sa.Text(),nullable=False),sa.Column("text_sha256",sa.String(64),nullable=False),sa.Column("source_passage_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("published",sa.Boolean(),server_default="false",nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.ForeignKeyConstraint(["ayah_id"],["quran_ayahs.id"],ondelete="RESTRICT"),sa.ForeignKeyConstraint(["source_passage_id"],["source_passages.id"],ondelete="RESTRICT"),sa.ForeignKeyConstraint(["translation_edition_id"],["quran_translation_editions.id"],ondelete="RESTRICT"),sa.PrimaryKeyConstraint("id"),sa.UniqueConstraint("translation_edition_id","ayah_id"))
    op.create_index("ix_quran_translations_ayah","quran_ayah_translations",["ayah_id"])


def downgrade() -> None:
    op.drop_index("ix_quran_translations_ayah",table_name="quran_ayah_translations"); op.drop_table("quran_ayah_translations"); op.drop_table("quran_translation_editions")
    op.drop_index(op.f("ix_quran_ayahs_text_edition_id"),table_name="quran_ayahs"); op.drop_index(op.f("ix_quran_ayahs_surah_id"),table_name="quran_ayahs"); op.drop_index("ix_quran_ayahs_reference",table_name="quran_ayahs"); op.drop_table("quran_ayahs"); op.drop_table("quran_surahs"); op.drop_table("quran_text_editions")
