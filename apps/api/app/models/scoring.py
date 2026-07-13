import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, new_uuid

SCORING_RULE_TYPES = (
    "service_equals",
    "source_equals",
    "estimated_value_at_least",
    "consent_given",
    "complete_contact_info",
    "repeat_enquiry",
    "answer_equals",
)


class ScoringRule(TimestampMixin, Base):
    __tablename__ = "scoring_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(40), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TenantScoringSettings(TimestampMixin, Base):
    __tablename__ = "tenant_scoring_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    hot_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    warm_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    standard_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
