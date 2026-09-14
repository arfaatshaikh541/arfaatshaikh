from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select

from app.core.errors import AppError
from app.models.identity import User
from app.models.sources import SourceEdition, SourcePassage
from app.models.tafsir import (
    TafsirEdition,
    TafsirEntry,
    TafsirImportBatch,
    TafsirImportEntry,
    TafsirImportEvent,
    TafsirImportReview,
    TafsirImportReviewAssignment,
    TafsirSection,
    TafsirVolume,
)
from app.schemas.tafsir import (
    TafsirImportBatchCreate,
    TafsirImportEntryCreate,
    TafsirImportReviewAssignmentCreate,
    TafsirImportReviewCreate,
)

REQUIRED_REVIEW_DOMAINS = {"tafsir_text", "source_provenance", "arabic_language"}


def calculate_tafsir_manifest_sha256(items: list[TafsirImportEntry]) -> str:
    lines = [
        "\t".join(
            [
                item.canonical_reference,
                item.text_sha256,
                str(item.source_passage_id),
                str(item.volume_number or ""),
                item.section_key or "",
            ]
        )
        for item in sorted(items, key=lambda i: (i.canonical_reference, str(i.id)))
    ]
    return sha256("\n".join(lines).encode("utf-8")).hexdigest()


class TafsirImportService:
    def __init__(self, db):
        self.db = db

    async def _batch(self, batch_id: UUID) -> TafsirImportBatch:
        batch = await self.db.get(TafsirImportBatch, batch_id)
        if not batch:
            raise AppError("tafsir_import_not_found", "Tafsir import batch not found", 404)
        return batch

    async def _approved_source(self, source_edition_id: UUID) -> SourceEdition:
        source = await self.db.get(SourceEdition, source_edition_id)
        if not source or source.review_status != "approved" or source.ingestion_status != "ready" or not source.approved_for_retrieval:
            raise AppError("tafsir_source_not_approved", "Tafsir import requires an approved retrieval-eligible source edition", 409)
        return source

    async def _passage_for(self, passage_id: UUID, source_edition_id: UUID) -> SourcePassage:
        passage = await self.db.get(SourcePassage, passage_id)
        if not passage or passage.source_edition_id != source_edition_id or not passage.is_current:
            raise AppError("tafsir_provenance_invalid", "Tafsir provenance is stale, missing, or belongs to another edition", 422)
        return passage

    async def _event(self, batch: TafsirImportBatch, actor_id: UUID, event_type: str, old: str | None, new: str | None, details: str) -> None:
        self.db.add(TafsirImportEvent(
            import_batch_id=batch.id,
            actor_user_id=actor_id,
            event_type=event_type,
            from_status=old,
            to_status=new,
            details=details,
            created_at=datetime.now(timezone.utc),
        ))

    async def create_batch(self, payload: TafsirImportBatchCreate, actor_id: UUID) -> TafsirImportBatch:
        edition = await self.db.get(TafsirEdition, payload.edition_id)
        if not edition:
            raise AppError("tafsir_edition_not_found", "Tafsir edition not found", 404)
        await self._approved_source(edition.source_edition_id)
        existing = await self.db.scalar(select(TafsirImportBatch).where(
            TafsirImportBatch.edition_id == edition.id,
            TafsirImportBatch.status.in_(["draft", "validating", "review_pending", "approved"]),
        ))
        if existing:
            raise AppError("tafsir_import_active", "This edition already has an active import batch", 409)
        batch = TafsirImportBatch(submitted_by_user_id=actor_id, **payload.model_dump())
        self.db.add(batch)
        await self.db.flush()
        await self._event(batch, actor_id, "tafsir_import.created", None, "draft", "Controlled tafsir import batch created")
        return batch

    async def add_entry(self, batch_id: UUID, payload: TafsirImportEntryCreate, actor_id: UUID) -> TafsirImportEntry:
        batch = await self._batch(batch_id)
        if batch.status != "draft":
            raise AppError("tafsir_import_locked", "Entries can only be staged while the batch is draft", 409)
        edition = await self.db.get(TafsirEdition, batch.edition_id)
        if not edition:
            raise AppError("tafsir_edition_not_found", "Tafsir edition not found", 404)
        for passage_id in (payload.volume_source_passage_id, payload.section_source_passage_id, payload.source_passage_id):
            if passage_id:
                await self._passage_for(passage_id, edition.source_edition_id)
        if payload.entry_type == "surah":
            reference = f"{edition.edition_key}:{payload.surah_number}"
        elif payload.entry_type == "ayah":
            reference = f"{edition.edition_key}:{payload.surah_number}:{payload.start_ayah_number}"
        elif payload.entry_type == "ayah_range":
            reference = f"{edition.edition_key}:{payload.surah_number}:{payload.start_ayah_number}-{payload.end_ayah_number}"
        else:
            reference = f"{edition.edition_key}:{payload.entry_type}:{payload.surah_number}"
        row = TafsirImportEntry(
            import_batch_id=batch.id,
            canonical_reference=reference,
            text_sha256=sha256(payload.arabic_text.encode("utf-8")).hexdigest(),
            **payload.model_dump(),
        )
        self.db.add(row)
        await self.db.flush()
        await self._event(batch, actor_id, "tafsir_import.entry_staged", "draft", "draft", reference)
        return row

    def _hierarchy_errors(self, items: list[TafsirImportEntry]) -> list[str]:
        errors: list[str] = []
        volumes: dict[int, tuple[str | None, UUID | None]] = {}
        sections: dict[str, tuple] = {}
        for item in items:
            if item.volume_number is not None:
                signature = (item.volume_title, item.volume_source_passage_id)
                if item.volume_number in volumes and volumes[item.volume_number] != signature:
                    errors.append(f"volume {item.volume_number} metadata conflicts")
                volumes[item.volume_number] = signature
            if item.section_key:
                signature = (item.section_type, item.section_title, item.section_sort_order, item.section_source_passage_id, item.volume_number)
                if item.section_key in sections and sections[item.section_key] != signature:
                    errors.append(f"section {item.section_key} metadata conflicts")
                sections[item.section_key] = signature
        return errors

    async def validate_batch(self, batch_id: UUID, actor_id: UUID) -> TafsirImportBatch:
        batch = await self._batch(batch_id)
        if batch.status not in {"draft", "failed", "changes_requested"}:
            raise AppError("tafsir_import_not_validatable", "Import is not in a validatable state", 409)
        edition = await self.db.get(TafsirEdition, batch.edition_id)
        if not edition:
            raise AppError("tafsir_edition_not_found", "Tafsir edition not found", 404)
        await self._approved_source(edition.source_edition_id)
        old = batch.status
        batch.status = "validating"
        items = list((await self.db.scalars(select(TafsirImportEntry).where(TafsirImportEntry.import_batch_id == batch.id))).all())
        errors: list[str] = []
        if len(items) != batch.expected_entry_count:
            errors.append(f"expected {batch.expected_entry_count} entries, staged {len(items)}")
        volume_count = len({i.volume_number for i in items if i.volume_number is not None})
        section_count = len({i.section_key for i in items if i.section_key})
        if volume_count != batch.expected_volume_count:
            errors.append(f"expected {batch.expected_volume_count} volumes, found {volume_count}")
        if section_count != batch.expected_section_count:
            errors.append(f"expected {batch.expected_section_count} sections, found {section_count}")
        if calculate_tafsir_manifest_sha256(items) != batch.manifest_sha256:
            errors.append("manifest checksum mismatch")
        errors.extend(self._hierarchy_errors(items))
        for item in items:
            item_errors: list[str] = []
            for passage_id in (item.volume_source_passage_id, item.section_source_passage_id, item.source_passage_id):
                if passage_id:
                    try:
                        await self._passage_for(passage_id, edition.source_edition_id)
                    except AppError as exc:
                        item_errors.append(exc.code)
            item.validation_status = "invalid" if item_errors else "valid"
            item.validation_errors = "; ".join(item_errors) or None
            errors.extend(f"{item.canonical_reference}: {e}" for e in item_errors)
        batch.validation_summary = "; ".join(errors) if errors else f"Validated {len(items)} entries across {volume_count} volumes and {section_count} sections"
        batch.validated_at = datetime.now(timezone.utc)
        batch.status = "failed" if errors else "review_pending"
        await self._event(batch, actor_id, "tafsir_import.validation_failed" if errors else "tafsir_import.validated", old, batch.status, batch.validation_summary)
        return batch

    async def assign_reviewer(self, batch_id: UUID, payload: TafsirImportReviewAssignmentCreate, actor_id: UUID) -> TafsirImportReviewAssignment:
        batch = await self._batch(batch_id)
        if batch.status != "review_pending":
            raise AppError("tafsir_import_not_assignable", "Only validated imports can receive review assignments", 409)
        if not await self.db.get(User, payload.reviewer_user_id):
            raise AppError("reviewer_not_found", "Reviewer user not found", 404)
        row = TafsirImportReviewAssignment(import_batch_id=batch.id, **payload.model_dump())
        self.db.add(row)
        await self.db.flush()
        await self._event(batch, actor_id, "tafsir_import.reviewer_assigned", batch.status, batch.status, payload.review_domain)
        return row

    async def review_assignment(self, assignment_id: UUID, reviewer_id: UUID, payload: TafsirImportReviewCreate) -> TafsirImportBatch:
        assignment = await self.db.get(TafsirImportReviewAssignment, assignment_id)
        if not assignment or assignment.reviewer_user_id != reviewer_id or assignment.status != "open":
            raise AppError("tafsir_review_assignment_invalid", "Open review assignment not found for this reviewer", 403)
        batch = await self._batch(assignment.import_batch_id)
        if batch.status != "review_pending":
            raise AppError("tafsir_import_not_reviewable", "Import is not awaiting review", 409)
        assignment.status = "completed"
        self.db.add(TafsirImportReview(
            assignment_id=assignment.id,
            import_batch_id=batch.id,
            reviewer_user_id=reviewer_id,
            review_domain=assignment.review_domain,
            decision=payload.decision,
            rationale=payload.rationale,
            created_at=datetime.now(timezone.utc),
        ))
        old = batch.status
        if payload.decision == "rejected":
            batch.status = "rejected"
        elif payload.decision == "changes_requested":
            batch.status = "changes_requested"
        else:
            approved_domains = set((await self.db.scalars(select(TafsirImportReview.review_domain).where(
                TafsirImportReview.import_batch_id == batch.id,
                TafsirImportReview.decision == "approved",
            ))).all()) | {assignment.review_domain}
            if REQUIRED_REVIEW_DOMAINS.issubset(approved_domains):
                batch.status = "approved"
        await self._event(batch, reviewer_id, "tafsir_import.reviewed", old, batch.status, f"{assignment.review_domain}: {payload.decision}")
        return batch

    async def reviewer_queue(self, reviewer_id: UUID):
        return list((await self.db.scalars(select(TafsirImportReviewAssignment).where(
            TafsirImportReviewAssignment.reviewer_user_id == reviewer_id,
            TafsirImportReviewAssignment.status == "open",
        ).order_by(TafsirImportReviewAssignment.due_at, TafsirImportReviewAssignment.created_at))).all())

    async def publish(self, batch_id: UUID, actor_id: UUID) -> TafsirImportBatch:
        batch = await self._batch(batch_id)
        if batch.status != "approved":
            raise AppError("tafsir_import_not_approved", "Import requires all scholarly review domains before publication", 409)
        edition = await self.db.get(TafsirEdition, batch.edition_id)
        if not edition:
            raise AppError("tafsir_edition_not_found", "Tafsir edition not found", 404)
        await self._approved_source(edition.source_edition_id)
        items = list((await self.db.scalars(select(TafsirImportEntry).where(TafsirImportEntry.import_batch_id == batch.id))).all())
        if len(items) != batch.expected_entry_count or calculate_tafsir_manifest_sha256(items) != batch.manifest_sha256:
            raise AppError("tafsir_manifest_changed", "Staged tafsir content changed after approval", 409)
        existing_count = await self.db.scalar(select(func.count()).select_from(TafsirEntry).where(TafsirEntry.edition_id == edition.id))
        if existing_count:
            raise AppError("tafsir_edition_not_empty", "Edition already contains canonical entries", 409)
        volumes: dict[int, TafsirVolume] = {}
        sections: dict[str, TafsirSection] = {}
        for item in sorted(items, key=lambda i: (i.volume_number or 0, i.section_sort_order, i.canonical_reference)):
            volume = None
            if item.volume_number is not None:
                volume = volumes.get(item.volume_number)
                if volume is None:
                    volume = TafsirVolume(edition_id=edition.id, volume_number=item.volume_number, title=item.volume_title, source_passage_id=item.volume_source_passage_id, published=True)
                    self.db.add(volume); await self.db.flush(); volumes[item.volume_number] = volume
            section = None
            if item.section_key:
                section = sections.get(item.section_key)
                if section is None:
                    section = TafsirSection(edition_id=edition.id, volume_id=volume.id if volume else None, section_key=item.section_key, section_type=item.section_type, title=item.section_title, sort_order=item.section_sort_order, source_passage_id=item.section_source_passage_id, published=True)
                    self.db.add(section); await self.db.flush(); sections[item.section_key] = section
            self.db.add(TafsirEntry(
                edition_id=edition.id,
                section_id=section.id if section else None,
                canonical_reference=item.canonical_reference,
                surah_number=item.surah_number,
                start_ayah_number=item.start_ayah_number,
                end_ayah_number=item.end_ayah_number,
                entry_type=item.entry_type,
                arabic_text=item.arabic_text,
                text_sha256=item.text_sha256,
                source_passage_id=item.source_passage_id,
                published=True,
            ))
        edition.published = True
        batch.status = "published"
        batch.published_at = datetime.now(timezone.utc)
        await self._event(batch, actor_id, "tafsir_import.published", "approved", "published", f"Published {len(items)} canonical tafsir entries atomically")
        return batch


