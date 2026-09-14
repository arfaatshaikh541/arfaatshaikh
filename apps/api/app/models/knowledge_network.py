from __future__ import annotations

from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CanonicalKnowledgeEntity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "canonical_knowledge_entities"
    __table_args__ = (
        UniqueConstraint("canonical_key", name="uq_canonical_knowledge_entity_key"),
        UniqueConstraint("entity_type", "source_entity_id", name="uq_canonical_knowledge_entity_source"),
        CheckConstraint("entity_type IN ('quran_ayah','hadith_narration','tafsir_entry','topic','lesson','course','scholar','research','dua','prophet','companion','place','historical_event')", name="canonical_knowledge_entity_type"),
        CheckConstraint("publication_status IN ('draft','reviewed','published','archived')", name="canonical_knowledge_publication_status"),
        Index("ix_canonical_knowledge_entity_type_status", "entity_type", "publication_status"),
    )

    canonical_key: Mapped[str] = mapped_column(String(220), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_entity_id: Mapped[UUID] = mapped_column(nullable=False)
    english_label: Mapped[str] = mapped_column(String(320), nullable=False)
    arabic_label: Mapped[str] = mapped_column(String(320), nullable=False, default="", server_default="")
    transliteration: Mapped[str] = mapped_column(String(320), nullable=False, default="", server_default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    canonical_url: Mapped[str] = mapped_column(String(500), nullable=False)
    publication_status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    source_passage_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=True)
    search_document: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")


class KnowledgeRelationship(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_relationships"
    __table_args__ = (
        UniqueConstraint("source_entity_id", "target_entity_id", "relationship_type", "evidence_passage_id", name="uq_knowledge_relationship_evidence"),
        CheckConstraint("source_entity_id <> target_entity_id", name="knowledge_relationship_not_self"),
        CheckConstraint("relationship_type IN ('explains','supports','authenticates','references','narrated_by','revealed_in','mentions','contradicts_claim','related_topic','prerequisite','continuation_of','derived_from','contextualises','topic_membership')", name="knowledge_relationship_type"),
        CheckConstraint("review_status IN ('pending','approved','rejected','withdrawn')", name="knowledge_relationship_review_status"),
        CheckConstraint("confidence BETWEEN 0 AND 100", name="knowledge_relationship_confidence"),
        Index("ix_knowledge_relationship_source", "source_entity_id", "relationship_type"),
        Index("ix_knowledge_relationship_target", "target_entity_id", "relationship_type"),
    )

    source_entity_id: Mapped[UUID] = mapped_column(ForeignKey("canonical_knowledge_entities.id", ondelete="CASCADE"), nullable=False)
    target_entity_id: Mapped[UUID] = mapped_column(ForeignKey("canonical_knowledge_entities.id", ondelete="CASCADE"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class KnowledgeEntityAlias(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_entity_aliases"
    __table_args__ = (
        UniqueConstraint("entity_id", "language", "normalized_alias", name="uq_knowledge_entity_alias"),
        Index("ix_knowledge_entity_alias_lookup", "language", "normalized_alias"),
    )

    entity_id: Mapped[UUID] = mapped_column(ForeignKey("canonical_knowledge_entities.id", ondelete="CASCADE"), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    alias: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(320), nullable=False)
    alias_type: Mapped[str] = mapped_column(String(24), nullable=False, default="name", server_default="name")


class KnowledgeTraversalAudit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_traversal_audits"
    __table_args__ = (
        CheckConstraint("max_depth BETWEEN 1 AND 5", name="knowledge_traversal_depth"),
        CheckConstraint("result_count >= 0", name="knowledge_traversal_result_count"),
        Index("ix_knowledge_traversal_audit_requester", "requester_user_id", "created_at"),
    )

    requester_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    root_entity_id: Mapped[UUID] = mapped_column(ForeignKey("canonical_knowledge_entities.id", ondelete="RESTRICT"), nullable=False)
    max_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    relationship_filters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
