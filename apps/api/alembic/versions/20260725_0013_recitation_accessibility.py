"""recitation governance and playback state

Revision ID: 20260725_0013
Revises: 20260725_0012
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_0013"
down_revision = "20260725_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quran_recitation_editions",
        sa.Column("source_edition_id", sa.Uuid(), nullable=False),
        sa.Column("recitation_key", sa.String(120), nullable=False),
        sa.Column("reciter_name", sa.String(300), nullable=False),
        sa.Column("riwayah", sa.String(160), nullable=False),
        sa.Column("display_name", sa.String(300), nullable=False),
        sa.Column("audio_format", sa.String(16), nullable=False),
        sa.Column("attribution_text", sa.Text(), nullable=False),
        sa.Column("published", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("audio_format IN ('mp3','m4a','ogg','webm')", name="ck_quran_recitation_editions_format"),
        sa.ForeignKeyConstraint(["source_edition_id"], ["source_editions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recitation_key"),
    )
    op.create_table(
        "quran_ayah_audio",
        sa.Column("recitation_edition_id", sa.Uuid(), nullable=False),
        sa.Column("ayah_id", sa.Uuid(), nullable=False),
        sa.Column("audio_url", sa.Text(), nullable=False),
        sa.Column("audio_sha256", sa.String(64), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("octet_size", sa.Integer(), nullable=False),
        sa.Column("published", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("duration_ms > 0", name="ck_quran_ayah_audio_duration"),
        sa.CheckConstraint("octet_size > 0", name="ck_quran_ayah_audio_size"),
        sa.ForeignKeyConstraint(["ayah_id"], ["quran_ayahs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recitation_edition_id"], ["quran_recitation_editions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recitation_edition_id", "ayah_id"),
    )
    op.create_index("ix_quran_ayah_audio_ayah", "quran_ayah_audio", ["ayah_id"])
    op.create_table(
        "quran_playback_progress",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("ayah_audio_id", sa.Uuid(), nullable=False),
        sa.Column("position_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("repeat_mode", sa.String(16), server_default="off", nullable=False),
        sa.Column("playback_rate", sa.Integer(), server_default="100", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("position_ms >= 0", name="ck_quran_playback_progress_position"),
        sa.CheckConstraint("repeat_mode IN ('off','ayah','surah')", name="ck_quran_playback_progress_repeat"),
        sa.CheckConstraint("playback_rate IN (75,100,125,150,175,200)", name="ck_quran_playback_progress_rate"),
        sa.ForeignKeyConstraint(["ayah_audio_id"], ["quran_ayah_audio.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_quran_playback_progress_user_id", "quran_playback_progress", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_quran_playback_progress_user_id", table_name="quran_playback_progress")
    op.drop_table("quran_playback_progress")
    op.drop_index("ix_quran_ayah_audio_ayah", table_name="quran_ayah_audio")
    op.drop_table("quran_ayah_audio")
    op.drop_table("quran_recitation_editions")
