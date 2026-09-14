from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.quran import (
    QuranAyah, QuranAyahTranslation, QuranTranslationEdition,
    QuranTranslationImportAyah, QuranTranslationImportBatch, QuranTranslationImportReview,
)
from app.models.sources import SourceEdition, SourcePassage
from app.schemas.quran import (
    QuranTranslationImportAyahCreate, QuranTranslationImportManifestCreate,
    QuranTranslationImportReviewCreate,
)


class QuranTranslationImportService:
    def __init__(self, db: AsyncSession): self.db = db

    async def create_batch(self, payload: QuranTranslationImportManifestCreate, user_id: UUID):
        edition = await self.db.get(QuranTranslationEdition, payload.translation_edition_id)
        if not edition or edition.published:
            raise AppError("translation_import_edition_invalid", "Translation edition is missing or already published", 409)
        source = await self.db.get(SourceEdition, edition.source_edition_id)
        if not source or source.review_status != "approved" or not source.approved_for_retrieval:
            raise AppError("translation_source_not_approved", "Translation source is not approved for retrieval", 409)
        batch = QuranTranslationImportBatch(**payload.model_dump(), submitted_by_user_id=user_id)
        self.db.add(batch); await self.db.flush(); return batch

    async def add_ayah(self, batch_id: UUID, payload: QuranTranslationImportAyahCreate):
        batch = await self.db.get(QuranTranslationImportBatch, batch_id)
        if not batch or batch.status != "draft": raise AppError("translation_import_not_editable", "Import batch is not editable", 409)
        edition = await self.db.get(QuranTranslationEdition, batch.translation_edition_id)
        ayah = await self.db.get(QuranAyah, payload.ayah_id)
        passage = await self.db.get(SourcePassage, payload.source_passage_id)
        if not edition or not ayah or not ayah.published or not passage:
            raise AppError("translation_import_reference_invalid", "Ayah or source passage is invalid", 422)
        if passage.edition_id != edition.source_edition_id or not passage.is_current:
            raise AppError("translation_provenance_mismatch", "Translation passage does not belong to its approved source edition", 409)
        item = QuranTranslationImportAyah(import_batch_id=batch.id, text_sha256=hashlib.sha256(payload.translated_text.encode("utf-8")).hexdigest(), **payload.model_dump())
        self.db.add(item); await self.db.flush(); return item

    async def validate_batch(self, batch_id: UUID):
        batch = await self.db.get(QuranTranslationImportBatch, batch_id)
        if not batch or batch.status != "draft": raise AppError("translation_import_not_validatable", "Import batch is not in draft", 409)
        rows = list((await self.db.scalars(select(QuranTranslationImportAyah).where(QuranTranslationImportAyah.import_batch_id == batch.id).order_by(QuranTranslationImportAyah.ayah_id))).all())
        lines = [f"{row.ayah_id}\t{row.text_sha256}\t{row.source_passage_id}" for row in rows]
        digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
        if len(rows) != batch.expected_ayah_count or digest != batch.manifest_sha256:
            batch.status = "failed"; batch.validation_summary = f"count={len(rows)} expected={batch.expected_ayah_count} manifest_match={digest == batch.manifest_sha256}"
            raise AppError("translation_manifest_mismatch", "Translation manifest reconciliation failed", 409)
        for row in rows: row.validation_status = "valid"; row.validation_errors = None
        batch.status = "review_pending"; batch.validation_summary = f"validated {len(rows)} translation records"
        await self.db.flush(); return batch

    async def review_batch(self, batch_id: UUID, reviewer_id: UUID, payload: QuranTranslationImportReviewCreate):
        batch = await self.db.get(QuranTranslationImportBatch, batch_id)
        if not batch or batch.status != "review_pending": raise AppError("translation_import_not_reviewable", "Import is not pending review", 409)
        review = QuranTranslationImportReview(import_batch_id=batch.id, reviewer_user_id=reviewer_id, decision=payload.decision, rationale=payload.rationale, created_at=datetime.now(timezone.utc))
        self.db.add(review)
        batch.status = "approved" if payload.decision == "approved" else "rejected"
        await self.db.flush(); return batch

    async def publish_batch(self, batch_id: UUID):
        batch = await self.db.get(QuranTranslationImportBatch, batch_id)
        if not batch or batch.status != "approved": raise AppError("translation_import_not_approved", "Import requires an approving review", 409)
        edition = await self.db.get(QuranTranslationEdition, batch.translation_edition_id)
        source = await self.db.get(SourceEdition, edition.source_edition_id) if edition else None
        if not edition or not source or source.review_status != "approved" or not source.approved_for_retrieval:
            raise AppError("translation_source_revoked", "Translation source approval is no longer valid", 409)
        existing = await self.db.scalar(select(QuranAyahTranslation.id).where(QuranAyahTranslation.translation_edition_id == edition.id).limit(1))
        if existing: raise AppError("translation_edition_not_empty", "Translation edition already contains records", 409)
        rows = list((await self.db.scalars(select(QuranTranslationImportAyah).where(QuranTranslationImportAyah.import_batch_id == batch.id, QuranTranslationImportAyah.validation_status == "valid"))).all())
        if len(rows) != batch.expected_ayah_count: raise AppError("translation_import_incomplete", "Validated translation count changed before publication", 409)
        for row in rows:
            self.db.add(QuranAyahTranslation(translation_edition_id=edition.id, ayah_id=row.ayah_id, translated_text=row.translated_text, text_sha256=row.text_sha256, source_passage_id=row.source_passage_id, published=True))
        edition.published = True; batch.status = "published"; batch.published_at = datetime.now(timezone.utc)
        await self.db.flush(); return batch
