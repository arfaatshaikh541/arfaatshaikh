from __future__ import annotations

from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from typing import Literal

ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))


def validate_arabic_text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Arabic text must not be empty")
    letters = [ord(ch) for ch in value if ch.isalpha()]
    if not letters or any(not any(start <= code <= end for start, end in ARABIC_RANGES) for code in letters):
        raise ValueError("Arabic text contains non-Arabic letters")
    return value


class QuranSurahView(BaseModel):
    id: UUID
    surah_number: int
    arabic_name: str
    transliterated_name: str
    english_name: str
    ayah_count: int
    revelation_classification: str

    model_config = {"from_attributes": True}


class QuranAyahView(BaseModel):
    id: UUID
    canonical_reference: str
    ayah_number: int
    arabic_text: str
    juz_number: int | None
    page_number: int | None

    model_config = {"from_attributes": True}


class QuranTranslationView(BaseModel):
    id: UUID
    translation_key: str
    language: str
    translator_name: str
    display_name: str

    model_config = {"from_attributes": True}


class QuranTextEditionCreate(BaseModel):
    source_edition_id: UUID
    edition_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    script_style: str = Field(pattern=r"^(uthmani|imlaei|other)$")
    recitation_system: str | None = Field(default=None, max_length=80)


class QuranSurahCreate(BaseModel):
    surah_number: int = Field(ge=1, le=114)
    arabic_name: str
    transliterated_name: str = Field(min_length=1, max_length=160)
    english_name: str = Field(min_length=1, max_length=160)
    ayah_count: int = Field(gt=0, le=300)
    revelation_classification: str = Field(pattern=r"^(makki|madani|disputed|unreviewed)$")
    revelation_order: int | None = Field(default=None, ge=1, le=114)
    metadata_source_passage_id: UUID | None = None

    _arabic_name = field_validator("arabic_name")(validate_arabic_text)


class QuranAyahCreate(BaseModel):
    surah_id: UUID
    ayah_number: int = Field(gt=0, le=300)
    arabic_text: str
    source_passage_id: UUID
    juz_number: int | None = Field(default=None, ge=1, le=30)
    hizb_number: int | None = Field(default=None, ge=1, le=60)
    rub_number: int | None = Field(default=None, ge=1, le=240)
    page_number: int | None = Field(default=None, ge=1)
    ruku_number: int | None = Field(default=None, ge=1)
    sajdah_type: str | None = Field(default=None, pattern=r"^(recommended|obligatory|disputed)$")
    bismillah_status: str = Field(default="not_applicable", pattern=r"^(included|separate|not_applicable|disputed)$")

    _arabic_text = field_validator("arabic_text")(validate_arabic_text)


class QuranTranslationEditionCreate(BaseModel):
    source_edition_id: UUID
    translation_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    language: str = Field(min_length=2, max_length=16)
    translator_name: str = Field(min_length=2, max_length=300)
    display_name: str = Field(min_length=2, max_length=300)

class QuranImportManifestCreate(BaseModel):
    text_edition_id: UUID
    manifest_version: str = Field(min_length=1, max_length=32)
    expected_surah_count: int = Field(default=114, ge=1, le=114)
    expected_ayah_count: int = Field(gt=0, le=10000)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class QuranImportAyahCreate(BaseModel):
    surah_number: int = Field(ge=1, le=114)
    ayah_number: int = Field(gt=0, le=300)
    arabic_text: str
    source_passage_id: UUID
    juz_number: int | None = Field(default=None, ge=1, le=30)
    hizb_number: int | None = Field(default=None, ge=1, le=60)
    rub_number: int | None = Field(default=None, ge=1, le=240)
    page_number: int | None = Field(default=None, ge=1)
    ruku_number: int | None = Field(default=None, ge=1)
    sajdah_type: str | None = Field(default=None, pattern=r"^(recommended|obligatory|disputed)$")
    bismillah_status: str = Field(default="not_applicable", pattern=r"^(included|separate|not_applicable|disputed)$")

    _arabic_text = field_validator("arabic_text")(validate_arabic_text)


