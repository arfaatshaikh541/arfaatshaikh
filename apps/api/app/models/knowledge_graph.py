from __future__ import annotations

from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeTopic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_topics"
    __table_args__ = (
        UniqueConstraint("topic_key"),
        CheckConstraint("sort_order >= 0", name="ck_knowledge_topics_sort_order"),
    )

    topic_key: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_topic_id: Mapped[UUID | None] = mapped_column(ForeignKey("knowledge_topics.id", ondelete="RESTRICT"), nullable=True, index=True)
    english_name: Mapped[str] = mapped_column(String(240), nullable=False)
    arabic_name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    source_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class KnowledgeTopicAlias(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_topic_aliases"
    __table_args__ = (UniqueConstraint("topic_id", "language", "alias"),)

    topic_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_topics.id", ondelete="CASCADE"), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    alias: Mapped[str] = mapped_column(String(240), nullable=False)


class KnowledgeCrossReference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_cross_references"
    __table_args__ = (
        CheckConstraint("source_type IN ('quran_ayah','hadith_narration','tafsir_entry','topic')", name="ck_knowledge_cross_refs_source_type"),
        CheckConstraint("target_type IN ('quran_ayah','hadith_narration','tafsir_entry','topic')", name="ck_knowledge_cross_refs_target_type"),
        CheckConstraint("relationship_type IN ('explains','supports','contextualises','parallel','topic_membership','linguistic_note','historical_context','asbab_al_nuzul','editorial_link')", name="ck_knowledge_cross_refs_relationship"),
        CheckConstraint("editorial_confidence BETWEEN 0 AND 100", name="ck_knowledge_cross_refs_confidence"),
        CheckConstraint("NOT (source_type = target_type AND source_entity_id = target_entity_id)", name="ck_knowledge_cross_refs_not_self"),
        UniqueConstraint("source_type", "source_entity_id", "target_type", "target_entity_id", "relationship_type", "evidence_passage_id"),
        Index("ix_knowledge_cross_refs_source", "source_type", "source_entity_id"),
        Index("ix_knowledge_cross_refs_target", "target_type", "target_entity_id"),
    )

    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_entity_id: Mapped[UUID] = mapped_column(nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_entity_id: Mapped[UUID] = mapped_column(nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(40), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    editorial_confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
