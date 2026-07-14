import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class QualificationQuestionType(str, enum.Enum):
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"
    EMAIL = "email"
    PHONE = "phone"
    NUMBER = "number"
    CURRENCY = "currency"
    DATE = "date"
    SINGLE_SELECT = "single_select"
    MULTI_SELECT = "multi_select"
    CHECKBOX = "checkbox"
    YES_NO = "yes_no"


class LeadPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConsentStatus(str, enum.Enum):
    PENDING = "pending"
    GIVEN = "given"
    DECLINED = "declined"


class PreferredContactMethod(str, enum.Enum):
    EMAIL = "email"
    PHONE = "phone"
    WHATSAPP = "whatsapp"


class ServiceCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_service_categories_tenant_name"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Service(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "services"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_services_tenant_name"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class QualificationForm(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "qualification_forms"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # NULL service_id = the default/general form used when a service has no dedicated form.
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    questions: Mapped[list["QualificationQuestion"]] = relationship(
        back_populates="form", cascade="all, delete-orphan", order_by="QualificationQuestion.sort_order"
    )


class QualificationQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "qualification_questions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("qualification_forms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    question_type: Mapped[QualificationQuestionType] = mapped_column(
        Enum(QualificationQuestionType, name="qualification_question_type", native_enum=False, length=20), nullable=False
    )
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Field-name convention this question maps onto a core Lead column
    # (e.g. "service_id", "preferred_contact_method") — NULL means it is
    # a free-form qualification answer with no dedicated Lead column.
    maps_to_field: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # {"show_if_question_id": "...", "show_if_value": "..."} — optional, simple single-condition visibility.
    conditional_on: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    form: Mapped["QualificationForm"] = relationship(back_populates="questions")
    options: Mapped[list["QualificationOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="QualificationOption.sort_order"
    )


class QualificationOption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "qualification_options"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("qualification_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    question: Mapped["QualificationQuestion"] = relationship(back_populates="options")


class QualificationAnswer(UUIDPrimaryKeyMixin, Base):
    """Historical record of what was actually answered — immutable once
    written, preserved even if the question/options are later edited."""

    __tablename__ = "qualification_answers"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("qualification_questions.id", ondelete="RESTRICT"), nullable=False
    )
    question_label: Mapped[str] = mapped_column(String(300), nullable=False)
    answer_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CustomFieldDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "custom_field_definitions"
    __table_args__ = (UniqueConstraint("tenant_id", "entity_type", "code", name="uq_custom_field_defs_tenant_entity_code"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, default="lead")
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    field_type: Mapped[QualificationQuestionType] = mapped_column(
        Enum(QualificationQuestionType, name="custom_field_type", native_enum=False, length=20), nullable=False
    )
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CustomFieldOption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "custom_field_options"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class LeadSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_sources"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_lead_sources_tenant_code"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leads"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reference_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(CITEXT, nullable=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)

    service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lead_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    pipeline_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_stages.id", ondelete="SET NULL"), nullable=True, index=True
    )

    priority: Mapped[LeadPriority] = mapped_column(
        Enum(LeadPriority, name="lead_priority", native_enum=False, length=20), nullable=False, default=LeadPriority.MEDIUM
    )
    # Set automatically the moment staff manually change `priority` — once
    # true, scoring's auto-priority mapping (Milestone 3) no longer
    # overwrites it on recompute.
    priority_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)

    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # multi_branch is a later milestone

    preferred_contact_method: Mapped[PreferredContactMethod | None] = mapped_column(
        Enum(PreferredContactMethod, name="preferred_contact_method", native_enum=False, length=20), nullable=True
    )
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus, name="consent_status", native_enum=False, length=20), nullable=False, default=ConsentStatus.PENDING
    )

    custom_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Attribution / anti-abuse metadata for publicly-submitted leads.
    utm_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(200), nullable=True)
    submitted_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    is_possible_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_of_lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
