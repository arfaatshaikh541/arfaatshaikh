import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EmailTriggerEvent(str, enum.Enum):
    MANUAL = "manual"
    LEAD_CREATED = "lead_created"
    LEAD_ASSIGNED = "lead_assigned"
    STAGE_CHANGED = "stage_changed"
    TASK_REMINDER = "task_reminder"
    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_REMINDER = "appointment_reminder"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    PROPOSAL_SENT = "proposal_sent"
    PROPOSAL_ACCEPTED = "proposal_accepted"
    PROPOSAL_REJECTED = "proposal_rejected"


class EmailDeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class EmailTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Merge fields in `subject`/`body_text`/`body_html` use `{{field}}`
    syntax, rendered by a small whitelisted substitution function (never
    a template engine with code-execution capability) — see
    `app.modules.communications.service.render_template`."""

    __tablename__ = "email_templates"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    trigger_event: Mapped[EmailTriggerEvent] = mapped_column(
        Enum(EmailTriggerEvent, name="email_trigger_event", native_enum=False, length=30), nullable=False
    )
    # Only meaningful when trigger_event == STAGE_CHANGED: "won" or "lost".
    trigger_stage_outcome: Mapped[str | None] = mapped_column(String(10), nullable=True)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EmailDeliveryLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "email_delivery_logs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_templates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    recipient: Mapped[str] = mapped_column(String(254), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    # Rendered snapshot at send time — retries resend exactly this content
    # rather than needing the original (lead-specific) merge-field context.
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[EmailDeliveryStatus] = mapped_column(
        Enum(EmailDeliveryStatus, name="email_delivery_status", native_enum=False, length=20),
        nullable=False, default=EmailDeliveryStatus.PENDING,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
