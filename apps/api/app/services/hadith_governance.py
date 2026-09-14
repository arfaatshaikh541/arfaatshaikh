from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.core.errors import AppError
from app.models.hadith import (
    HadithCollection, HadithBook, HadithChapter, HadithNarration, HadithGrading,
    HadithTranslationEdition, HadithTranslation,
    HadithTranslationImportBatch, HadithTranslationImportItem, HadithTranslationImportReview,
    HadithGradingImportBatch, HadithGradingImportItem, HadithGradingImportReview,
)
from app.models.sources import SourceEdition, SourcePassage
from app.schemas.hadith import (
    HadithTranslationEditionCreate, HadithTranslationImportManifestCreate,
    HadithTranslationImportItemCreate, HadithGradingImportManifestCreate,
    HadithGradingImportItemCreate, HadithGovernedReviewCreate,
)


class HadithGovernanceService:
    def __init__(self, db): self.db = db

    async def _approved_source(self, edition_id: UUID) -> SourceEdition:
        row = await self.db.get(SourceEdition, edition_id)
        if not row or row.review_status != "approved" or row.ingestion_status != "ready" or not row.approved_for_retrieval:
            raise AppError("hadith_source_not_approved", "Source edition is not approved for hadith retrieval", 409)
        return row

    async def _current_passage(self, passage_id: UUID, edition_id: UUID) -> SourcePassage:
        row = await self.db.get(SourcePassage, passage_id)
        if not row or row.edition_id != edition_id or not row.is_current:
            raise AppError("hadith_provenance_invalid", "Source passage is missing, stale, or belongs to another edition", 422)
        return row

    async def create_translation_edition(self, payload: HadithTranslationEditionCreate):
        await self._approved_source(payload.source_edition_id)
        row = HadithTranslationEdition(**payload.model_dump())
        self.db.add(row); await self.db.flush(); return row

    async def create_translation_batch(self, payload: HadithTranslationImportManifestCreate, user_id: UUID):
        edition = await self.db.get(HadithTranslationEdition, payload.translation_edition_id)
        if not edition or edition.published:
            raise AppError("hadith_translation_edition_invalid", "Translation edition is missing or already published", 409)
        await self._approved_source(edition.source_edition_id)
        row = HadithTranslationImportBatch(**payload.model_dump(), submitted_by_user_id=user_id)
        self.db.add(row); await self.db.flush(); return row

    async def add_translation_item(self, batch_id: UUID, payload: HadithTranslationImportItemCreate):
        batch = await self.db.get(HadithTranslationImportBatch, batch_id)
        edition = await self.db.get(HadithTranslationEdition, batch.translation_edition_id) if batch else None
        narration = await self.db.get(HadithNarration, payload.narration_id)
        if not batch or batch.status != "draft" or not edition:
            raise AppError("hadith_translation_import_not_editable", "Translation import is not editable", 409)
        if not narration or not narration.published:
            raise AppError("hadith_translation_narration_invalid", "Translation requires a published narration", 422)
        await self._current_passage(payload.source_passage_id, edition.source_edition_id)
        row = HadithTranslationImportItem(
            import_batch_id=batch.id,
            text_sha256=hashlib.sha256(payload.translated_text.encode("utf-8")).hexdigest(),
            **payload.model_dump(),
        )
        self.db.add(row); await self.db.flush(); return row

    async def validate_translation_batch(self, batch_id: UUID):
        batch = await self.db.get(HadithTranslationImportBatch, batch_id)
        if not batch or batch.status != "draft":
            raise AppError("hadith_translation_import_not_validatable", "Translation import is not in draft", 409)
        rows = list((await self.db.scalars(select(HadithTranslationImportItem).where(HadithTranslationImportItem.import_batch_id == batch.id).order_by(HadithTranslationImportItem.narration_id))).all())
        digest = hashlib.sha256("\n".join(f"{r.narration_id}\t{r.text_sha256}\t{r.source_passage_id}" for r in rows).encode("utf-8")).hexdigest()
        if len(rows) != batch.expected_record_count or digest != batch.manifest_sha256:
            batch.status = "failed"; batch.validation_summary = f"count={len(rows)} manifest_match={digest == batch.manifest_sha256}"
            raise AppError("hadith_translation_manifest_mismatch", "Translation manifest reconciliation failed", 409)
        for row in rows: row.validation_status = "valid"
        batch.status = "review_pending"; batch.validation_summary = f"validated {len(rows)} translation records"
        await self.db.flush(); return batch

    async def review_translation_batch(self, batch_id: UUID, reviewer_id: UUID, payload: HadithGovernedReviewCreate):
        batch = await self.db.get(HadithTranslationImportBatch, batch_id)
        if not batch or batch.status != "review_pending": raise AppError("hadith_translation_not_reviewable", "Translation import is not pending review", 409)
        self.db.add(HadithTranslationImportReview(import_batch_id=batch.id, reviewer_user_id=reviewer_id, decision=payload.decision, rationale=payload.rationale, created_at=datetime.now(timezone.utc)))
        batch.status = "approved" if payload.decision == "approved" else "rejected"
        await self.db.flush(); return batch

    async def publish_translation_batch(self, batch_id: UUID):
        batch = await self.db.get(HadithTranslationImportBatch, batch_id)
        edition = await self.db.get(HadithTranslationEdition, batch.translation_edition_id) if batch else None
        if not batch or batch.status != "approved" or not edition:
            raise AppError("hadith_translation_not_approved", "Translation import requires approval", 409)
        await self._approved_source(edition.source_edition_id)
        existing = await self.db.scalar(select(HadithTranslation.id).where(HadithTranslation.translation_edition_id == edition.id).limit(1))
        if existing: raise AppError("hadith_translation_edition_not_empty", "Translation edition already contains records", 409)
        rows = list((await self.db.scalars(select(HadithTranslationImportItem).where(HadithTranslationImportItem.import_batch_id == batch.id, HadithTranslationImportItem.validation_status == "valid"))).all())
        if len(rows) != batch.expected_record_count: raise AppError("hadith_translation_import_changed", "Validated translation count changed before publication", 409)
        for row in rows:
            await self._current_passage(row.source_passage_id, edition.source_edition_id)
            self.db.add(HadithTranslation(translation_edition_id=edition.id, narration_id=row.narration_id, translated_text=row.translated_text, text_sha256=row.text_sha256, source_passage_id=row.source_passage_id, published=True))
        edition.published = True; batch.status = "published"; batch.published_at = datetime.now(timezone.utc)
        await self.db.flush(); return batch

    async def create_grading_batch(self, payload: HadithGradingImportManifestCreate, user_id: UUID):
        collection = await self.db.get(HadithCollection, payload.collection_id)
        if not collection: raise AppError("hadith_collection_not_found", "Hadith collection not found", 404)
        await self._approved_source(payload.source_edition_id)
        row = HadithGradingImportBatch(**payload.model_dump(), submitted_by_user_id=user_id)
        self.db.add(row); await self.db.flush(); return row

    async def add_grading_item(self, batch_id: UUID, payload: HadithGradingImportItemCreate):
        batch = await self.db.get(HadithGradingImportBatch, batch_id)
        narration = await self.db.get(HadithNarration, payload.narration_id)
        if not batch or batch.status != "draft": raise AppError("hadith_grading_import_not_editable", "Grading import is not editable", 409)
        if not narration or not narration.published or narration.collection_id != batch.collection_id:
            raise AppError("hadith_grading_narration_invalid", "Grading narration is invalid for this collection", 422)
        await self._current_passage(payload.source_passage_id, batch.source_edition_id)
        row = HadithGradingImportItem(import_batch_id=batch.id, **payload.model_dump())
        self.db.add(row); await self.db.flush(); return row

    async def validate_grading_batch(self, batch_id: UUID):
        batch = await self.db.get(HadithGradingImportBatch, batch_id)
        if not batch or batch.status != "draft": raise AppError("hadith_grading_import_not_validatable", "Grading import is not in draft", 409)
        rows = list((await self.db.scalars(select(HadithGradingImportItem).where(HadithGradingImportItem.import_batch_id == batch.id).order_by(HadithGradingImportItem.narration_id, HadithGradingImportItem.grader_name, HadithGradingImportItem.grading_label))).all())
        digest = hashlib.sha256("\n".join(f"{r.narration_id}\t{r.grader_name}\t{r.grading_label}\t{r.source_passage_id}" for r in rows).encode("utf-8")).hexdigest()
        if len(rows) != batch.expected_record_count or digest != batch.manifest_sha256:
            batch.status = "failed"; batch.validation_summary = f"count={len(rows)} manifest_match={digest == batch.manifest_sha256}"
            raise AppError("hadith_grading_manifest_mismatch", "Grading manifest reconciliation failed", 409)
        for row in rows: row.validation_status = "valid"
        batch.status = "review_pending"; batch.validation_summary = f"validated {len(rows)} attributed grading opinions"
        await self.db.flush(); return batch

    async def review_grading_batch(self, batch_id: UUID, reviewer_id: UUID, payload: HadithGovernedReviewCreate):
        batch = await self.db.get(HadithGradingImportBatch, batch_id)
        if not batch or batch.status != "review_pending": raise AppError("hadith_grading_not_reviewable", "Grading import is not pending review", 409)
        self.db.add(HadithGradingImportReview(import_batch_id=batch.id, reviewer_user_id=reviewer_id, decision=payload.decision, rationale=payload.rationale, created_at=datetime.now(timezone.utc)))
        batch.status = "approved" if payload.decision == "approved" else "rejected"
        await self.db.flush(); return batch

    async def publish_grading_batch(self, batch_id: UUID):
        batch = await self.db.get(HadithGradingImportBatch, batch_id)
        if not batch or batch.status != "approved": raise AppError("hadith_grading_not_approved", "Grading import requires approval", 409)
        await self._approved_source(batch.source_edition_id)
        rows = list((await self.db.scalars(select(HadithGradingImportItem).where(HadithGradingImportItem.import_batch_id == batch.id, HadithGradingImportItem.validation_status == "valid"))).all())
        if len(rows) != batch.expected_record_count: raise AppError("hadith_grading_import_changed", "Validated grading count changed before publication", 409)
        for row in rows:
            await self._current_passage(row.source_passage_id, batch.source_edition_id)
            self.db.add(HadithGrading(narration_id=row.narration_id, grader_name=row.grader_name, grading_label=row.grading_label, grading_text=row.grading_text, methodology_note=row.methodology_note, source_passage_id=row.source_passage_id, published=True))
        batch.status = "published"; batch.published_at = datetime.now(timezone.utc)
        await self.db.flush(); return batch


