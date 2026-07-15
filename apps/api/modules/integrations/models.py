from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

TENANT_INTEGRATION_STATUSES = ("connecting", "connected", "error", "disconnected")
SYNC_RUN_STATUSES = ("running", "success", "failed")
HEALTH_STATUSES = ("healthy", "degraded", "error")


class IntegrationCatalogEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Platform-wide catalogue of connectable providers, seeded from
    `gridkeep_connector_sdk.registry.REGISTRY` (see seed/bootstrap.py). Not
    tenant-scoped — this is what every tenant chooses from, not what any
    one tenant has connected (that's `TenantIntegration`)."""

    __tablename__ = "integration_catalog"

    provider_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    auth_method: Mapped[str] = mapped_column(String(30), nullable=False)
    required_scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    permission_risk: Mapped[str] = mapped_column(String(20), nullable=False)
    supported_data_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    sync_modes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    webhook_support: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_simulator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TenantIntegration(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """One tenant's configured instance of a catalogue connector."""

    __tablename__ = "tenant_integrations"

    catalog_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integration_catalog.id", ondelete="RESTRICT"), nullable=False
    )
    credential_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integration_credentials.id", ondelete="RESTRICT"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(*TENANT_INTEGRATION_STATUSES, name="tenant_integration_status"),
        nullable=False,
        default="connecting",
    )
    sync_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="full")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    catalog_entry: Mapped[IntegrationCatalogEntry] = relationship()


class IntegrationHealth(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Append-only health-check history. The most recent row per
    `tenant_integration_id` is "current" health — no separate mutable
    latest-status column to keep out of sync with reality."""

    __tablename__ = "integration_health"

    tenant_integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        Enum(*HEALTH_STATUSES, name="integration_health_status"), nullable=False
    )
    message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IntegrationSyncRun(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "integration_sync_runs"

    tenant_integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        Enum(*SYNC_RUN_STATUSES, name="integration_sync_run_status"), nullable=False, default="running"
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_processed: Mapped[int] = mapped_column(nullable=False, default=0)
    records_created: Mapped[int] = mapped_column(nullable=False, default=0)
    records_updated: Mapped[int] = mapped_column(nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
