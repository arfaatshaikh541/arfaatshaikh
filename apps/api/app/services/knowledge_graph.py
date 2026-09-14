from __future__ import annotations

from uuid import UUID
from sqlalchemy import or_, select

from app.core.errors import AppError
from app.models.hadith import HadithNarration
from app.models.knowledge_graph import KnowledgeCrossReference, KnowledgeTopic, KnowledgeTopicAlias
from app.models.quran import QuranAyah
from app.models.sources import SourceEdition, SourcePassage
from app.models.tafsir import TafsirAuthor, TafsirCollection, TafsirEdition, TafsirEntry, TafsirTranslation
from app.schemas.tafsir import KnowledgeCrossReferenceCreate, KnowledgeCrossReferenceReview, KnowledgeTopicAliasCreate, KnowledgeTopicCreate


class KnowledgeGraphService:
    ENTITY_MODELS = {
        "quran_ayah": QuranAyah,
        "hadith_narration": HadithNarration,
        "tafsir_entry": TafsirEntry,
        "topic": KnowledgeTopic,
    }

    def __init__(self, db): self.db = db

    async def _current_approved_passage(self, passage_id: UUID) -> SourcePassage:
        passage = await self.db.get(SourcePassage, passage_id)
        if not passage or not passage.is_current:
            raise AppError("knowledge_evidence_invalid", "Evidence passage is missing or stale", 422)
        edition = await self.db.get(SourceEdition, passage.source_edition_id)
        if not edition or edition.review_status != "approved" or edition.ingestion_status != "ready" or not edition.approved_for_retrieval:
            raise AppError("knowledge_evidence_source_unapproved", "Evidence requires an approved retrieval-eligible source", 409)
        return passage

    async def _entity(self, entity_type: str, entity_id: UUID, require_published: bool = False):
        model = self.ENTITY_MODELS.get(entity_type)
        if not model: raise AppError("knowledge_entity_type_invalid", "Unsupported knowledge entity type", 422)
        row = await self.db.get(model, entity_id)
        if not row: raise AppError("knowledge_entity_not_found", "Linked knowledge entity was not found", 404)
        if require_published and not getattr(row, "published", False):
            raise AppError("knowledge_entity_unpublished", "Linked knowledge entity is not published", 409)
        return row

    async def create_topic(self, payload: KnowledgeTopicCreate):
        await self._current_approved_passage(payload.source_passage_id)
        if payload.parent_topic_id:
            await self._entity("topic", payload.parent_topic_id)
        row = KnowledgeTopic(**payload.model_dump())
        self.db.add(row); await self.db.flush(); return row

    async def add_alias(self, topic_id: UUID, payload: KnowledgeTopicAliasCreate):
        await self._entity("topic", topic_id)
        row = KnowledgeTopicAlias(topic_id=topic_id, **payload.model_dump())
        self.db.add(row); await self.db.flush(); return row

    async def create_cross_reference(self, payload: KnowledgeCrossReferenceCreate):
        await self._entity(payload.source_type, payload.source_entity_id)
        await self._entity(payload.target_type, payload.target_entity_id)
        await self._current_approved_passage(payload.evidence_passage_id)
        row = KnowledgeCrossReference(**payload.model_dump())
        self.db.add(row); await self.db.flush(); return row

    async def review_cross_reference(self, reference_id: UUID, reviewer_id: UUID, payload: KnowledgeCrossReferenceReview):
        row = await self.db.get(KnowledgeCrossReference, reference_id)
        if not row: raise AppError("knowledge_reference_not_found", "Cross-reference not found", 404)
        await self._current_approved_passage(row.evidence_passage_id)
        if payload.decision == "approved":
            await self._entity(row.source_type, row.source_entity_id, True)
            await self._entity(row.target_type, row.target_entity_id, True)
            row.review_status = "approved"; row.published = True
        else:
            row.review_status = "rejected"; row.published = False
        row.reviewed_by_user_id = reviewer_id
        row.rationale = f"{row.rationale}\n\nReview rationale: {payload.rationale}"
        await self.db.flush(); return row

    async def list_topics(self):
        return list((await self.db.scalars(select(KnowledgeTopic).where(KnowledgeTopic.published.is_(True)).order_by(KnowledgeTopic.sort_order, KnowledgeTopic.english_name))).all())

    async def topic_detail(self, topic_key: str):
        topic = await self.db.scalar(select(KnowledgeTopic).where(KnowledgeTopic.topic_key == topic_key, KnowledgeTopic.published.is_(True)))
        if not topic: raise AppError("knowledge_topic_not_found", "Topic not found or unpublished", 404)
        refs = list((await self.db.scalars(select(KnowledgeCrossReference).where(KnowledgeCrossReference.published.is_(True), or_(
            (KnowledgeCrossReference.source_type == "topic") & (KnowledgeCrossReference.source_entity_id == topic.id),
            (KnowledgeCrossReference.target_type == "topic") & (KnowledgeCrossReference.target_entity_id == topic.id),
        )))).all())
        return topic, refs

    async def references_for(self, entity_type: str, entity_id: UUID):
        await self._entity(entity_type, entity_id, True)
        return list((await self.db.scalars(select(KnowledgeCrossReference).where(KnowledgeCrossReference.published.is_(True), or_(
            (KnowledgeCrossReference.source_type == entity_type) & (KnowledgeCrossReference.source_entity_id == entity_id),
            (KnowledgeCrossReference.target_type == entity_type) & (KnowledgeCrossReference.target_entity_id == entity_id),
        )).order_by(KnowledgeCrossReference.relationship_type))).all())

    async def tafsir_for_ayah(self, surah_number: int, ayah_number: int, translation_key: str | None = None):
        entries = list((await self.db.scalars(select(TafsirEntry).join(TafsirEdition).where(
            TafsirEntry.published.is_(True), TafsirEdition.published.is_(True), TafsirEntry.surah_number == surah_number,
            or_(TafsirEntry.start_ayah_number.is_(None), TafsirEntry.start_ayah_number <= ayah_number),
            or_(TafsirEntry.end_ayah_number.is_(None), TafsirEntry.end_ayah_number >= ayah_number),
        ).order_by(TafsirEntry.canonical_reference))).all())
        result = []
        for entry in entries:
            translation = None
            if translation_key:
                from app.models.tafsir import TafsirTranslationEdition
                translation = await self.db.scalar(select(TafsirTranslation).join(TafsirTranslationEdition).where(
                    TafsirTranslation.tafsir_entry_id == entry.id, TafsirTranslation.published.is_(True),
                    TafsirTranslationEdition.translation_key == translation_key, TafsirTranslationEdition.published.is_(True)))
            result.append({"entry": entry, "translation": translation})
        return result

    async def search_tafsir(self, q: str, collection: str | None, author_id: UUID | None, topic: str | None, surah_number: int | None, limit: int, offset: int):
        stmt = select(TafsirEntry, TafsirEdition, TafsirCollection, TafsirAuthor).join(TafsirEdition, TafsirEdition.id == TafsirEntry.edition_id).join(TafsirCollection, TafsirCollection.id == TafsirEdition.collection_id).join(TafsirAuthor, TafsirAuthor.id == TafsirCollection.author_id).where(
            TafsirEntry.published.is_(True), TafsirEdition.published.is_(True), TafsirCollection.published.is_(True), TafsirAuthor.published.is_(True),
            TafsirEntry.arabic_text.ilike(f"%{q}%"))
        if collection: stmt = stmt.where(TafsirCollection.collection_key == collection)
        if author_id: stmt = stmt.where(TafsirAuthor.id == author_id)
        if surah_number: stmt = stmt.where(TafsirEntry.surah_number == surah_number)
        if topic:
            topic_row = await self.db.scalar(select(KnowledgeTopic).where(KnowledgeTopic.topic_key == topic, KnowledgeTopic.published.is_(True)))
            if not topic_row: return []
            linked_ids = select(KnowledgeCrossReference.target_entity_id).where(KnowledgeCrossReference.published.is_(True), KnowledgeCrossReference.source_type == "topic", KnowledgeCrossReference.source_entity_id == topic_row.id, KnowledgeCrossReference.target_type == "tafsir_entry")
            stmt = stmt.where(TafsirEntry.id.in_(linked_ids))
        rows = (await self.db.execute(stmt.order_by(TafsirEntry.canonical_reference).limit(limit).offset(offset))).all()
        return [{"entry": e, "edition": ed, "collection": c, "author": a} for e, ed, c, a in rows]