class QuranImportReviewCreate(BaseModel):
    decision: str = Field(pattern=r"^(approved|changes_requested|rejected)$")
    rationale: str = Field(min_length=10, max_length=4000)


class QuranImportBatchView(BaseModel):
    id: UUID
    text_edition_id: UUID
    manifest_version: str
    manifest_sha256: str
    expected_surah_count: int
    expected_ayah_count: int
    status: str
    validation_summary: str | None

    model_config = {"from_attributes": True}

class QuranAyahReadingView(QuranAyahView):
    translation: str | None = None
    translation_edition_id: UUID | None = None


class QuranSurahReadingView(BaseModel):
    surah: QuranSurahView
    text_edition_id: UUID
    translation: QuranTranslationView | None = None
    ayahs: list[QuranAyahReadingView]
    next_surah_number: int | None
    previous_surah_number: int | None


class QuranBookmarkCreate(BaseModel):
    ayah_id: UUID
    note: str | None = Field(default=None, max_length=500)


class QuranBookmarkView(BaseModel):
    id: UUID
    ayah_id: UUID
    canonical_reference: str
    note: str | None


class QuranReadingProgressCreate(BaseModel):
    ayah_id: UUID
    translation_edition_id: UUID | None = None


class QuranReadingProgressView(BaseModel):
    ayah_id: UUID
    canonical_reference: str
    translation_edition_id: UUID | None

class QuranTranslationImportManifestCreate(BaseModel):
    translation_edition_id: UUID
    manifest_version: str = Field(min_length=1, max_length=32)
    expected_ayah_count: int = Field(gt=0, le=10000)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class QuranTranslationImportAyahCreate(BaseModel):
    ayah_id: UUID
    translated_text: str = Field(min_length=1, max_length=12000)
    source_passage_id: UUID


class QuranTranslationImportReviewCreate(BaseModel):
    decision: str = Field(pattern=r"^(approved|changes_requested|rejected)$")
    rationale: str = Field(min_length=10, max_length=4000)


class QuranTranslationImportBatchView(BaseModel):
    id: UUID
    translation_edition_id: UUID
    manifest_version: str
    manifest_sha256: str
    expected_ayah_count: int
    status: str
    validation_summary: str | None

    model_config = {"from_attributes": True}


class QuranReaderPreferenceUpdate(BaseModel):
    translation_edition_id: UUID | None = None
    show_translation: bool = True
    arabic_font_scale: int = Field(default=100, ge=80, le=200)
    theme: str = Field(default="system", pattern=r"^(system|light|dark|sepia)$")


class QuranReaderPreferenceView(QuranReaderPreferenceUpdate):
    id: UUID

    model_config = {"from_attributes": True}

class QuranRecitationEditionCreate(BaseModel):
    source_edition_id: UUID
    recitation_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    reciter_name: str = Field(min_length=2, max_length=300)
    riwayah: str = Field(min_length=2, max_length=160)
    display_name: str = Field(min_length=2, max_length=300)
    audio_format: str = Field(pattern=r"^(mp3|m4a|ogg|webm)$")
    attribution_text: str = Field(min_length=5, max_length=4000)


class QuranAyahAudioCreate(BaseModel):
    ayah_id: UUID
    audio_url: str = Field(pattern=r"^https://[^\s]+$")
    audio_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    duration_ms: int = Field(gt=0, le=3600000)
    octet_size: int = Field(gt=0, le=100000000)


class QuranRecitationView(BaseModel):
    id: UUID
    recitation_key: str
    reciter_name: str
    riwayah: str
    display_name: str
    attribution_text: str
    model_config = {"from_attributes": True}


class QuranAyahAudioView(BaseModel):
    id: UUID
    ayah_id: UUID
    canonical_reference: str
    audio_url: str
    duration_ms: int


class QuranPlaybackProgressUpdate(BaseModel):
    ayah_audio_id: UUID
    position_ms: int = Field(ge=0)
    repeat_mode: str = Field(default="off", pattern=r"^(off|ayah|surah)$")
    playback_rate: Literal[75, 100, 125, 150, 175, 200] = 100


class QuranPlaybackProgressView(QuranPlaybackProgressUpdate):
    canonical_reference: str
