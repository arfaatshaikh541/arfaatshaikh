from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select

from app.core.errors import AppError
from app.models.hadith import (
    HadithBook,
    HadithChapter,
    HadithCollection,
    HadithDuplicateCandidate,
    HadithImportBatch,
    HadithImportEvent,
    HadithImportIsnadNode,
    HadithImportNarration,
    HadithImportReview,
    HadithImportReviewAssignment,
    HadithIsnadNode,
    HadithNarration,
    HadithNarrator,
)
from app.models.sources import SourceEdition, SourcePassage
from app.models.identity import User
from app.schemas.hadith import (
    HadithDuplicateResolutionCreate,
    HadithImportIsnadNodeCreate,
    HadithImportManifestCreate,
    HadithImportNarrationCreate,
    HadithImportReviewAssignmentCreate,
    HadithImportReviewCreate,
)


def narration_manifest_line(item: HadithImportNarration) -> str:
    chapter = "" if item.chapter_number is None else str(item.chapter_number)
    return "\t".join(
        [
            str(item.book_number),
            chapter,
            str(item.collection_hadith_number),
            item.matn_sha256,
            str(item.source_passage_id),
        ]
    )


def calculate_hadith_manifest_sha256(items: list[HadithImportNarration]) -> str:
    ordered = sorted(items, key=lambda row: (row.book_number, row.chapter_number or 0, row.collection_hadith_number))
    payload = "\n".join(narration_manifest_line(item) for item in ordered).encode("utf-8")
    return sha256(payload).hexdigest()


