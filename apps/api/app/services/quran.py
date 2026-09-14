from __future__ import annotations

import hashlib
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.quran import (
    QuranAyah, QuranAyahTranslation, QuranBookmark, QuranReadingProgress,
    QuranSurah, QuranTextEdition, QuranTranslationEdition, QuranReaderPreference,
    QuranRecitationEdition, QuranAyahAudio, QuranPlaybackProgress,
)
from app.models.sources import SourceEdition, SourcePassage
from app.schemas.quran import QuranAyahCreate, QuranSurahCreate, QuranTextEditionCreate, QuranTranslationEditionCreate, QuranRecitationEditionCreate, QuranAyahAudioCreate, QuranPlaybackProgressUpdate


class QuranService:
    def __init__(self, db: AsyncSession): self.db = db

    async def _canonical_edition(self) -> QuranTextEdition:
        edition = await self.db.scalar(select(QuranTextEdition).where(QuranTextEdition.canonical.is_(True), QuranTextEdition.published.is_(True)))
        if not edition: raise AppError("quran_corpus_unavailable", "No approved canonical Qur'an edition is published", 404)
        return edition

    async def list_surahs(self) -> list[QuranSurah]:
        result = await self.db.scalars(select(QuranSurah).order_by(QuranSurah.surah_number)); return list(result)

    async def get_surah(self, surah_number: int) -> QuranSurah:
        surah = await self.db.scalar(select(QuranSurah).where(QuranSurah.surah_number == surah_number))
        if not surah: raise AppError("quran_surah_not_found", "Surah not found", 404)
        return surah

    async def get_surah_reading(self, surah_number: int, translation_key: str | None = None) -> dict:
        edition = await self._canonical_edition(); surah = await self.get_surah(surah_number)
        translation = None
        if translation_key:
            translation = await self.db.scalar(select(QuranTranslationEdition).where(QuranTranslationEdition.translation_key == translation_key, QuranTranslationEdition.published.is_(True)))
            if not translation: raise AppError("quran_translation_not_found", "Translation not found or unpublished", 404)
        ayahs = list((await self.db.scalars(select(QuranAyah).where(QuranAyah.text_edition_id == edition.id, QuranAyah.surah_id == surah.id, QuranAyah.published.is_(True)).order_by(QuranAyah.ayah_number))).all())
        translation_map = {}
        if translation and ayahs:
            rows = (await self.db.execute(select(QuranAyahTranslation).where(QuranAyahTranslation.translation_edition_id == translation.id, QuranAyahTranslation.ayah_id.in_([a.id for a in ayahs]), QuranAyahTranslation.published.is_(True)))).scalars().all()
            translation_map = {row.ayah_id: row.translated_text for row in rows}
        return {"surah": surah, "text_edition_id": edition.id, "translation": translation, "ayahs": [{"id": a.id, "canonical_reference": a.canonical_reference, "ayah_number": a.ayah_number, "arabic_text": a.arabic_text, "juz_number": a.juz_number, "page_number": a.page_number, "translation": translation_map.get(a.id), "translation_edition_id": translation.id if translation else None} for a in ayahs], "next_surah_number": surah_number + 1 if surah_number < 114 else None, "previous_surah_number": surah_number - 1 if surah_number > 1 else None}

    async def get_ayah(self, reference: str) -> QuranAyah:
        edition = await self._canonical_edition()
        ayah = await self.db.scalar(select(QuranAyah).where(QuranAyah.text_edition_id == edition.id, QuranAyah.canonical_reference == reference, QuranAyah.published.is_(True)))
        if not ayah: raise AppError("quran_ayah_not_found", "Ayah not found or not published", 404)
        return ayah

    async def list_translations(self) -> list[QuranTranslationEdition]:
        return list((await self.db.scalars(select(QuranTranslationEdition).where(QuranTranslationEdition.published.is_(True)).order_by(QuranTranslationEdition.language, QuranTranslationEdition.display_name))).all())

    async def list_bookmarks(self, user_id: UUID) -> list[dict]:
        rows = (await self.db.execute(select(QuranBookmark, QuranAyah.canonical_reference).join(QuranAyah, QuranAyah.id == QuranBookmark.ayah_id).where(QuranBookmark.user_id == user_id).order_by(QuranBookmark.created_at.desc()))).all()
        return [{"id": b.id, "ayah_id": b.ayah_id, "canonical_reference": ref, "note": b.note} for b, ref in rows]

    async def add_bookmark(self, user_id: UUID, ayah_id: UUID, note: str | None) -> dict:
        ayah = await self.db.get(QuranAyah, ayah_id)
        if not ayah or not ayah.published: raise AppError("quran_ayah_not_found", "Published ayah not found", 404)
        existing = await self.db.scalar(select(QuranBookmark).where(QuranBookmark.user_id == user_id, QuranBookmark.ayah_id == ayah_id))
        if existing: existing.note = note; bookmark = existing
        else: bookmark = QuranBookmark(user_id=user_id, ayah_id=ayah_id, note=note); self.db.add(bookmark)
        await self.db.flush(); return {"id": bookmark.id, "ayah_id": ayah.id, "canonical_reference": ayah.canonical_reference, "note": bookmark.note}

    async def remove_bookmark(self, user_id: UUID, bookmark_id: UUID) -> None:
        result = await self.db.execute(delete(QuranBookmark).where(QuranBookmark.id == bookmark_id, QuranBookmark.user_id == user_id))
        if result.rowcount == 0: raise AppError("quran_bookmark_not_found", "Bookmark not found", 404)

    async def set_progress(self, user_id: UUID, ayah_id: UUID, translation_id: UUID | None) -> dict:
        ayah = await self.db.get(QuranAyah, ayah_id)
        if not ayah or not ayah.published: raise AppError("quran_ayah_not_found", "Published ayah not found", 404)
        if translation_id:
            translation = await self.db.get(QuranTranslationEdition, translation_id)
            if not translation or not translation.published: raise AppError("quran_translation_not_found", "Published translation not found", 404)
        progress = await self.db.scalar(select(QuranReadingProgress).where(QuranReadingProgress.user_id == user_id))
        if progress: progress.ayah_id = ayah_id; progress.translation_edition_id = translation_id
        else: progress = QuranReadingProgress(user_id=user_id, ayah_id=ayah_id, translation_edition_id=translation_id); self.db.add(progress)
        await self.db.flush(); return {"ayah_id": ayah.id, "canonical_reference": ayah.canonical_reference, "translation_edition_id": translation_id}

    async def get_progress(self, user_id: UUID) -> dict | None:
        row = (await self.db.execute(select(QuranReadingProgress, QuranAyah.canonical_reference).join(QuranAyah, QuranAyah.id == QuranReadingProgress.ayah_id).where(QuranReadingProgress.user_id == user_id))).first()
        if not row: return None
        progress, reference = row; return {"ayah_id": progress.ayah_id, "canonical_reference": reference, "translation_edition_id": progress.translation_edition_id}


    async def get_preferences(self, user_id: UUID) -> dict:
        preference = await self.db.scalar(select(QuranReaderPreference).where(QuranReaderPreference.user_id == user_id))
        if not preference:
            return {"id": UUID(int=0), "translation_edition_id": None, "show_translation": True, "arabic_font_scale": 100, "theme": "system"}
        return preference

    async def set_preferences(self, user_id: UUID, payload) -> QuranReaderPreference:
        if payload.translation_edition_id:
            translation = await self.db.get(QuranTranslationEdition, payload.translation_edition_id)
            if not translation or not translation.published:
                raise AppError("quran_translation_not_found", "Published translation not found", 404)
        preference = await self.db.scalar(select(QuranReaderPreference).where(QuranReaderPreference.user_id == user_id))
        if preference:
            for key, value in payload.model_dump().items(): setattr(preference, key, value)
        else:
            preference = QuranReaderPreference(user_id=user_id, **payload.model_dump()); self.db.add(preference)
        await self.db.flush(); return preference

    async def create_text_edition(self, payload: QuranTextEditionCreate) -> QuranTextEdition:
        source_edition = await self.db.get(SourceEdition, payload.source_edition_id)
        if not source_edition or not source_edition.approved_for_retrieval or source_edition.review_status != "approved": raise AppError("quran_source_not_approved", "Qur'an edition requires an approved source edition", 409)
        edition = QuranTextEdition(**payload.model_dump()); self.db.add(edition); await self.db.flush(); return edition

    async def create_surah(self, payload: QuranSurahCreate) -> QuranSurah:
        surah = QuranSurah(**payload.model_dump()); self.db.add(surah); await self.db.flush(); return surah

    async def create_ayah(self, edition_id: UUID, payload: QuranAyahCreate) -> QuranAyah:
        edition = await self.db.get(QuranTextEdition, edition_id); surah = await self.db.get(QuranSurah, payload.surah_id); passage = await self.db.get(SourcePassage, payload.source_passage_id)
        if not edition or not surah or not passage: raise AppError("quran_reference_invalid", "Edition, surah, or source passage is invalid", 422)
        if passage.edition_id != edition.source_edition_id or not passage.is_current: raise AppError("quran_provenance_mismatch", "Source passage does not belong to the approved Qur'an edition", 409)
        if payload.ayah_number > surah.ayah_count: raise AppError("quran_ayah_out_of_range", "Ayah number exceeds declared surah count", 422)
        ayah = QuranAyah(text_edition_id=edition.id, canonical_reference=f"{surah.surah_number}:{payload.ayah_number}", text_sha256=hashlib.sha256(payload.arabic_text.encode()).hexdigest(), **payload.model_dump()); self.db.add(ayah); await self.db.flush(); return ayah

    async def create_translation_edition(self, payload: QuranTranslationEditionCreate) -> QuranTranslationEdition:
        source_edition = await self.db.get(SourceEdition, payload.source_edition_id)
        if not source_edition or not source_edition.approved_for_retrieval or source_edition.review_status != "approved": raise AppError("translation_source_not_approved", "Translation requires an approved source edition", 409)
        translation = QuranTranslationEdition(**payload.model_dump()); self.db.add(translation); await self.db.flush(); return translation
    async def list_recitations(self) -> list[QuranRecitationEdition]:
        return list((await self.db.scalars(select(QuranRecitationEdition).where(QuranRecitationEdition.published.is_(True)).order_by(QuranRecitationEdition.display_name))).all())

    async def get_surah_audio(self, surah_number: int, recitation_key: str) -> list[dict]:
        edition = await self._canonical_edition()
        surah = await self.get_surah(surah_number)
        recitation = await self.db.scalar(select(QuranRecitationEdition).where(QuranRecitationEdition.recitation_key == recitation_key, QuranRecitationEdition.published.is_(True)))
        if not recitation:
            raise AppError("quran_recitation_not_found", "Recitation not found or unpublished", 404)
        rows = (await self.db.execute(select(QuranAyahAudio, QuranAyah.canonical_reference).join(QuranAyah, QuranAyah.id == QuranAyahAudio.ayah_id).where(QuranAyahAudio.recitation_edition_id == recitation.id, QuranAyahAudio.published.is_(True), QuranAyah.text_edition_id == edition.id, QuranAyah.surah_id == surah.id, QuranAyah.published.is_(True)).order_by(QuranAyah.ayah_number))).all()
        return [{"id": audio.id, "ayah_id": audio.ayah_id, "canonical_reference": reference, "audio_url": audio.audio_url, "duration_ms": audio.duration_ms} for audio, reference in rows]

    async def create_recitation_edition(self, payload: QuranRecitationEditionCreate) -> QuranRecitationEdition:
        source = await self.db.get(SourceEdition, payload.source_edition_id)
        if not source or source.review_status != "approved" or source.ingestion_status != "ready" or not source.approved_for_retrieval:
            raise AppError("recitation_source_not_approved", "Recitation requires an approved and retrieval-eligible source edition", 409)
        edition = QuranRecitationEdition(**payload.model_dump())
        self.db.add(edition); await self.db.flush(); return edition

    async def add_ayah_audio(self, recitation_id: UUID, payload: QuranAyahAudioCreate) -> QuranAyahAudio:
        recitation = await self.db.get(QuranRecitationEdition, recitation_id)
        ayah = await self.db.get(QuranAyah, payload.ayah_id)
        if not recitation or not ayah or not ayah.published:
            raise AppError("recitation_reference_invalid", "Recitation edition or published ayah is invalid", 422)
        audio = QuranAyahAudio(recitation_edition_id=recitation.id, **payload.model_dump())
        self.db.add(audio); await self.db.flush(); return audio

    async def publish_recitation(self, recitation_id: UUID) -> QuranRecitationEdition:
        recitation = await self.db.get(QuranRecitationEdition, recitation_id)
        if not recitation:
            raise AppError("quran_recitation_not_found", "Recitation edition not found", 404)
        source = await self.db.get(SourceEdition, recitation.source_edition_id)
        if not source or source.review_status != "approved" or source.ingestion_status != "ready" or not source.approved_for_retrieval:
            raise AppError("recitation_source_revoked", "The recitation source is no longer retrieval eligible", 409)
        count = await self.db.scalar(select(sa.func.count()).select_from(QuranAyahAudio).where(QuranAyahAudio.recitation_edition_id == recitation.id))
        if not count:
            raise AppError("recitation_audio_missing", "At least one verified ayah audio record is required", 409)
        await self.db.execute(sa.update(QuranAyahAudio).where(QuranAyahAudio.recitation_edition_id == recitation.id).values(published=True))
        recitation.published = True; await self.db.flush(); return recitation

    async def get_playback_progress(self, user_id: UUID) -> dict | None:
        row = (await self.db.execute(select(QuranPlaybackProgress, QuranAyah.canonical_reference).join(QuranAyahAudio, QuranAyahAudio.id == QuranPlaybackProgress.ayah_audio_id).join(QuranAyah, QuranAyah.id == QuranAyahAudio.ayah_id).where(QuranPlaybackProgress.user_id == user_id))).first()
        if not row: return None
        progress, reference = row
        return {"ayah_audio_id": progress.ayah_audio_id, "position_ms": progress.position_ms, "repeat_mode": progress.repeat_mode, "playback_rate": progress.playback_rate, "canonical_reference": reference}

    async def set_playback_progress(self, user_id: UUID, payload: QuranPlaybackProgressUpdate) -> dict:
        audio = await self.db.get(QuranAyahAudio, payload.ayah_audio_id)
        if not audio or not audio.published:
            raise AppError("quran_audio_not_found", "Published ayah audio not found", 404)
        if payload.position_ms > audio.duration_ms:
            raise AppError("quran_audio_position_invalid", "Playback position exceeds audio duration", 422)
        progress = await self.db.scalar(select(QuranPlaybackProgress).where(QuranPlaybackProgress.user_id == user_id))
        values = payload.model_dump()
        if progress:
            for key, value in values.items(): setattr(progress, key, value)
        else:
            progress = QuranPlaybackProgress(user_id=user_id, **values); self.db.add(progress)
        ayah = await self.db.get(QuranAyah, audio.ayah_id)
        await self.db.flush()
        return {**values, "canonical_reference": ayah.canonical_reference}

