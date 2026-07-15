import enum
import uuid
from datetime import date as date_
from datetime import datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DeadlineStatus(str, enum.Enum):
    OPEN = "open"
    COMPLETED = "completed"


class Deadline(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A compliance or service deadline for a lead/client (e.g. trade
    license renewal, VAT filing). `recurrence_interval_days` is nullable —
    when set, completing this deadline creates the next occurrence
    `recurrence_interval_days` after the completed one's due date, the
    same way a recurring task would."""

    __tablename__ = "deadlines"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    due_date: Mapped[date_] = mapped_column(Date, nullable=False)
    status: Mapped[DeadlineStatus] = mapped_column(
        Enum(DeadlineStatus, name="deadline_status", native_enum=False, length=20), nullable=False, default=DeadlineStatus.OPEN
    )
    recurrence_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Set once a reminder email has been sent for this occurrence, so the
    # sweep never re-notifies the same deadline twice — same convention as
    # Task.reminder_sent_at (Milestone 3) and Appointment.reminder_sent_at
    # (Milestone 4).
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
