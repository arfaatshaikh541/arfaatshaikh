"""Campaign, CampaignFilter, CampaignEvent, CampaignError, and
CampaignUsageEstimate.

Consolidated from the full architecture's larger entity list (see
docs/adr/0008): CampaignSearchArea's fields live on CampaignFilter (the
two are 1:1 anyway), CampaignSource is a plain `source_key` column on
Campaign (Milestone 2 supports exactly one connector per campaign and
adding a join table for that would be pure ceremony), and
CampaignUsageReservation is a `reservation_id` FK directly on Campaign.
CampaignQuery and SearchCursor live on CampaignJob/CampaignTask - see
`app.modules.campaign_jobs.models`.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin

CAMPAIGN_STATUSES = (
    "draft",
    "estimating",
    "ready",
    "queued",
    "running",
    "pausing",
    "paused",
    "cancelling",
    "cancelled",
    "completed",
    "partially_completed",
    "failed",
)

WEBSITE_REQUIREMENTS = ("any", "required", "missing")


class Campaign(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "campaigns"
    __table_args__ = (UniqueConstraint("tenant_id", "id", name="uq_campaigns_tenant_id_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_key: Mapped[str] = mapped_column(String(50), nullable=False, default="mock")
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False, index=True)
    result_limit: Mapped[int] = mapped_column(nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("credit_reservations.id", ondelete="SET NULL"),
        nullable=True,
    )


class CampaignFilter(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "campaign_filters"
    __table_args__ = (
        UniqueConstraint("campaign_id", name="uq_campaign_filters_campaign_id"),
        ForeignKeyConstraint(
            ["tenant_id", "campaign_id"],
            ["campaigns.tenant_id", "campaigns.id"],
            name="fk_campaign_filters_tenant_campaign",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    radius_km: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    min_rating: Mapped[float | None] = mapped_column(Numeric(2, 1), nullable=True)
    min_reviews: Mapped[int | None] = mapped_column(nullable=True)
    must_have_phone: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    website_requirement: Mapped[str] = mapped_column(String(20), default="any", nullable=False)
    business_status: Mapped[str | None] = mapped_column(String(50), nullable=True)


class CampaignUsageEstimate(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "campaign_usage_estimates"
    __table_args__ = (
        UniqueConstraint("campaign_id", name="uq_campaign_usage_estimates_campaign_id"),
        ForeignKeyConstraint(
            ["tenant_id", "campaign_id"],
            ["campaigns.tenant_id", "campaigns.id"],
            name="fk_campaign_usage_estimates_tenant_campaign",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    estimated_credits: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    estimated_results: Mapped[int] = mapped_column(nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CampaignEvent(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "campaign_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "campaign_id"],
            ["campaigns.tenant_id", "campaigns.id"],
            name="fk_campaign_events_tenant_campaign",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class CampaignError(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "campaign_errors"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "campaign_id"],
            ["campaigns.tenant_id", "campaigns.id"],
            name="fk_campaign_errors_tenant_campaign",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("campaign_tasks.id", ondelete="SET NULL"), nullable=True
    )
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
