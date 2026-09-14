from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SourceLicence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_licences"
    __table_args__ = (UniqueConstraint("spdx_identifier", "version"),)

    name: Mapped[str] = mapped_column(String(180), nullable=False)
    spdx_identifier: Mapped[str | None] = mapped_column(String(80), nullable=True)
    version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    licence_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    copyright_holder: Mapped[str | None] = mapped_column(String(240), nullable=True)
    redistribution_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    modification_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    commercial_use_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    attribution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    restrictions: Mapped[str | None] = mapped_column(Text, nullable=True)
    legal_review_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("source_type IN ('quran','hadith','tafsir','fiqh','aqidah','seerah','history','arabic','comparative_religion','modern_analysis','other')", name="ck_sources_type"),
        CheckConstraint("authority_status IN ('unassessed','candidate','approved','restricted','rejected')", name="ck_sources_authority_status"),
        Index("ix_sources_type_status", "source_type", "authority_status"),
    )

    canonical_title: Mapped[str] = mapped_column(String(500), nullable=False)
    original_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    primary_language: Mapped[str] = mapped_column(String(16), nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    compiler_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    authority_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unassessed", server_default="unassessed")
    public_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SourceEdition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_editions"
    __table_args__ = (
        UniqueConstraint("source_id", "edition_key"),
        CheckConstraint("ingestion_status IN ('not_started','registered','validating','ready','blocked','retired')", name="ck_source_editions_ingestion_status"),
        CheckConstraint("review_status IN ('pending','in_review','approved','changes_requested','rejected','expired')", name="ck_source_editions_review_status"),
        Index("ix_source_editions_source_review", "source_id", "review_status"),
    )

    source_id: Mapped[UUID] = mapped_column(ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False, index=True)
    licence_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_licences.id", ondelete="RESTRICT"), nullable=True, index=True)
    edition_key: Mapped[str] = mapped_column(String(120), nullable=False)
    edition_statement: Mapped[str | None] = mapped_column(String(300), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(300), nullable=True)
    publication_year: Mapped[int | None] = mapped_column(nullable=True)
    editor_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    translator_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    isbn: Mapped[str | None] = mapped_column(String(32), nullable=True)
    citation_format: Mapped[str] = mapped_column(Text, nullable=False)
    ingestion_status: Mapped[str] = mapped_column(String(24), nullable=False, default="not_started", server_default="not_started")
    review_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")
    approved_for_retrieval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class SourceAcquisition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_acquisitions"
    __table_args__ = (CheckConstraint("method IN ('publisher_delivery','licensed_api','institutional_archive','manual_upload','public_domain_import','other')", name="ck_source_acquisitions_method"),)

    edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="CASCADE"), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    acquired_from: Mapped[str] = mapped_column(String(500), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    terms_snapshot_object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recorded_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class SourceIntegrityRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "source_integrity_records"
    __table_args__ = (
        UniqueConstraint("edition_id", "algorithm", "digest"),
        CheckConstraint("algorithm IN ('sha256','sha512')", name="ck_source_integrity_algorithm"),
        Index("ix_source_integrity_edition_created", "edition_id", "created_at"),
    )

    edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="CASCADE"), nullable=False, index=True)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(16), nullable=False)
    digest: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SourceReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "source_reviews"
    __table_args__ = (
        CheckConstraint("decision IN ('pending','approved','changes_requested','rejected','expired')", name="ck_source_reviews_decision"),
        Index("ix_source_reviews_edition_created", "edition_id", "created_at"),
    )

    edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    review_domain: Mapped[str] = mapped_column(String(60), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SourceReviewAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_review_assignments"
    __table_args__ = (
        UniqueConstraint("edition_id", "reviewer_user_id", "review_domain", "status"),
        CheckConstraint("status IN ('assigned','in_progress','completed','cancelled')", name="ck_source_review_assignments_status"),
        Index("ix_source_review_assignments_reviewer_status", "reviewer_user_id", "status"),
    )

    edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    assigned_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    review_domain: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="assigned", server_default="assigned")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SourcePassage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_passages"
    __table_args__ = (
        UniqueConstraint("edition_id", "passage_key", "version"),
        CheckConstraint("version > 0", name="ck_source_passages_version_positive"),
        Index("ix_source_passages_edition_key", "edition_id", "passage_key"),
    )

    edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="RESTRICT"), nullable=False, index=True)
    passage_key: Mapped[str] = mapped_column(String(240), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    source_locator: Mapped[str] = mapped_column(String(500), nullable=False)
    citation_label: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class SourceAttribution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_attributions"
    __table_args__ = (UniqueConstraint("edition_id", "language"),)

    edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="CASCADE"), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    display_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    licence_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class SourceLifecycleEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "source_lifecycle_events"
    __table_args__ = (Index("ix_source_lifecycle_edition_created", "edition_id", "created_at"),)

    edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class SourceClaim(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_claims"
    __table_args__ = (
        CheckConstraint("claim_status IN ('draft','reviewed','approved','disputed','withdrawn')", name="ck_source_claims_status"),
        Index("ix_source_claims_status_created", "claim_status", "created_at"),
    )

    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    claim_status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    methodology: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dispute_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class ClaimPassageLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "claim_passage_links"
    __table_args__ = (
        UniqueConstraint("claim_id", "passage_id", "relation_type"),
        CheckConstraint("relation_type IN ('supports','qualifies','disputes','contextualises')", name="ck_claim_passage_links_relation"),
        CheckConstraint("citation_start >= 0 AND citation_end > citation_start", name="ck_claim_passage_links_span"),
    )

    claim_id: Mapped[UUID] = mapped_column(ForeignKey("source_claims.id", ondelete="CASCADE"), nullable=False, index=True)
    passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    citation_start: Mapped[int] = mapped_column(nullable=False)
    citation_end: Mapped[int] = mapped_column(nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class PassageCorrection(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "passage_corrections"
    __table_args__ = (
        CheckConstraint("status IN ('requested','accepted','rejected','superseded')", name="ck_passage_corrections_status"),
        Index("ix_passage_corrections_passage_created", "passage_id", "created_at"),
    )

    passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=False, index=True)
    replacement_passage_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"), nullable=True)
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decided_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="requested", server_default="requested")
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SourceSupersession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "source_supersessions"
    __table_args__ = (
        UniqueConstraint("superseded_edition_id", "replacement_edition_id"),
        CheckConstraint("superseded_edition_id <> replacement_edition_id", name="ck_source_supersessions_distinct"),
    )

    superseded_edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="RESTRICT"), nullable=False, index=True)
    replacement_edition_id: Mapped[UUID] = mapped_column(ForeignKey("source_editions.id", ondelete="RESTRICT"), nullable=False, index=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApprovalPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "approval_policies"
    __table_args__ = (
        UniqueConstraint("source_type", "policy_version"),
        CheckConstraint("status IN ('draft','active','retired')", name="ck_approval_policies_status"),
    )

    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    policy_version: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    minimum_reviewers: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")
    require_legal_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    require_integrity_verification: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    required_review_domains: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

class SourceAuditExport(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "source_audit_exports"
    __table_args__ = (
        CheckConstraint("format IN ('json','csv')", name="ck_source_audit_exports_format"),
        Index("ix_source_audit_exports_created", "created_at"),
    )

    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    edition_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_editions.id", ondelete="RESTRICT"), nullable=True, index=True)
    format: Mapped[str] = mapped_column(String(12), nullable=False)
    filters_json: Mapped[str] = mapped_column(Text, nullable=False)
    record_count: Mapped[int] = mapped_column(nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