def calculate_tafsir_translation_manifest_sha256(items) -> str:
    lines = [f"{item.tafsir_entry_id}\t{item.text_sha256}\t{item.source_passage_id}" for item in sorted(items, key=lambda i: str(i.tafsir_entry_id))]
    return sha256("\n".join(lines).encode("utf-8")).hexdigest()


class TafsirTranslationImportService(TafsirImportService):
    async def create_translation_batch(self, payload, actor_id: UUID):
        from app.models.tafsir import TafsirTranslationEdition, TafsirTranslationImportBatch
        edition = await self.db.get(TafsirTranslationEdition, payload.translation_edition_id)
        if not edition:
            raise AppError("tafsir_translation_edition_not_found", "Tafsir translation edition not found", 404)
        await self._approved_source(edition.source_edition_id)
        batch = TafsirTranslationImportBatch(submitted_by_user_id=actor_id, **payload.model_dump())
        self.db.add(batch); await self.db.flush(); return batch

    async def add_translation_item(self, batch_id: UUID, payload):
        from app.models.tafsir import TafsirTranslationEdition, TafsirTranslationImportBatch, TafsirTranslationImportItem
        batch = await self.db.get(TafsirTranslationImportBatch, batch_id)
        if not batch or batch.status != "draft":
            raise AppError("tafsir_translation_import_locked", "Translation import is missing or locked", 409)
        edition = await self.db.get(TafsirTranslationEdition, batch.translation_edition_id)
        entry = await self.db.get(TafsirEntry, payload.tafsir_entry_id)
        if not edition or not entry or entry.edition_id != edition.tafsir_edition_id or not entry.published:
            raise AppError("tafsir_translation_hierarchy_invalid", "Translation target is missing, unpublished, or belongs to another tafsir edition", 422)
        await self._passage_for(payload.source_passage_id, edition.source_edition_id)
        row = TafsirTranslationImportItem(import_batch_id=batch.id, text_sha256=sha256(payload.translated_text.encode("utf-8")).hexdigest(), **payload.model_dump())
        self.db.add(row); await self.db.flush(); return row

    async def validate_translation_batch(self, batch_id: UUID):
        from app.models.tafsir import TafsirTranslationEdition, TafsirTranslationImportBatch, TafsirTranslationImportItem
        batch = await self.db.get(TafsirTranslationImportBatch, batch_id)
        if not batch or batch.status not in {"draft","failed","changes_requested"}:
            raise AppError("tafsir_translation_not_validatable", "Translation import is not validatable", 409)
        edition = await self.db.get(TafsirTranslationEdition, batch.translation_edition_id)
        await self._approved_source(edition.source_edition_id)
        items = list((await self.db.scalars(select(TafsirTranslationImportItem).where(TafsirTranslationImportItem.import_batch_id == batch.id))).all())
        errors = []
        if len(items) != batch.expected_translation_count: errors.append("translation count mismatch")
        if calculate_tafsir_translation_manifest_sha256(items) != batch.manifest_sha256: errors.append("manifest checksum mismatch")
        for item in items:
            try: await self._passage_for(item.source_passage_id, edition.source_edition_id)
            except AppError as exc: errors.append(exc.code)
        batch.validation_summary = "; ".join(errors) or f"Validated {len(items)} translations"
        batch.validated_at = datetime.now(timezone.utc); batch.status = "failed" if errors else "review_pending"
        return batch

    async def review_translation_batch(self, batch_id: UUID, reviewer_id: UUID, payload):
        from app.models.tafsir import TafsirTranslationImportBatch, TafsirTranslationImportReview
        batch = await self.db.get(TafsirTranslationImportBatch, batch_id)
        if not batch or batch.status != "review_pending": raise AppError("tafsir_translation_not_reviewable", "Translation import is not awaiting review", 409)
        self.db.add(TafsirTranslationImportReview(import_batch_id=batch.id, reviewer_user_id=reviewer_id, decision=payload.decision, rationale=payload.rationale, created_at=datetime.now(timezone.utc)))
        batch.status = "approved" if payload.decision == "approved" else payload.decision
        return batch

    async def publish_translation_batch(self, batch_id: UUID):
        from app.models.tafsir import TafsirTranslationEdition, TafsirTranslationImportBatch, TafsirTranslationImportItem, TafsirTranslation
        batch = await self.db.get(TafsirTranslationImportBatch, batch_id)
        if not batch or batch.status != "approved": raise AppError("tafsir_translation_not_approved", "Translation import requires review approval", 409)
        edition = await self.db.get(TafsirTranslationEdition, batch.translation_edition_id)
        await self._approved_source(edition.source_edition_id)
        items = list((await self.db.scalars(select(TafsirTranslationImportItem).where(TafsirTranslationImportItem.import_batch_id == batch.id))).all())
        if calculate_tafsir_translation_manifest_sha256(items) != batch.manifest_sha256: raise AppError("tafsir_translation_manifest_changed", "Translation manifest changed after approval", 409)
        existing = await self.db.scalar(select(func.count()).select_from(TafsirTranslation).where(TafsirTranslation.translation_edition_id == edition.id))
        if existing: raise AppError("tafsir_translation_edition_not_empty", "Translation edition already contains published records", 409)
        for item in items:
            self.db.add(TafsirTranslation(translation_edition_id=edition.id, tafsir_entry_id=item.tafsir_entry_id, translated_text=item.translated_text, text_sha256=item.text_sha256, source_passage_id=item.source_passage_id, published=True))
        edition.published = True; batch.status = "published"; batch.published_at = datetime.now(timezone.utc)
        return batch
