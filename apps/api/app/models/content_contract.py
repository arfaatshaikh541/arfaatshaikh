"""Governed datasets, knowledge records (generic data contract) and the directory engine.

A DataSet is the unit of licensing and publication: nothing in `knowledge_records` or an imported
directory listing is publicly visible unless its dataset is enabled, published and has a licence status
that permits publication (see app/services/data_contracts.py::can_publish).
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

LICENSE_STATUSES = ("VERIFIED_OPEN", "PUBLIC_DOMAIN", "PD_WORK_OPEN_EDITION_DECLARED", "OWNER_PERMISSION_GRANTED",
                    "LICENSE_REQUIRED", "PROVENANCE_UNCLEAR", "UNKNOWN")
VALIDATION_STATUSES = ("VERIFIED", "NEEDS_REVIEW", "FAILED", "NOT_RUN")
PUBLICATION_STATUSES = ("draft", "staged", "published", "disabled", "rejected")
READINESS = ("VERIFIED", "NEEDS_REVIEW", "LICENSE_REQUIRED", "PROVENANCE_UNCLEAR", "UNAVAILABLE", "OWNER_UPLOAD_REQUIRED")
RECORD_TYPES = ("fiqh", "aqeedah", "seerah", "hadith_grading", "terminology", "library_work", "history", "civilization",
                "scholar", "book", "person", "event", "place", "concept", "institution")
LISTING_TYPES = ("mosque", "business", "charity", "job", "professional", "organisation", "event", "volunteering", "health")
PUBLICATION_FORMS = ("published_edition", "manuscript", "online_resource", "dataset", "unspecified")
PROVENANCE_STATUSES = ("source_and_page_cited", "source_cited", "unclear")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ",".join(f"'{value}'" for value in values) + ")"


class DataSet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_sets"
    __table_args__ = (
        UniqueConstraint("dataset_key", name="uq_data_sets_dataset_key"),
        CheckConstraint(_in("license_status", LICENSE_STATUSES), name="license_status"),
        CheckConstraint(_in("validation_status", VALIDATION_STATUSES), name="validation_status"),
        CheckConstraint(_in("publication_status", PUBLICATION_STATUSES), name="publication_status"),
        CheckConstraint(_in("readiness", READINESS), name="readiness"),
    )

    dataset_key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_name: Mapped[str] = mapped_column(String(300), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    date_acquired: Mapped[date | None] = mapped_column(Date, nullable=True)
    license_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    license_status: Mapped[str] = mapped_column(String(40), nullable=False, default="UNKNOWN", server_default="UNKNOWN")
    provenance: Mapped[str] = mapped_column(Text, nullable=False)
    transformation: Mapped[str | None] = mapped_column(Text, nullable=True)
    importer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    importer_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="NOT_RUN", server_default="NOT_RUN")
    publication_status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    readiness: Mapped[str] = mapped_column(String(32), nullable=False, default="OWNER_UPLOAD_REQUIRED", server_default="OWNER_UPLOAD_REQUIRED")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    rights_confirmation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    remaining_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_checked: Mapped[date | None] = mapped_column(Date, nullable=True)


class DataSetImport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_set_imports"
    __table_args__ = (
        CheckConstraint("status IN ('applied','rolled_back','failed')", name="status"),
        Index("ix_data_set_imports_dataset_created", "dataset_id", "created_at"),
    )

    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("data_sets.id", ondelete="CASCADE"), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    importer_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="applied", server_default="applied")
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failures: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    snapshot: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    imported_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # what the importer retrieved: source version, when, its checksum and which adapter produced the rows
    adapter_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)


class KnowledgeRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_records"
    __table_args__ = (
        UniqueConstraint("dataset_id", "record_key", name="uq_knowledge_records_dataset_key"),
        CheckConstraint(_in("entity_type", RECORD_TYPES), name="entity_type"),
        CheckConstraint("scholarly_status IN ('unreviewed','reviewed','scholar_verified','disputed','rejected')", name="scholarly_status"),
        CheckConstraint("confidence BETWEEN 0 AND 100", name="confidence"),
        CheckConstraint(_in("license_status", LICENSE_STATUSES), name="license_status"),
        CheckConstraint(_in("publication_status", PUBLICATION_FORMS), name="publication_status"),
        CheckConstraint(_in("provenance_status", PROVENANCE_STATUSES), name="provenance_status"),
        Index("ix_knowledge_records_type", "entity_type"),
    )

    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("data_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    import_id: Mapped[UUID | None] = mapped_column(ForeignKey("data_set_imports.id", ondelete="SET NULL"), nullable=True, index=True)
    record_key: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    arabic_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    author: Mapped[str | None] = mapped_column(String(300), nullable=True)
    record_date: Mapped[str | None] = mapped_column(String(80), nullable=True)
    license: Mapped[str] = mapped_column(String(240), nullable=False)
    provenance: Mapped[str] = mapped_column(Text, nullable=False)
    scholarly_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unreviewed", server_default="unreviewed")
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_verified: Mapped[date | None] = mapped_column(Date, nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    relationships: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # source-level provenance of religious content (docs/data-contracts.md): which work, edition, volume, page, chapter
    source_work: Mapped[str | None] = mapped_column(String(500), nullable=True)
    edition: Mapped[str | None] = mapped_column(String(300), nullable=True)
    volume: Mapped[str | None] = mapped_column(String(80), nullable=True)
    page: Mapped[str | None] = mapped_column(String(80), nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(300), nullable=True)
    language: Mapped[str | None] = mapped_column(String(24), nullable=True)
    publication_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unspecified", server_default="unspecified")
    license_status: Mapped[str] = mapped_column(String(40), nullable=False, default="UNKNOWN", server_default="UNKNOWN")
    provenance_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unclear", server_default="unclear")
    # type-specific structure: madhhab/question/ruling/evidence (fiqh), school/statement (aqeedah), grades (hadith grading) ...
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")


class DirectoryListing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "directory_listings"
    __table_args__ = (
        CheckConstraint(_in("listing_type", LISTING_TYPES), name="listing_type"),
        CheckConstraint("status IN ('pending','published','hidden','rejected')", name="status"),
        CheckConstraint("verification_status IN ('unverified','pending','verified','rejected','suspended')", name="verification_status"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="latitude"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="longitude"),
        CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="coordinates_pair"),
        UniqueConstraint("dataset_id", "external_key", name="uq_directory_listings_dataset_key"),
        Index("ix_directory_listings_type_status", "listing_type", "status"),
        Index("ix_directory_listings_geo", "latitude", "longitude"),
        Index("ix_directory_listings_dedupe", "dedupe_key"),
    )

    dataset_id: Mapped[UUID | None] = mapped_column(ForeignKey("data_sets.id", ondelete="CASCADE"), nullable=True, index=True)
    import_id: Mapped[UUID | None] = mapped_column(ForeignKey("data_set_imports.id", ondelete="SET NULL"), nullable=True, index=True)
    external_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    listing_type: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    arabic_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    license: Mapped[str] = mapped_column(String(240), nullable=False)
    provenance: Mapped[str] = mapped_column(Text, nullable=False)
    source_updated_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unverified", server_default="unverified")
    verified_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moderation_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    submitted_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    duplicate_of_id: Mapped[UUID | None] = mapped_column(ForeignKey("directory_listings.id", ondelete="SET NULL"), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(300), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_verified: Mapped[date | None] = mapped_column(Date, nullable=True)
    # type-specific fields (employer, salary, employment_type, application_url, hours, facilities, registration ...)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")


class DirectoryReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "directory_reports"
    __table_args__ = (
        CheckConstraint("reason IN ('incorrect','closed','duplicate','offensive','fraud','other')", name="reason"),
        CheckConstraint("status IN ('open','actioned','dismissed')", name="status"),
        Index("ix_directory_reports_status", "status", "created_at"),
    )

    listing_id: Mapped[UUID] = mapped_column(ForeignKey("directory_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    reporter_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    details: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", server_default="open")
    resolved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlatformAuditEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only record of platform-level administrative actions (datasets, directory moderation, imports).

    Separate from the tenant-scoped audit_events table, whose row-level security only admits rows that belong to an organisation.
    """
    __tablename__ = "platform_audit_events"
    __table_args__ = (Index("ix_platform_audit_events_created", "created_at"), Index("ix_platform_audit_events_action", "action"))

    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_id: Mapped[UUID | None] = mapped_column(nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
