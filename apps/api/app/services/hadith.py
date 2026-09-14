from hashlib import sha256
from uuid import UUID
from sqlalchemy import select

from app.core.errors import AppError
from app.models.hadith import HadithBook, HadithChapter, HadithCollection, HadithGrading, HadithIsnadNode, HadithNarration, HadithNarrator
from app.models.sources import SourceEdition, SourcePassage
from app.schemas.hadith import HadithBookCreate, HadithChapterCreate, HadithCollectionCreate, HadithGradingCreate, HadithIsnadNodeCreate, HadithNarrationCreate, HadithNarratorCreate


class HadithService:
    def __init__(self, db): self.db = db

    async def _approved_source(self, source_edition_id: UUID) -> SourceEdition:
        source = await self.db.get(SourceEdition, source_edition_id)
        if not source or source.review_status != "approved" or source.ingestion_status != "ready" or not source.approved_for_retrieval:
            raise AppError("hadith_source_not_approved", "Hadith content requires an approved retrieval-eligible source edition", 409)
        return source

    async def _passage_for(self, passage_id: UUID, source_edition_id: UUID) -> SourcePassage:
        passage = await self.db.get(SourcePassage, passage_id)
        if not passage or passage.source_edition_id != source_edition_id or not passage.is_current:
            raise AppError("hadith_provenance_invalid", "Hadith provenance passage is missing, stale, or belongs to another edition", 422)
        return passage

    async def list_collections(self):
        return list((await self.db.scalars(select(HadithCollection).where(HadithCollection.published.is_(True)).order_by(HadithCollection.display_title))).all())

    async def get_narration(self, reference: str):
        narration = await self.db.scalar(select(HadithNarration).where(HadithNarration.canonical_reference == reference, HadithNarration.published.is_(True)))
        if not narration: raise AppError("hadith_not_found", "Hadith narration not found or unpublished", 404)
        return narration

    async def create_collection(self, payload: HadithCollectionCreate):
        await self._approved_source(payload.source_edition_id)
        row = HadithCollection(**payload.model_dump()); self.db.add(row); await self.db.flush(); return row

    async def create_book(self, collection_id: UUID, payload: HadithBookCreate):
        collection = await self.db.get(HadithCollection, collection_id)
        if not collection: raise AppError("hadith_collection_not_found", "Hadith collection not found", 404)
        await self._passage_for(payload.source_passage_id, collection.source_edition_id)
        row = HadithBook(collection_id=collection_id, **payload.model_dump()); self.db.add(row); await self.db.flush(); return row

    async def create_chapter(self, book_id: UUID, payload: HadithChapterCreate):
        book = await self.db.get(HadithBook, book_id)
        collection = await self.db.get(HadithCollection, book.collection_id) if book else None
        if not book or not collection: raise AppError("hadith_book_not_found", "Hadith book not found", 404)
        await self._passage_for(payload.source_passage_id, collection.source_edition_id)
        row = HadithChapter(book_id=book_id, **payload.model_dump()); self.db.add(row); await self.db.flush(); return row

    async def create_narration(self, collection_id: UUID, payload: HadithNarrationCreate):
        collection = await self.db.get(HadithCollection, collection_id)
        book = await self.db.get(HadithBook, payload.book_id)
        if not collection or not book or book.collection_id != collection_id: raise AppError("hadith_hierarchy_invalid", "Book does not belong to the collection", 422)
        if payload.chapter_id:
            chapter = await self.db.get(HadithChapter, payload.chapter_id)
            if not chapter or chapter.book_id != book.id: raise AppError("hadith_hierarchy_invalid", "Chapter does not belong to the book", 422)
        await self._passage_for(payload.source_passage_id, collection.source_edition_id)
        reference = f"{collection.collection_key}:{payload.collection_hadith_number}"
        row = HadithNarration(collection_id=collection_id, canonical_reference=reference, matn_sha256=sha256(payload.arabic_matn.encode()).hexdigest(), **payload.model_dump())
        self.db.add(row); await self.db.flush(); return row

    async def create_narrator(self, payload: HadithNarratorCreate):
        row = HadithNarrator(**payload.model_dump()); self.db.add(row); await self.db.flush(); return row

    async def add_isnad_node(self, narration_id: UUID, payload: HadithIsnadNodeCreate):
        narration = await self.db.get(HadithNarration, narration_id)
        collection = await self.db.get(HadithCollection, narration.collection_id) if narration else None
        if not narration or not collection: raise AppError("hadith_not_found", "Hadith narration not found", 404)
        await self._passage_for(payload.source_passage_id, collection.source_edition_id)
        if payload.narrator_id and not await self.db.get(HadithNarrator, payload.narrator_id): raise AppError("hadith_narrator_not_found", "Narrator not found", 404)
        row = HadithIsnadNode(narration_id=narration_id, **payload.model_dump()); self.db.add(row); await self.db.flush(); return row

    async def add_grading(self, narration_id: UUID, payload: HadithGradingCreate):
        narration = await self.db.get(HadithNarration, narration_id)
        collection = await self.db.get(HadithCollection, narration.collection_id) if narration else None
        if not narration or not collection: raise AppError("hadith_not_found", "Hadith narration not found", 404)
        await self._passage_for(payload.source_passage_id, collection.source_edition_id)
        row = HadithGrading(narration_id=narration_id, **payload.model_dump()); self.db.add(row); await self.db.flush(); return row
