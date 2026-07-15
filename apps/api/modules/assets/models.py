from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

CRITICALITY_LEVELS = ("low", "medium", "high", "critical")
EXPOSURE_LEVELS = ("internal", "external", "unknown")
LIFECYCLE_STATUSES = ("active", "inactive", "decommissioned")


class AssetType(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Platform-wide catalogue of asset kinds. Not tenant-scoped. Seeded
    minimally for the record types Milestone 2's mock connectors produce
    (see seed/bootstrap.py) — later milestones add the rest of the
    architecture doc's asset-category list (domain, subdomain, IP, ...)
    as connectors that actually produce them land."""

    __tablename__ = "asset_types"

    key: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)


class Asset(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "assets"

    asset_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_types.id", ondelete="RESTRICT"), nullable=False
    )
    tenant_integration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_integrations.id", ondelete="SET NULL"), nullable=True
    )
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False, default=1.0)
    criticality: Mapped[str] = mapped_column(
        Enum(*CRITICALITY_LEVELS, name="asset_criticality"), nullable=False, default="medium"
    )
    exposure: Mapped[str] = mapped_column(
        Enum(*EXPOSURE_LEVELS, name="asset_exposure"), nullable=False, default="unknown"
    )
    lifecycle_status: Mapped[str] = mapped_column(
        Enum(*LIFECYCLE_STATUSES, name="asset_lifecycle_status"), nullable=False, default="active"
    )
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    asset_type: Mapped[AssetType] = relationship()
    identifiers: Mapped[list[AssetIdentifier]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class AssetIdentifier(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """The dedup key: a (tenant, identifier_type, identifier_value) triple
    resolves to exactly one asset. An asset may carry more than one
    identifier (e.g. a device with both a hostname and a serial number)."""

    __tablename__ = "asset_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "identifier_type", "identifier_value", name="uq_asset_identifiers_dedup_key"
        ),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(60), nullable=False)
    identifier_value: Mapped[str] = mapped_column(String(500), nullable=False)

    asset: Mapped[Asset] = relationship(back_populates="identifiers")


class AssetRelationship(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "asset_relationships"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "from_asset_id", "to_asset_id", "relationship_type",
            name="uq_asset_relationships_edge",
        ),
    )

    from_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(60), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False, default=1.0)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AssetOwner(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "asset_owners"
    __table_args__ = (
        UniqueConstraint("tenant_id", "asset_id", "user_id", name="uq_asset_owners_pair"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ownership_type: Mapped[str] = mapped_column(String(40), nullable=False, default="owner")


class AssetTag(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "asset_tags"
    __table_args__ = (UniqueConstraint("tenant_id", "asset_id", "key", name="uq_asset_tags_pair"),)

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    value: Mapped[str] = mapped_column(String(300), nullable=False)


class AssetChange(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Append-only delta log — the change-tracking requirement from the
    architecture doc. No `updated_at`/mutation path: a change record
    describes a fact that already happened."""

    __tablename__ = "asset_changes"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_integration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_integrations.id", ondelete="SET NULL"), nullable=True
    )
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
