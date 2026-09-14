from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class QuranTextEdition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_text_editions"
    __table_args__ = (
        UniqueConstraint("source_edition_id"),
        CheckConstraint("script_style IN ('uthmani','imlaei','other')", name="ck_quran_text_editions_script_style"),
    )

    source_edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="RESTRICT"), nullable=False)
    edition_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    script_style: Mapped[str] = mapped_column(String(24), nullable=False)
    recitation_system: Mapped[str | None] = mapped_column(String(80), nullable=True)
    canonical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class QuranSurah(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_surahs"
    __table_args__ = (
        UniqueConstraint("surah_number"),
        CheckConstraint("surah_number BETWEEN 1 AND 114", name="ck_quran_surahs_number"),
        CheckConstraint("ayah_count > 0", name="ck_quran_surahs_ayah_count"),
        CheckConstraint("revelation_classification IN ('makki','madani','disputed','unreviewed')", name="ck_quran_surahs_revelation"),
    )

    surah_number: Mapped[int] = mapped_column(Integer, nullable=False)
    arabic_name: Mapped[str] = mapped_column(String(120), nullable=False)
    transliterated_name: Mapped[str] = mapped_column(String(160), nullable=False)
    english_name: Mapped[str] = mapped_column(String(160), nullable=False)
    ayah_count: Mapped[int] = mapped_column(Integer, nullable=False)
    revelation_classification: Mapped[str] = mapped_column(String(24), nullable=False, default="unreviewed", server_default="unreviewed")
    revelation_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_source_passage_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=True)


