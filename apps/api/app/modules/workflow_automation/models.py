import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class WorkflowTriggerEvent(str, enum.Enum):
    LEAD_CREATED = "lead_created"
    STAGE_CHANGED = "stage_changed"
    SCORE_THRESHOLD_REACHED = "score_threshold_reached"
    TAG_ADDED = "tag_added"
    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_COMPLETED = "appointment_completed"
    PROPOSAL_ACCEPTED = "proposal_accepted"
    PROPOSAL_REJECTED = "proposal_rejected"


class WorkflowActionType(str, enum.Enum):
    SEND_EMAIL_TEMPLATE = "send_email_template"
    CREATE_TASK = "create_task"
    CHANGE_STAGE = "change_stage"
    ADD_TAG = "add_tag"
    START_ONBOARDING_CASE = "start_onboarding_case"


class WorkflowRunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class WorkflowStepLogStatus(str, enum.Enum):
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Workflow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A trigger-condition-action automation. `trigger_config` narrows the
    trigger itself (e.g. {"stage_name": "Qualified"} for STAGE_CHANGED);
    `conditions` is an additional list of field/operator/value filters
    evaluated against the lead at trigger time — see
    `app.modules.workflow_automation.conditions`."""

    __tablename__ = "workflows"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trigger_event: Mapped[WorkflowTriggerEvent] = mapped_column(
        Enum(WorkflowTriggerEvent, name="workflow_trigger_event", native_enum=False, length=30), nullable=False
    )
    trigger_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    conditions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class WorkflowStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_steps"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Minutes to wait after the previous step (or after the trigger, for
    # the first step) before this step becomes due. 0 means "due as soon
    # as the next sweep runs" — see the module docstring in service.py for
    # why even delay=0 steps go through the sweep rather than running
    # synchronously at trigger time.
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action_type: Mapped[WorkflowActionType] = mapped_column(
        Enum(WorkflowActionType, name="workflow_action_type", native_enum=False, length=30), nullable=False
    )
    action_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class WorkflowRun(UUIDPrimaryKeyMixin, Base):
    """One per (workflow, lead) trigger match. `current_step_index` points
    at the next step to execute; `next_run_at` is when that step becomes
    due, NULL once the run reaches a terminal status."""

    __tablename__ = "workflow_runs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[WorkflowRunStatus] = mapped_column(
        Enum(WorkflowRunStatus, name="workflow_run_status", native_enum=False, length=20),
        nullable=False, default=WorkflowRunStatus.RUNNING,
    )
    current_step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class WorkflowStepLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workflow_step_logs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[WorkflowStepLogStatus] = mapped_column(
        Enum(WorkflowStepLogStatus, name="workflow_step_log_status", native_enum=False, length=20), nullable=False
    )
    result_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
