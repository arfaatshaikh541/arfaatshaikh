"""CsvImport and CsvImportError.

Milestone 8's second half: a new inbound data source. It deliberately
does **not** implement `connector_sdk.BaseConnector` - that interface is
shaped around a paginated remote API (`estimate_cost`/`search` with a
cursor), which doesn't fit "parse this already-uploaded file" at all
(there is no remote page to request, no API cost to estimate, no cursor
to resume from). Forcing CSV import through that interface would mean
either a fake cursor over an in-memory list or a connector whose `search`
never actually does what the interface implies. Instead, CSV import rows
are fed through the exact same `businesses.repositories.
upsert_business_from_discovery` -> `businesses.dedup.
process_new_business_for_duplicates` pipeline a campaign's discovered
businesses already go through, just from a different entry point - see
`worker.csv_import_tasks`.

Status flow: `mapping_required` (file uploaded, headers/sample rows
detected, waiting for the caller to confirm which CSV column maps to
which Business field) -> `queued` (mapping confirmed, credits reserved,
Celery task dispatched) -> `processing` -> `completed`/`failed`. Two
steps (upload-and-preview, then confirm-and-start) rather than one,
because the caller cannot know the column mapping before seeing the
file's actual headers - a real CSV's column names are never assumed.
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

CSV_IMPORT_STATUSES = ("mapping_required", "queued", "processing", "completed", "failed")

# Business fields a CSV column may be mapped onto - the exact same set
# `businesses.repositories.DISCOVERY_FIELDS` accepts from a connector,
# minus nothing except that this is the *offered* mapping target list
# shown to the caller (name is the only one that's actually required).
# `email` is deliberately excluded - enrichment-owned only, never set by
# any discovery-shaped source, CSV import included. See models docstring.
MAPPABLE_FIELDS = (
    "name",
    "category",
    "subcategory",
    "address",
    "country",
    "region",
    "city",
    "area",
    "phone",
    "website",
    "google_maps_url",
    "rating",
    "review_count",
)


class CsvImport(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "csv_imports"
    __table_args__ = (UniqueConstraint("tenant_id", "id", name="uq_csv_imports_tenant_id_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="mapping_required", nullable=False, index=True
    )
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    detected_headers: Mapped[list] = mapped_column(JSONB, nullable=False)
    sample_rows: Mapped[list] = mapped_column(JSONB, nullable=False)
    # {business_field: csv_header} - null until `start` confirms it.
    column_mapping: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("credit_reservations.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class CsvImportError(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "csv_import_errors"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "csv_import_id"],
            ["csv_imports.tenant_id", "csv_imports.id"],
            name="fk_csv_import_errors_tenant_csv_import",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    csv_import_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
