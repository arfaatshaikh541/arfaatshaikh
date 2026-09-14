from hashlib import sha256
from uuid import UUID
from sqlalchemy import select

from app.core.errors import AppError
from app.models.sources import SourceEdition, SourcePassage
from app.models.tafsir import TafsirAuthor, TafsirCollection, TafsirEdition, TafsirEntry, TafsirSection, TafsirTranslation, TafsirTranslationEdition, TafsirVolume
from app.schemas.tafsir import *


class TafsirService:
    def __init__(self, db): self.db = db

    async def _approved_source(self, source_edition_id: UUID) -> SourceEdition:
        source = await self.db.get(SourceEdition, source_edition_id)
        if not source or source.review_status != "approved" or source.ingestion_status != "ready" or not source.approved_for_retrieval:
            raise AppError("tafsir_source_not_approved", "Tafsir content requires an approved retrieval-eligible source edition", 409)
        return source

    async def _passage_for(self, passage_id: UUID, source_edition_id: UUID) -> SourcePassage:
        passage = await self.db.get(SourcePassage, passage_id)
        if not passage or passage.source_edition_id != source_edition_id or not passage.is_current:
            raise AppError("tafsir_provenance_invalid", "Tafsir provenance is missing, stale, or belongs to another edition", 422)
        return passage

    async def list_authors(self):
        return list((await self.db.scalars(select(TafsirAuthor).where(TafsirAuthor.published.is_(True)).order_by(TafsirAuthor.canonical_name))).all())

    async def list_collections(self):
        return list((await self.db.scalars(select(TafsirCollection).where(TafsirCollection.published.is_(True)).order_by(TafsirCollection.display_title))).all())

    async def get_collection(self, key: str):
        row = await self.db.scalar(select(TafsirCollection).where(TafsirCollection.collection_key == key, TafsirCollection.published.is_(True)))
        if not row: raise AppError("tafsir_collection_not_found", "Tafsir collection not found or unpublished", 404)
        return row

    async def get_entry(self, reference: str):
        row = await self.db.scalar(select(TafsirEntry).join(TafsirEdition, TafsirEdition.id == TafsirEntry.edition_id).where(TafsirEntry.canonical_reference == reference, TafsirEntry.published.is_(True), TafsirEdition.published.is_(True)))
        if not row: raise AppError("tafsir_entry_not_found", "Tafsir entry not found or unpublished", 404)
        return row

    async def create_author(self, payload: TafsirAuthorCreate):
        passage = await self.db.get(SourcePassage, payload.source_passage_id)
        if not passage or not passage.is_current: raise AppError("tafsir_author_provenance_invalid", "Author evidence passage is missing or stale", 422)
        await self._approved_source(passage.source_edition_id)
        row = TafsirAuthor(**payload.model_dump()); self.db.add(row); await self.db.flush(); return row

    async def create_collection(self, payload: TafsirCollectionCreate):
        if not await self.db.get(TafsirAuthor, payload.author_id): raise AppError("tafsir_author_not_found", "Tafsir author not found", 404)
        row = TafsirCollection(**payload.model_dump()); self.db.add(row); await self.db.flush(); return row

    async def create_edition(self, payload: TafsirEditionCreate):
        if not await self.db.get(TafsirCollection, payload.collection_id): raise AppError("tafsir_collection_not_found", "Tafsir collection not found", 404)
        await self._approved_source(payload.source_edition_id)
        row = TafsirEdition(**payload.model_dump()); self.db.add(row); await self.db.flush(); return row

    async def create_volume(self, edition_id: UUID, payload: TafsirVolumeCreate):
        edition = await self.db.get(TafsirEdition, edition_id)
        if not edition: raise AppError("tafsir_edition_not_found", "Tafsir edition not found", 404)
        await self._passage_for(payload.source_passage_id, edition.source_edition_id)
        row = TafsirVolume(edition_id=edition_id, **payload.model_dump()); self.db.add(row); await self.db.flush(); return row

    async def create_section(self, edition_id: UUID, payload: TafsirSectionCreate):
        edition = await self.db.get(TafsirEdition, edition_id)
        if not edition: raise AppError("tafsir_edition_not_found", "Tafsir edition not found", 404)
        if payload.volume_id:
            volume = await self.db.get(TafsirVolume, payload.volume_id)
            if not volume or volume.edition_id != edition_id: raise AppError("tafsir_hierarchy_invalid", "Volume does not belong to this edition", 422)
        await self._passage_for(payload.source_passage_id, edition.source_edition_id)
        row = TafsirSection(edition_id=edition_id, **payload.model_dump()); self.db.add(row); await self.db.flush(); return row

    async def create_entry(self, edition_id: UUID, payload: TafsirEntryCreate):
        edition = await self.db.get(TafsirEdition, edition_id)
        if not edition: raise AppError("tafsir_edition_not_found", "Tafsir edition not found", 404)
        if payload.section_id:
            section = await self.db.get(TafsirSection, payload.section_id)
            if not section or section.edition_id != edition_id: raise AppError("tafsir_hierarchy_invalid", "Section does not belong to this edition", 422)
        await self._passage_for(payload.source_passage_id, edition.source_edition_id)
        if payload.entry_type == "surah": ref = f"{edition.edition_key}:{payload.surah_number}"
        elif payload.entry_type == "ayah": ref = f"{edition.edition_key}:{payload.surah_number}:{payload.start_ayah_number}"
        elif payload.entry_type == "ayah_range": ref = f"{edition.edition_key}:{payload.surah_number}:{payload.start_ayah_number}-{payload.end_ayah_number}"
        else: ref = f"{edition.edition_key}:{payload.entry_type}:{payload.surah_number}"
        row = TafsirEntry(edition_id=edition_id, canonical_reference=ref, text_sha256=sha256(payload.arabic_text.encode("utf-8")).hexdigest(), **payload.model_dump())
        self.db.add(row); await self.db.flush(); return row

    async def create_translation_edition(self, payload: TafsirTranslationEditionCreate):
        tafsir_edition = await self.db.get(TafsirEdition, payload.tafsir_edition_id)
        if not tafsir_edition: raise AppError("tafsir_edition_not_found", "Tafsir edition not found", 404)
        await self._approved_source(payload.source_edition_id)
        row = TafsirTranslationEdition(**payload.model_dump()); self.db.add(row); await self.db.flush(); return row

    async def create_translation(self, payload: TafsirTranslationCreate):
        translation_edition = await self.db.get(TafsirTranslationEdition, payload.translation_edition_id)
        entry = await self.db.get(TafsirEntry, payload.tafsir_entry_id)
        if not translation_edition or not entry or entry.edition_id != translation_edition.tafsir_edition_id:
            raise AppError("tafsir_translation_hierarchy_invalid", "Translation and tafsir entry are not aligned", 422)
        await self._passage_for(payload.source_passage_id, translation_edition.source_edition_id)
        row = TafsirTranslation(text_sha256=sha256(payload.translated_text.encode("utf-8")).hexdigest(), **payload.model_dump())
        self.db.add(row); await self.db.flush(); return row
