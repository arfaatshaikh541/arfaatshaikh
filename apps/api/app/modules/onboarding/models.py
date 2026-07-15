import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OnboardingStepType(str, enum.Enum):
    TASK = "task"
    DOCUMENT_REQUEST = "document_request"


class OnboardingCaseStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OnboardingCaseStepStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class OnboardingTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "onboarding_templates"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_onboarding_templates_tenant_name"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class OnboardingTemplateStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "onboarding_template_steps"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("onboarding_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    step_type: Mapped[OnboardingStepType] = mapped_column(
        Enum(OnboardingStepType, name="onboarding_step_type", native_enum=False, length=20), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Only meaningful for TASK steps — how many days after case start the
    # generated task's due_at is set to. DOCUMENT_REQUEST steps have no
    # due date of their own (a document request stays open until fulfilled).
    due_in_days: Mapped[int | None] = mapped_column(Integer, nullable=True)


class OnboardingCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "onboarding_cases"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("onboarding_templates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[OnboardingCaseStatus] = mapped_column(
        Enum(OnboardingCaseStatus, name="onboarding_case_status", native_enum=False, length=20),
        nullable=False, default=OnboardingCaseStatus.NOT_STARTED,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class OnboardingCaseStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Instantiated from an `OnboardingTemplateStep` (or added ad hoc with
    no `template_step_id`) when a case starts. `task_id`/`document_request_id`
    point at the real `Task`/`DocumentRequest` row this step spawned —
    `crm.service.complete_task` and `documents.service.approve_document_request`
    each call back into `onboarding.service` to advance the matching step
    when that underlying resource is finished."""

    __tablename__ = "onboarding_case_steps"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("onboarding_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("onboarding_template_steps.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    step_type: Mapped[OnboardingStepType] = mapped_column(
        Enum(OnboardingStepType, name="onboarding_step_type", native_enum=False, length=20), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[OnboardingCaseStepStatus] = mapped_column(
        Enum(OnboardingCaseStepStatus, name="onboarding_case_step_status", native_enum=False, length=20),
        nullable=False, default=OnboardingCaseStepStatus.PENDING,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    document_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_requests.id", ondelete="SET NULL"), nullable=True, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
