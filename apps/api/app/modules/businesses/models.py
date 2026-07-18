"""Business and BusinessSourceRecord.

A Business is the tenant-owned, individually addressable record a
discovered business becomes once a campaign task processes it - the
persistence layer the original architecture's "Business Data Model"
section calls for. Milestone 2 did not build this (it only stored a raw
JSON snapshot per campaign task page - see `CampaignTask.result_snapshot`),
which was a real gap: there was nothing with its own stable ID for
Milestone 4's website enrichment to attach evidence to. See docs/adr/0011.

Consolidated from the full architecture's larger entity list, following
the same reasoning as ADR-0008: BusinessIdentifier/BusinessCategory/
BusinessLocation/BusinessContact/BusinessWebsite/BusinessSocialProfile are
all 1:1 with Business and live as columns directly on it here; per-field
provenance (source, confidence, collected_at) lives in a `field_provenance`
JSONB column rather than a separate BusinessFieldProvenance table, for the
same "no join for a 1:1-shaped concern" reason ADR-0008 gave. This is
metadata *about* a Business's own current field values, not a 1:many
relationship in its own right.

`BusinessSourceRecord` DOES get its own real table: a business can
genuinely be rediscovered by multiple campaigns over time, and each
rediscovery's full raw connector output must be preserved, not
overwritten - this is what "preserve source provenance" and Milestone 5's
future deduplication step both need. `BusinessSnapshot` and
`BusinessMergeHistory` are Milestone 5 scope - there is nothing to
snapshot-diff or merge yet with only one discovery pipeline feeding one
Business per source record and no merge step implemented.

`Business.email` is deliberately never set by discovery - Google Places
(and the mock connector, matching it) has no email field at all in its
schema. It is populated exclusively by Milestone 4's enrichment crawler,
which is a clean, structural way to guarantee it is never fabricated.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin


class Business(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "businesses"
    __table_args__ = (UniqueConstraint("tenant_id", "id", name="uq_businesses_tenant_id_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str | None] = mapped_column(String(150), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(150), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Enrichment-only (Milestone 4) - never set by discovery. See module docstring.
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    canonical_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    google_place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_maps_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rating: Mapped[float | None] = mapped_column(Numeric(2, 1), nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    business_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # {field_name: {"source": str, "source_record_id": str, "confidence": float, "collected_at": iso str}}
    field_provenance: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class BusinessSourceRecord(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "business_source_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source",
            "source_native_id",
            name="uq_business_source_records_tenant_source_native_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "business_id"],
            ["businesses.tenant_id", "businesses.id"],
            name="fk_business_source_records_tenant_business",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    business_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    # Plain (non-composite) FK, deliberately: a composite ["tenant_id",
    # "campaign_id"] FK with ondelete="SET NULL" would null out *every*
    # column in that constraint on delete - including tenant_id, which
    # would corrupt the row's RLS scoping. campaign_id here is purely an
    # informational backreference ("which campaign last (re)discovered
    # this"); the row's own tenant_id (validated separately via the
    # business_id composite FK above) is what actually governs access.
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_native_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
