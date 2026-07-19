"""Export and ExportError.

An `Export` is both the background job record (status tracking - the
architecture's explicit "export status tracking" requirement) and its own
audit record: who requested it, what selection of leads it covered,
when it started/finished, how many rows it produced. This mirrors the
same "the entity's own row *is* the audit trail" pattern
`CampaignEvent`/`LeadStatusHistory` already use, rather than routing
export creation through the generic `AuditLog` table - which nothing else
in the campaign/lead domain does either (`AuditLog` is used exclusively by
`tenancy`/`platform_admin` for membership and platform-staff actions; see
docs/adr/0015).

`selection` stores exactly what the requester asked to export - either an
explicit set of lead ids (a Lead Workspace bulk selection) or a filter
set shaped like `leads.repositories.LeadListFilters` (the "export
everything matching my current view" case) - so the export task can
re-resolve the exact same lead set the requester saw, and so `Export`
itself stays a complete, self-contained record of what was exported
without a second query needed to reconstruct it.

`ExportError` rows are what make "partial completion" real for exports:
one lead that fails to resolve (e.g. deleted, or merged away between
selection and execution) is recorded here and skipped, not a reason to
fail the whole job - the same "retries/cancellation/partial completion"
principle the campaign engine already applies, scaled down to what an
export actually needs (a single Celery task queries, writes, and uploads
one file - there is no Milestone 2-style page fan-out to coordinate -
just per-row resilience within that one task).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin

EXPORT_FORMATS = ("xlsx", "csv")
EXPORT_STATUSES = ("pending", "processing", "completed", "failed")


class Export(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "exports"
    __table_args__ = (UniqueConstraint("tenant_id", "id", name="uq_exports_tenant_id_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    # {"mode": "lead_ids", "lead_ids": [str, ...]} or
    # {"mode": "filters", "filters": {...}, "sort_by": str, "sort_dir": str}
    selection: Mapped[dict] = mapped_column(JSONB, nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the underlying object becomes eligible for storage cleanup - set
    # to `completed_at + settings.export_retention_days` when the export
    # finishes (worker.export_tasks). Consumed by the periodic
    # `worker.export_cleanup_tasks.cleanup_expired_exports` sweep
    # (Milestone 14, docs/adr/0022), which deletes the object once this
    # passes. Download URLs are always signed fresh per-request with their
    # own, much shorter TTL (see app.core.storage.presigned_download_url) -
    # unrelated to this field.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # Set once the cleanup sweep has deleted the underlying object - never
    # unset. `object_key` is deliberately left in place after this (the
    # Export row remains a complete audit record of what was exported and
    # when its file was removed); `get_download_url` must refuse to
    # presign a URL for a key that no longer exists once this is set.
    storage_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ExportError(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "export_errors"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "export_id"],
            ["exports.tenant_id", "exports.id"],
            name="fk_export_errors_tenant_export",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    export_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