class HadithImportService:
    REQUIRED_REVIEW_DOMAINS = {"hadith_text", "isnad", "source_provenance"}

    def __init__(self, db):
        self.db = db

    async def create_batch(self, payload: HadithImportManifestCreate, actor_id: UUID) -> HadithImportBatch:
        collection = await self.db.get(HadithCollection, payload.collection_id)
        if not collection:
            raise AppError("hadith_collection_not_found", "Hadith collection not found", 404)
        await self._approved_source(collection.source_edition_id)
        existing = await self.db.scalar(
            select(HadithImportBatch).where(
                HadithImportBatch.collection_id == collection.id,
                HadithImportBatch.status.in_(["draft", "validating", "validated", "review_pending", "approved"]),
            )
        )
        if existing:
            raise AppError("hadith_import_active", "This collection already has an active import batch", 409)
        batch = HadithImportBatch(submitted_by_user_id=actor_id, **payload.model_dump())
        self.db.add(batch)
        await self.db.flush()
        await self._event(batch, actor_id, "hadith_import.created", None, "draft", "Controlled hadith import batch created")
        return batch

    async def add_narration(self, batch_id: UUID, payload: HadithImportNarrationCreate, actor_id: UUID) -> HadithImportNarration:
        batch = await self._batch(batch_id)
        if batch.status != "draft":
            raise AppError("hadith_import_locked", "Narrations can only be staged while the batch is draft", 409)
        collection = await self.db.get(HadithCollection, batch.collection_id)
        if not collection:
            raise AppError("hadith_collection_not_found", "Hadith collection not found", 404)
        await self._validate_chapter_shape(payload)
        for passage_id in (payload.book_source_passage_id, payload.chapter_source_passage_id, payload.source_passage_id):
            if passage_id:
                await self._passage_for(passage_id, collection.source_edition_id)
        canonical_reference = f"{collection.collection_key}:{payload.collection_hadith_number}"
        row = HadithImportNarration(
            import_batch_id=batch.id,
            canonical_reference=canonical_reference,
            matn_sha256=sha256(payload.arabic_matn.encode("utf-8")).hexdigest(),
            **payload.model_dump(),
        )
        self.db.add(row)
        await self.db.flush()
        await self._detect_duplicates(row, collection.id)
        await self._event(batch, actor_id, "hadith_import.narration_staged", "draft", "draft", canonical_reference)
        return row

    async def add_isnad_node(self, import_narration_id: UUID, payload: HadithImportIsnadNodeCreate, actor_id: UUID) -> HadithImportIsnadNode:
        narration = await self.db.get(HadithImportNarration, import_narration_id)
        batch = await self.db.get(HadithImportBatch, narration.import_batch_id) if narration else None
        collection = await self.db.get(HadithCollection, batch.collection_id) if batch else None
        if not narration or not batch or not collection:
            raise AppError("hadith_import_narration_not_found", "Staged narration not found", 404)
        if batch.status != "draft":
            raise AppError("hadith_import_locked", "Isnad nodes can only be staged while the batch is draft", 409)
        await self._passage_for(payload.source_passage_id, collection.source_edition_id)
        if payload.narrator_id and not await self.db.get(HadithNarrator, payload.narrator_id):
            raise AppError("hadith_narrator_not_found", "Narrator not found", 404)
        row = HadithImportIsnadNode(import_narration_id=narration.id, **payload.model_dump())
        self.db.add(row)
        await self.db.flush()
        await self._event(batch, actor_id, "hadith_import.isnad_staged", "draft", "draft", f"{narration.canonical_reference} position {row.position}")
        return row

    async def resolve_duplicate(self, candidate_id: UUID, payload: HadithDuplicateResolutionCreate, actor_id: UUID) -> HadithDuplicateCandidate:
        candidate = await self.db.get(HadithDuplicateCandidate, candidate_id)
        narration = await self.db.get(HadithImportNarration, candidate.import_narration_id) if candidate else None
        batch = await self.db.get(HadithImportBatch, narration.import_batch_id) if narration else None
        if not candidate or not narration or not batch:
            raise AppError("hadith_duplicate_not_found", "Duplicate candidate not found", 404)
        if batch.status not in {"draft", "failed"}:
            raise AppError("hadith_duplicate_locked", "Duplicate decisions are locked after validation", 409)
        candidate.resolution = payload.resolution
        candidate.resolved_by_user_id = actor_id
        candidate.resolution_rationale = payload.rationale
        await self._event(batch, actor_id, "hadith_import.duplicate_resolved", batch.status, batch.status, f"{candidate.match_type}: {payload.resolution}")
        return candidate

    async def validate_batch(self, batch_id: UUID, actor_id: UUID) -> HadithImportBatch:
        batch = await self._batch(batch_id)
        if batch.status not in {"draft", "failed", "changes_requested"}:
            raise AppError("hadith_import_not_validatable", "Import is not in a validatable state", 409)
        collection = await self.db.get(HadithCollection, batch.collection_id)
        if not collection:
            raise AppError("hadith_collection_not_found", "Hadith collection not found", 404)
        await self._approved_source(collection.source_edition_id)
        old = batch.status
        batch.status = "validating"
        items = list((await self.db.scalars(select(HadithImportNarration).where(HadithImportNarration.import_batch_id == batch.id))).all())
        errors: list[str] = []
        if len(items) != batch.expected_narration_count:
            errors.append(f"expected {batch.expected_narration_count} narrations, staged {len(items)}")
        books = {item.book_number for item in items}
        chapters = {(item.book_number, item.chapter_number) for item in items if item.chapter_number is not None}
        if len(books) != batch.expected_book_count:
            errors.append(f"expected {batch.expected_book_count} books, found {len(books)}")
        if len(chapters) != batch.expected_chapter_count:
            errors.append(f"expected {batch.expected_chapter_count} chapters, found {len(chapters)}")
        if calculate_hadith_manifest_sha256(items) != batch.manifest_sha256:
            errors.append("manifest checksum mismatch")
        errors.extend(self._hierarchy_errors(items))
        unresolved = await self.db.scalar(
            select(func.count()).select_from(HadithDuplicateCandidate).join(
                HadithImportNarration, HadithImportNarration.id == HadithDuplicateCandidate.import_narration_id
            ).where(HadithImportNarration.import_batch_id == batch.id, HadithDuplicateCandidate.resolution == "pending")
        )
        if unresolved:
            errors.append(f"{unresolved} duplicate candidates require resolution")
        for item in items:
            item_errors: list[str] = []
            for passage_id in (item.book_source_passage_id, item.chapter_source_passage_id, item.source_passage_id):
                if passage_id:
                    try:
                        await self._passage_for(passage_id, collection.source_edition_id)
                    except AppError as exc:
                        item_errors.append(exc.code)
            nodes = list((await self.db.scalars(select(HadithImportIsnadNode).where(HadithImportIsnadNode.import_narration_id == item.id).order_by(HadithImportIsnadNode.position))).all())
            if nodes and [node.position for node in nodes] != list(range(1, len(nodes) + 1)):
                item_errors.append("isnad_positions_not_contiguous")
            if batch.require_complete_isnad and not nodes:
                item_errors.append("isnad_required")
            item.validation_status = "invalid" if item_errors else "valid"
            item.validation_errors = "; ".join(item_errors) or None
            errors.extend(f"{item.canonical_reference}: {error}" for error in item_errors)
        batch.validation_summary = "; ".join(errors) if errors else f"Validated {len(items)} narrations across {len(books)} books and {len(chapters)} chapters"
        batch.validated_at = datetime.now(timezone.utc)
        batch.status = "failed" if errors else "validated"
        if not errors:
            batch.status = "review_pending"
        await self._event(batch, actor_id, "hadith_import.validation_failed" if errors else "hadith_import.validated", old, batch.status, batch.validation_summary)
        return batch

    async def assign_reviewer(self, batch_id: UUID, payload: HadithImportReviewAssignmentCreate, actor_id: UUID) -> HadithImportReviewAssignment:
        batch = await self._batch(batch_id)
        if batch.status != "review_pending":
            raise AppError("hadith_import_not_assignable", "Only validated imports can receive review assignments", 409)
        if not await self.db.get(User, payload.reviewer_user_id):
            raise AppError("reviewer_not_found", "Reviewer user not found", 404)
        row = HadithImportReviewAssignment(import_batch_id=batch.id, **payload.model_dump())
        self.db.add(row)
        await self.db.flush()
        await self._event(batch, actor_id, "hadith_import.reviewer_assigned", "review_pending", "review_pending", payload.review_domain)
        return row

    async def review_assignment(self, assignment_id: UUID, reviewer_id: UUID, payload: HadithImportReviewCreate) -> HadithImportBatch:
        assignment = await self.db.get(HadithImportReviewAssignment, assignment_id)
        if not assignment or assignment.reviewer_user_id != reviewer_id or assignment.status != "open":
            raise AppError("hadith_review_assignment_invalid", "Open review assignment not found for this reviewer", 403)
        batch = await self._batch(assignment.import_batch_id)
        if batch.status != "review_pending":
            raise AppError("hadith_import_not_reviewable", "Import is not awaiting review", 409)
        assignment.status = "completed"
        self.db.add(HadithImportReview(
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
            reviews = list((await self.db.scalars(select(HadithImportReview).where(HadithImportReview.import_batch_id == batch.id))).all())
            approved_domains = {review.review_domain for review in reviews if review.decision == "approved"}
            approved_domains.add(assignment.review_domain)
            if self.REQUIRED_REVIEW_DOMAINS.issubset(approved_domains):
                batch.status = "approved"
        await self._event(batch, reviewer_id, f"hadith_import.review_{payload.decision}", old, batch.status, payload.rationale)
        return batch

    async def publish_batch(self, batch_id: UUID, actor_id: UUID) -> HadithImportBatch:
        batch = await self._batch(batch_id)
        if batch.status != "approved":
            raise AppError("hadith_import_not_approved", "All required review domains must approve before publication", 409)
        collection = await self.db.get(HadithCollection, batch.collection_id)
        if not collection:
            raise AppError("hadith_collection_not_found", "Hadith collection not found", 404)
        await self._approved_source(collection.source_edition_id)
        items = list((await self.db.scalars(select(HadithImportNarration).where(HadithImportNarration.import_batch_id == batch.id, HadithImportNarration.validation_status == "valid").order_by(HadithImportNarration.book_number, HadithImportNarration.chapter_number, HadithImportNarration.collection_hadith_number))).all())
        if len(items) != batch.expected_narration_count or calculate_hadith_manifest_sha256(items) != batch.manifest_sha256:
            raise AppError("hadith_publication_manifest_changed", "Validated import no longer matches its approved manifest", 409)
        existing = await self.db.scalar(select(func.count()).select_from(HadithNarration).where(HadithNarration.collection_id == collection.id))
        if existing:
            raise AppError("hadith_collection_already_populated", "This collection already contains canonical narrations", 409)
        book_rows: dict[int, HadithBook] = {}
        chapter_rows: dict[tuple[int, int], HadithChapter] = {}
        for item in items:
            book = book_rows.get(item.book_number)
            if not book:
                book = HadithBook(collection_id=collection.id, book_number=item.book_number, arabic_title=item.book_arabic_title, display_title=item.book_display_title, source_passage_id=item.book_source_passage_id, published=True)
                self.db.add(book)
                await self.db.flush()
                book_rows[item.book_number] = book
            chapter = None
            if item.chapter_number is not None:
                key = (item.book_number, item.chapter_number)
                chapter = chapter_rows.get(key)
                if not chapter:
                    chapter = HadithChapter(book_id=book.id, chapter_number=item.chapter_number, arabic_title=item.chapter_arabic_title or "", display_title=item.chapter_display_title or "", source_passage_id=item.chapter_source_passage_id, published=True)
                    self.db.add(chapter)
                    await self.db.flush()
                    chapter_rows[key] = chapter
            narration = HadithNarration(collection_id=collection.id, book_id=book.id, chapter_id=chapter.id if chapter else None, collection_hadith_number=item.collection_hadith_number, canonical_reference=item.canonical_reference, arabic_matn=item.arabic_matn, matn_sha256=item.matn_sha256, source_passage_id=item.source_passage_id, published=True)
            self.db.add(narration)
            await self.db.flush()
            nodes = list((await self.db.scalars(select(HadithImportIsnadNode).where(HadithImportIsnadNode.import_narration_id == item.id).order_by(HadithImportIsnadNode.position))).all())
            for node in nodes:
                self.db.add(HadithIsnadNode(narration_id=narration.id, narrator_id=node.narrator_id, position=node.position, transmitted_name=node.transmitted_name, transmission_term=node.transmission_term, source_passage_id=node.source_passage_id))
        collection.published = True
        batch.status = "published"
        batch.published_at = datetime.now(timezone.utc)
        await self._event(batch, actor_id, "hadith_import.published", "approved", "published", f"Published {len(items)} narrations atomically")
        return batch

    async def reviewer_queue(self, reviewer_id: UUID):
        return list((await self.db.scalars(select(HadithImportReviewAssignment).where(HadithImportReviewAssignment.reviewer_user_id == reviewer_id, HadithImportReviewAssignment.status == "open").order_by(HadithImportReviewAssignment.due_at, HadithImportReviewAssignment.created_at))).all())

    async def _detect_duplicates(self, item: HadithImportNarration, collection_id: UUID) -> None:
        exact_reference = await self.db.scalar(select(HadithNarration).where(HadithNarration.collection_id == collection_id, HadithNarration.canonical_reference == item.canonical_reference))
        if exact_reference:
            self.db.add(HadithDuplicateCandidate(import_narration_id=item.id, existing_narration_id=exact_reference.id, match_type="exact_reference", similarity_basis="Same canonical collection reference"))
        exact_matn = await self.db.scalar(select(HadithNarration).where(HadithNarration.collection_id == collection_id, HadithNarration.matn_sha256 == item.matn_sha256))
        if exact_matn and (not exact_reference or exact_matn.id != exact_reference.id):
            self.db.add(HadithDuplicateCandidate(import_narration_id=item.id, existing_narration_id=exact_matn.id, match_type="exact_matn", similarity_basis="Exact UTF-8 matn SHA-256 match"))
        await self.db.flush()

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

    async def _batch(self, batch_id: UUID) -> HadithImportBatch:
        batch = await self.db.get(HadithImportBatch, batch_id)
        if not batch:
            raise AppError("hadith_import_not_found", "Hadith import batch not found", 404)
        return batch

    @staticmethod
    async def _validate_chapter_shape(payload: HadithImportNarrationCreate) -> None:
        chapter_fields = (payload.chapter_arabic_title, payload.chapter_display_title, payload.chapter_source_passage_id)
        if payload.chapter_number is None and any(value is not None for value in chapter_fields):
            raise AppError("hadith_chapter_shape_invalid", "Chapter metadata requires a chapter number", 422)
        if payload.chapter_number is not None and any(value is None for value in chapter_fields):
            raise AppError("hadith_chapter_shape_invalid", "Numbered chapters require both titles and provenance", 422)

    @staticmethod
    def _hierarchy_errors(items: list[HadithImportNarration]) -> list[str]:
        errors: list[str] = []
        books: dict[int, tuple[str, str, UUID]] = {}
        chapters: dict[tuple[int, int], tuple[str, str, UUID]] = {}
        for item in items:
            book_value = (item.book_arabic_title, item.book_display_title, item.book_source_passage_id)
            if item.book_number in books and books[item.book_number] != book_value:
                errors.append(f"book {item.book_number} metadata is inconsistent")
            books[item.book_number] = book_value
            if item.chapter_number is not None:
                key = (item.book_number, item.chapter_number)
                chapter_value = (item.chapter_arabic_title or "", item.chapter_display_title or "", item.chapter_source_passage_id)
                if key in chapters and chapters[key] != chapter_value:
                    errors.append(f"book {item.book_number} chapter {item.chapter_number} metadata is inconsistent")
                chapters[key] = chapter_value
        return errors

    async def _event(self, batch: HadithImportBatch, actor_id: UUID, event_type: str, from_status: str | None, to_status: str | None, details: str) -> None:
        self.db.add(HadithImportEvent(import_batch_id=batch.id, actor_user_id=actor_id, event_type=event_type, from_status=from_status, to_status=to_status, details=details, created_at=datetime.now(timezone.utc)))
        await self.db.flush()
