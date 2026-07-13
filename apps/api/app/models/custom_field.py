import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_uuid

FIELD_TYPES = (
    "short_text",
    "long_text",
    "email",
    "phone",
    "number",
    "currency",
    "date",
    "single_select",
    "multi_select",
    "checkbox",
    "yes_no",
)

SELECT_FIELD_TYPES = ("single_select", "multi_select")


class CustomFieldDefinition(TimestampMixin, Base):
    __tablename__ = "custom_field_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "entity_type", "field_key", name="uq_custom_field_tenant_entity_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False, default="lead")
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    field_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    options: Mapped[list["CustomFieldOption"]] = relationship(
        back_populates="field_definition",
        cascade="all, delete-orphan",
        order_by="CustomFieldOption.sort_order",
        lazy="selectin",
    )


class CustomFieldOption(Base):
    __tablename__ = "custom_field_options"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    field_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    field_definition: Mapped["CustomFieldDefinition"] = relationship(back_populates="options")
