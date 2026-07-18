"""BusinessEnrichment and EnrichmentEvidence.

`BusinessEnrichment` tracks one crawl attempt against a Business's
website - status, timing, and how many pages were actually fetched.
`EnrichmentEvidence` is one row per detected signal (a contact email
found, a WhatsApp link found, a missing mobile viewport, etc.) - the
architecture's explicit "evidence storage" requirement: every enrichment
claim carries its own source URL, detector type, structured result,
confidence, and collection timestamp, so a human can verify it rather than
trust it blindly. See `worker.enrichment_tasks` for what writes these, and
`worker.crawler.detectors` for what each `detector_type` means.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin

ENRICHMENT_STATUSES = ("pending", "running", "completed", "failed")


class BusinessEnrichment(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "business_enrichments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_business_enrichments_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "business_id"],
            ["businesses.tenant_id", "businesses.id"],
            name="fk_business_enrichments_tenant_business",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    business_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class EnrichmentEvidence(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "enrichment_evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "business_id"],
            ["businesses.tenant_id", "businesses.id"],
            name="fk_enrichment_evidence_tenant_business",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "enrichment_id"],
            ["business_enrichments.tenant_id", "business_enrichments.id"],
            name="fk_enrichment_evidence_tenant_enrichment",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    business_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    enrichment_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    detector_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    structured_result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    supporting_snippet: Mapped[str | None] = mapped_column(String(500), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