class HadithReadingService:
    def __init__(self, db): self.db = db

    async def list_books(self, collection_key: str):
        collection = await self.db.scalar(select(HadithCollection).where(HadithCollection.collection_key == collection_key, HadithCollection.published.is_(True)))
        if not collection: raise AppError("hadith_collection_not_found", "Hadith collection not found", 404)
        return list((await self.db.scalars(select(HadithBook).where(HadithBook.collection_id == collection.id, HadithBook.published.is_(True)).order_by(HadithBook.book_number))).all())

    async def list_chapters(self, collection_key: str, book_number: int):
        collection = await self.db.scalar(select(HadithCollection).where(HadithCollection.collection_key == collection_key, HadithCollection.published.is_(True)))
        book = await self.db.scalar(select(HadithBook).where(HadithBook.collection_id == collection.id, HadithBook.book_number == book_number, HadithBook.published.is_(True))) if collection else None
        if not book: raise AppError("hadith_book_not_found", "Hadith book not found", 404)
        return list((await self.db.scalars(select(HadithChapter).where(HadithChapter.book_id == book.id, HadithChapter.published.is_(True)).order_by(HadithChapter.chapter_number))).all())

    async def chapter_reading(self, collection_key: str, book_number: int, chapter_number: int, translation: str | None = None):
        collection = await self.db.scalar(select(HadithCollection).where(HadithCollection.collection_key == collection_key, HadithCollection.published.is_(True)))
        book = await self.db.scalar(select(HadithBook).where(HadithBook.collection_id == collection.id, HadithBook.book_number == book_number, HadithBook.published.is_(True))) if collection else None
        chapter = await self.db.scalar(select(HadithChapter).where(HadithChapter.book_id == book.id, HadithChapter.chapter_number == chapter_number, HadithChapter.published.is_(True))) if book else None
        if not collection or not book or not chapter: raise AppError("hadith_chapter_not_found", "Hadith chapter not found", 404)
        narrations = list((await self.db.scalars(select(HadithNarration).where(HadithNarration.chapter_id == chapter.id, HadithNarration.published.is_(True)).order_by(HadithNarration.collection_hadith_number))).all())
        translation_edition = None
        if translation:
            translation_edition = await self.db.scalar(select(HadithTranslationEdition).where(HadithTranslationEdition.translation_key == translation, HadithTranslationEdition.published.is_(True)))
            if not translation_edition: raise AppError("hadith_translation_not_found", "Published hadith translation not found", 404)
        payload = []
        for narration in narrations:
            translations = []
            if translation_edition:
                tr = await self.db.scalar(select(HadithTranslation).where(HadithTranslation.translation_edition_id == translation_edition.id, HadithTranslation.narration_id == narration.id, HadithTranslation.published.is_(True)))
                if tr:
                    translations.append({"translation_key": translation_edition.translation_key, "language": translation_edition.language, "translator_name": translation_edition.translator_name, "attribution_text": translation_edition.attribution_text, "translated_text": tr.translated_text})
            gradings = list((await self.db.scalars(select(HadithGrading).where(HadithGrading.narration_id == narration.id, HadithGrading.published.is_(True)).order_by(HadithGrading.grader_name, HadithGrading.grading_label))).all())
            payload.append({"id": narration.id, "canonical_reference": narration.canonical_reference, "collection_hadith_number": narration.collection_hadith_number, "arabic_matn": narration.arabic_matn, "translations": translations, "gradings": [{"grader_name": g.grader_name, "grading_label": g.grading_label, "grading_text": g.grading_text, "methodology_note": g.methodology_note} for g in gradings]})
        return {"collection_key": collection.collection_key, "collection_title": collection.display_title, "book_number": book.book_number, "book_title": book.display_title, "chapter_number": chapter.chapter_number, "chapter_title": chapter.display_title, "narrations": payload}
