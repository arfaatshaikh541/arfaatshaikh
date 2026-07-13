import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid

WORKFLOW_TRIGGER_TYPES = (
    "lead_created",
    "lead_stage_changed",
    "lead_assigned",
    "appointment_booked",
)

WORKFLOW_ACTION_TYPES = ("create_task", "send_email", "add_tag", "create_notification")

WORKFLOW_CONDITION_FIELDS = ("service_id", "source", "priority", "estimated_value", "to_stage_slug")
WORKFLOW_CONDITION_OPERATORS = ("equals", "not_equals", "at_least")


class WorkflowRule(TimestampMixin, Base):
    """A tenant-configured automation: WHEN trigger_type fires AND every
    condition matches, THEN run each action in order. See
    docs/architecture/erd-summary-m4.md - trigger/condition/action are
    always structured JSON matched against a closed dispatch table,
    never a code string, so there is no eval/exec anywhere here."""

    __tablename__ = "workflow_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    conditions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class WorkflowExecutionLog(Base):
    """Append-only: one row per rule that actually fired (conditions
    matched), recording what actions ran and their outcome."""

    __tablename__ = "workflow_execution_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True
    )
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actions_taken: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
