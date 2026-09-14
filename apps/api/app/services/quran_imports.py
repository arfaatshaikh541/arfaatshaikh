from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.quran import (
    QuranAyah,
    QuranImportAyah,
    QuranImportBatch,
    QuranImportEvent,
    QuranImportReview,
    QuranSurah,
    QuranTextEdition,
)
from app.models.sources import SourceEdition, SourcePassage
from app.schemas.quran import QuranImportAyahCreate, QuranImportManifestCreate, QuranImportReviewCreate


class QuranImportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_batch(self, payload: QuranImportManifestCreate, actor_id: UUID) -> QuranImportBatch:
        edition = await self.db.get(QuranTextEdition, payload.text_edition_id)
        if not edition:
            raise AppError("quran_edition_not_found", "Qur'an text edition not found", 404)
        source = await self.db.get(SourceEdition, edition.source_edition_id)
        if not source or not source.approved_for_retrieval or source.review_status != "approved" or source.ingestion_status != "ready":
            raise AppError("quran_import_source_not_ready", "The linked source edition is not approved and ready", 409)
        active = await self.db.scalar(select(QuranImportBatch).where(QuranImportBatch.text_edition_id == edition.id, QuranImportBatch.status.in_(["draft", "validating", "validated", "review_pending", "approved"])))
        if active:
            raise AppError("quran_import_already_active", "An active import already exists for this edition", 409)
        batch = QuranImportBatch(**payload.model_dump(), submitted_by_user_id=actor_id)
        self.db.add(batch)
        await self.db.flush()
        await self._event(batch, actor_id, "import.created", None, "draft", "Import manifest registered")
        return batch

    async def add_ayah(self, batch_id: UUID, payload: QuranImportAyahCreate, actor_id: UUID) -> QuranImportAyah:
        batch = await self._batch(batch_id)
        if batch.status != "draft":
            raise AppError("quran_import_locked", "Ayahs can only be added while an import is in draft", 409)
        edition = await self.db.get(QuranTextEdition, batch.text_edition_id)
        passage = await self.db.get(SourcePassage, payload.source_passage_id)
        surah = await self.db.scalar(select(QuranSurah).where(QuranSurah.surah_number == payload.surah_number))
        if not edition or not passage or not surah:
            raise AppError("quran_import_reference_invalid", "Edition, source passage, or surah is invalid", 422)
        if passage.edition_id != edition.source_edition_id or not passage.is_current:
            raise AppError("quran_import_provenance_mismatch", "Ayah provenance does not belong to this approved edition", 409)
        if payload.ayah_number > surah.ayah_count:
            raise AppError("quran_import_ayah_out_of_range", "Ayah exceeds the canonical surah count", 422)
        reference = f"{payload.surah_number}:{payload.ayah_number}"
        digest = hashlib.sha256(payload.arabic_text.encode("utf-8")).hexdigest()
        metadata = payload.model_dump(exclude={"surah_number", "ayah_number", "arabic_text", "source_passage_id"})
        item = QuranImportAyah(import_batch_id=batch.id, surah_number=payload.surah_number, ayah_number=payload.ayah_number, canonical_reference=reference, arabic_text=payload.arabic_text, text_sha256=digest, source_passage_id=payload.source_passage_id, metadata_json=json.dumps(metadata, sort_keys=True, separators=(",", ":")))
        self.db.add(item)
        await self.db.flush()
        return item

    async def validate_batch(self, batch_id: UUID, actor_id: UUID) -> QuranImportBatch:
        batch = await self._batch(batch_id)
        if batch.status not in {"draft", "failed"}:
            raise AppError("quran_import_invalid_transition", "Import cannot be validated from its current state", 409)
        old = batch.status
        batch.status = "validating"
        await self.db.flush()
        items = list(await self.db.scalars(select(QuranImportAyah).where(QuranImportAyah.import_batch_id == batch.id).order_by(QuranImportAyah.surah_number, QuranImportAyah.ayah_number)))
        errors: list[str] = []
        if len(items) != batch.expected_ayah_count:
            errors.append(f"expected {batch.expected_ayah_count} ayahs but received {len(items)}")
        by_surah = Counter(i.surah_number for i in items)
        if len(by_surah) != batch.expected_surah_count:
            errors.append(f"expected {batch.expected_surah_count} surahs but received {len(by_surah)}")
        canonical_surahs = list(await self.db.scalars(select(QuranSurah).order_by(QuranSurah.surah_number)))
        expected_counts = {s.surah_number: s.ayah_count for s in canonical_surahs}
        for number, expected in expected_counts.items():
            actual = by_surah.get(number, 0)
            if actual != expected:
                errors.append(f"surah {number} expected {expected} ayahs but received {actual}")
        ordered_manifest = "\n".join(f"{i.canonical_reference}\t{i.text_sha256}\t{i.source_passage_id}" for i in items)
        calculated_manifest = hashlib.sha256(ordered_manifest.encode("utf-8")).hexdigest()
        if calculated_manifest != batch.manifest_sha256:
            errors.append("manifest checksum mismatch")
        for item in items:
            item.validation_status = "invalid" if errors else "valid"
            item.validation_errors = "; ".join(errors) if errors else None
        batch.validated_at = datetime.now(timezone.utc)
        batch.validation_summary = "; ".join(errors) if errors else f"Validated {len(items)} ayahs across {len(by_surah)} surahs"
        batch.status = "failed" if errors else "review_pending"
        await self._event(batch, actor_id, "import.validation_failed" if errors else "import.validated", old, batch.status, batch.validation_summary)
        return batch

    async def review_batch(self, batch_id: UUID, reviewer_id: UUID, payload: QuranImportReviewCreate) -> QuranImportBatch:
        batch = await self._batch(batch_id)
        if batch.status != "review_pending":
            raise AppError("quran_import_not_reviewable", "Only validated imports can be reviewed", 409)
        review = QuranImportReview(import_batch_id=batch.id, reviewer_user_id=reviewer_id, decision=payload.decision, rationale=payload.rationale, created_at=datetime.now(timezone.utc))
        self.db.add(review)
        old = batch.status
        batch.status = "approved" if payload.decision == "approved" else "rejected"
        await self._event(batch, reviewer_id, f"import.review_{payload.decision}", old, batch.status, payload.rationale)
        return batch

    async def publish_batch(self, batch_id: UUID, actor_id: UUID) -> QuranImportBatch:
        batch = await self._batch(batch_id)
        if batch.status != "approved":
            raise AppError("quran_import_not_approved", "Import must have an approved review before publication", 409)
        edition = await self.db.get(QuranTextEdition, batch.text_edition_id)
        source = await self.db.get(SourceEdition, edition.source_edition_id) if edition else None
        if not edition or not source or not source.approved_for_retrieval or source.review_status != "approved" or source.ingestion_status != "ready":
            raise AppError("quran_publication_source_closed", "The source edition is no longer retrieval eligible", 409)
        items = list(await self.db.scalars(select(QuranImportAyah).where(QuranImportAyah.import_batch_id == batch.id, QuranImportAyah.validation_status == "valid").order_by(QuranImportAyah.surah_number, QuranImportAyah.ayah_number)))
        if len(items) != batch.expected_ayah_count:
            raise AppError("quran_publication_incomplete", "Validated ayah count no longer matches the manifest", 409)
        existing = await self.db.scalar(select(func.count()).select_from(QuranAyah).where(QuranAyah.text_edition_id == edition.id))
        if existing:
            raise AppError("quran_edition_already_populated", "This edition already contains ayahs", 409)
        surahs = {s.surah_number: s for s in await self.db.scalars(select(QuranSurah))}
        for item in items:
            metadata = json.loads(item.metadata_json)
            self.db.add(QuranAyah(text_edition_id=edition.id, surah_id=surahs[item.surah_number].id, ayah_number=item.ayah_number, canonical_reference=item.canonical_reference, arabic_text=item.arabic_text, text_sha256=item.text_sha256, source_passage_id=item.source_passage_id, published=True, **metadata))
        edition.published = True
        batch.status = "published"
        batch.published_at = datetime.now(timezone.utc)
        await self._event(batch, actor_id, "import.published", "approved", "published", f"Published {len(items)} provenance-linked ayahs")
        return batch

    async def _batch(self, batch_id: UUID) -> QuranImportBatch:
        batch = await self.db.get(QuranImportBatch, batch_id)
        if not batch:
            raise AppError("quran_import_not_found", "Qur'an import batch not found", 404)
        return batch

    async def _event(self, batch: QuranImportBatch, actor_id: UUID, event_type: str, from_status: str | None, to_status: str | None, details: str) -> None:
        self.db.add(QuranImportEvent(import_batch_id=batch.id, actor_user_id=actor_id, event_type=event_type, from_status=from_status, to_status=to_status, details=details, created_at=datetime.now(timezone.utc)))
        await self.db.flush()
