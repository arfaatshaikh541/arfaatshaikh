import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentRequestStatus(str, enum.Enum):
    REQUESTED = "requested"
    UPLOADED = "uploaded"
    APPROVED = "approved"
    REJECTED = "rejected"


class DocumentRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """`public_token` is the client-facing upload page's authorization
    proof — raw (unhashed), unguessable, and NOT row-level-secured, the
    same pattern as `Proposal.public_token`/`TenantCaptureToken`. Unlike
    the public proposal accept/reject routes, the public *upload* route
    (see `documents.service.upload_document_public`) is still gated
    behind the `document_collection` module entitlement: accepting or
    rejecting a proposal just flips a status flag, but uploading a file
    consumes ongoing storage — if a tenant's subscription lapses, new
    uploads should stop rather than silently keep consuming a resource
    nobody's paying for."""

    __tablename__ = "document_requests"
    __table_args__ = (UniqueConstraint("public_token", name="uq_document_requests_public_token"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[DocumentRequestStatus] = mapped_column(
        Enum(DocumentRequestStatus, name="document_request_status", native_enum=False, length=20),
        nullable=False, default=DocumentRequestStatus.REQUESTED,
    )
    public_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The actual uploaded file(s) against a `DocumentRequest` — kept as
    its own row rather than folded into the request, so a rejected
    request can be re-uploaded without losing the earlier attempt's
    history. `uploaded_by` is null for a public/client upload."""

    __tablename__ = "documents"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    content_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
