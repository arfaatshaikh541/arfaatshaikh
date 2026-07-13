import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_uuid
from app.models.custom_field import CustomFieldDefinition


class QualificationForm(TimestampMixin, Base):
    __tablename__ = "qualification_forms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    questions: Mapped[list["QualificationQuestion"]] = relationship(
        back_populates="form",
        cascade="all, delete-orphan",
        order_by="QualificationQuestion.sort_order",
        lazy="selectin",
    )


class QualificationQuestion(TimestampMixin, Base):
    __tablename__ = "qualification_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("qualification_forms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_field_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    help_text: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    form: Mapped["QualificationForm"] = relationship(back_populates="questions")
    field_definition: Mapped["CustomFieldDefinition"] = relationship(lazy="selectin")
    rules: Mapped[list["QualificationRule"]] = relationship(
        foreign_keys="QualificationRule.question_id",
        back_populates="question",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class QualificationRule(Base):
    """Conditional visibility: `question` is shown only if
    `depends_on_question`'s answer matches `depends_on_value`."""

    __tablename__ = "qualification_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("qualification_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    depends_on_question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("qualification_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    operator: Mapped[str] = mapped_column(String(20), nullable=False, default="equals")
    depends_on_value: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False, default="show")

    question: Mapped["QualificationQuestion"] = relationship(foreign_keys=[question_id])