class QuranAyah(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_ayahs"
    __table_args__ = (
        UniqueConstraint("text_edition_id", "surah_id", "ayah_number"),
        UniqueConstraint("text_edition_id", "canonical_reference"),
        CheckConstraint("ayah_number > 0", name="ck_quran_ayahs_number"),
        Index("ix_quran_ayahs_reference", "canonical_reference"),
    )

    text_edition_id: Mapped[UUID] = mapped_column(ForeignKey("quran_text_editions.id", ondelete="RESTRICT"), nullable=False, index=True)
    surah_id: Mapped[UUID] = mapped_column(ForeignKey("quran_surahs.id", ondelete="RESTRICT"), nullable=False, index=True)
    ayah_number: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_reference: Mapped[str] = mapped_column(String(16), nullable=False)
    arabic_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    juz_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hizb_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rub_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ruku_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sajdah_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    bismillah_status: Mapped[str] = mapped_column(String(24), nullable=False, default="not_applicable", server_default="not_applicable")
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class QuranTranslationEdition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_translation_editions"
    __table_args__ = (UniqueConstraint("source_edition_id"),)

    source_edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="RESTRICT"), nullable=False)
    translation_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    translator_name: Mapped[str] = mapped_column(String(300), nullable=False)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class QuranAyahTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_ayah_translations"
    __table_args__ = (
        UniqueConstraint("translation_edition_id", "ayah_id"),
        Index("ix_quran_translations_ayah", "ayah_id"),
    )

    translation_edition_id: Mapped[UUID] = mapped_column(ForeignKey("quran_translation_editions.id", ondelete="RESTRICT"), nullable=False)
    ayah_id: Mapped[UUID] = mapped_column(ForeignKey("quran_ayahs.id", ondelete="RESTRICT"), nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

class QuranImportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_import_batches"
    __table_args__ = (
        CheckConstraint("status IN ('draft','validating','validated','review_pending','approved','rejected','published','failed')", name="ck_quran_import_batches_status"),
        CheckConstraint("expected_ayah_count > 0", name="ck_quran_import_batches_expected_count"),
        Index("ix_quran_import_batches_edition_status", "text_edition_id", "status"),
    )

    text_edition_id: Mapped[UUID] = mapped_column(ForeignKey("quran_text_editions.id", ondelete="RESTRICT"), nullable=False, index=True)
    manifest_version: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_surah_count: Mapped[int] = mapped_column(Integer, nullable=False, default=114, server_default="114")
    expected_ayah_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    submitted_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    validated_at: Mapped[object | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    published_at: Mapped[object | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    validation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class QuranImportAyah(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_import_ayahs"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "canonical_reference"),
        CheckConstraint("ayah_number > 0", name="ck_quran_import_ayahs_number"),
        CheckConstraint("validation_status IN ('pending','valid','invalid')", name="ck_quran_import_ayahs_validation"),
        Index("ix_quran_import_ayahs_batch_surah", "import_batch_id", "surah_number", "ayah_number"),
    )

    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("quran_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    surah_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ayah_number: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_reference: Mapped[str] = mapped_column(String(16), nullable=False)
    arabic_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", server_default="{}")
    validation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    validation_errors: Mapped[str | None] = mapped_column(Text, nullable=True)


class QuranImportReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "quran_import_reviews"
    __table_args__ = (
        CheckConstraint("decision IN ('approved','changes_requested','rejected')", name="ck_quran_import_reviews_decision"),
        UniqueConstraint("import_batch_id", "reviewer_user_id"),
        Index("ix_quran_import_reviews_batch_created", "import_batch_id", "created_at"),
    )

    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("quran_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class QuranImportEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "quran_import_events"
    __table_args__ = (Index("ix_quran_import_events_batch_created", "import_batch_id", "created_at"),)

    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("quran_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(sa.DateTime(timezone=True), nullable=False)

class QuranBookmark(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_bookmarks"
    __table_args__ = (
        UniqueConstraint("user_id", "ayah_id"),
        Index("ix_quran_bookmarks_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ayah_id: Mapped[UUID] = mapped_column(ForeignKey("quran_ayahs.id", ondelete="CASCADE"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class QuranReadingProgress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_reading_progress"
    __table_args__ = (UniqueConstraint("user_id"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ayah_id: Mapped[UUID] = mapped_column(ForeignKey("quran_ayahs.id", ondelete="RESTRICT"), nullable=False)
    translation_edition_id: Mapped[UUID | None] = mapped_column(ForeignKey("quran_translation_editions.id", ondelete="SET NULL"), nullable=True)

class QuranTranslationImportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_translation_import_batches"
    __table_args__ = (
        CheckConstraint("status IN ('draft','validated','review_pending','approved','rejected','published','failed')", name="ck_quran_translation_import_batches_status"),
        CheckConstraint("expected_ayah_count > 0", name="ck_quran_translation_import_batches_expected_count"),
        Index("ix_quran_translation_import_batches_edition_status", "translation_edition_id", "status"),
    )

    translation_edition_id: Mapped[UUID] = mapped_column(ForeignKey("quran_translation_editions.id", ondelete="RESTRICT"), nullable=False, index=True)
    manifest_version: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_ayah_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    submitted_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    validation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[object | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class QuranTranslationImportAyah(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_translation_import_ayahs"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "ayah_id"),
        CheckConstraint("validation_status IN ('pending','valid','invalid')", name="ck_quran_translation_import_ayahs_validation"),
    )

    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("quran_translation_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    ayah_id: Mapped[UUID] = mapped_column(ForeignKey("quran_ayahs.id", ondelete="RESTRICT"), nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    validation_errors: Mapped[str | None] = mapped_column(Text, nullable=True)


class QuranTranslationImportReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "quran_translation_import_reviews"
    __table_args__ = (
        CheckConstraint("decision IN ('approved','changes_requested','rejected')", name="ck_quran_translation_import_reviews_decision"),
        UniqueConstraint("import_batch_id", "reviewer_user_id"),
    )

    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("quran_translation_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class QuranReaderPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_reader_preferences"
    __table_args__ = (
        UniqueConstraint("user_id"),
        CheckConstraint("arabic_font_scale BETWEEN 80 AND 200", name="ck_quran_reader_preferences_font_scale"),
        CheckConstraint("theme IN ('system','light','dark','sepia')", name="ck_quran_reader_preferences_theme"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    translation_edition_id: Mapped[UUID | None] = mapped_column(ForeignKey("quran_translation_editions.id", ondelete="SET NULL"), nullable=True)
    show_translation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    arabic_font_scale: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    theme: Mapped[str] = mapped_column(String(16), nullable=False, default="system", server_default="system")

class QuranRecitationEdition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_recitation_editions"
    __table_args__ = (
        UniqueConstraint("recitation_key"),
        CheckConstraint("audio_format IN ('mp3','m4a','ogg','webm')", name="ck_quran_recitation_editions_format"),
    )

    source_edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="RESTRICT"), nullable=False)
    recitation_key: Mapped[str] = mapped_column(String(120), nullable=False)
    reciter_name: Mapped[str] = mapped_column(String(300), nullable=False)
    riwayah: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    audio_format: Mapped[str] = mapped_column(String(16), nullable=False)
    attribution_text: Mapped[str] = mapped_column(Text, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class QuranAyahAudio(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_ayah_audio"
    __table_args__ = (
        UniqueConstraint("recitation_edition_id", "ayah_id"),
        CheckConstraint("duration_ms > 0", name="ck_quran_ayah_audio_duration"),
        CheckConstraint("octet_size > 0", name="ck_quran_ayah_audio_size"),
        Index("ix_quran_ayah_audio_ayah", "ayah_id"),
    )

    recitation_edition_id: Mapped[UUID] = mapped_column(ForeignKey("quran_recitation_editions.id", ondelete="RESTRICT"), nullable=False)
    ayah_id: Mapped[UUID] = mapped_column(ForeignKey("quran_ayahs.id", ondelete="RESTRICT"), nullable=False)
    audio_url: Mapped[str] = mapped_column(Text, nullable=False)
    audio_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    octet_size: Mapped[int] = mapped_column(Integer, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class QuranPlaybackProgress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quran_playback_progress"
    __table_args__ = (
        UniqueConstraint("user_id"),
        CheckConstraint("position_ms >= 0", name="ck_quran_playback_progress_position"),
        CheckConstraint("repeat_mode IN ('off','ayah','surah')", name="ck_quran_playback_progress_repeat"),
        CheckConstraint("playback_rate IN (75,100,125,150,175,200)", name="ck_quran_playback_progress_rate"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ayah_audio_id: Mapped[UUID] = mapped_column(ForeignKey("quran_ayah_audio.id", ondelete="RESTRICT"), nullable=False)
    position_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    repeat_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="off", server_default="off")
    playback_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
