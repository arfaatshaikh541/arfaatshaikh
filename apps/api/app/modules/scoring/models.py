import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class ScoringOperator(str, enum.Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    IS_SET = "is_set"
    IN = "in"


class ScoringRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single deterministic condition -> points contribution. A lead's
    score is the clamped (0-100) sum of every active rule whose condition
    matches — see `app.modules.scoring.service.compute_score`."""

    __tablename__ = "scoring_rules"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    # Lead attribute name (e.g. "estimated_value", "consent_status",
    # "utm_source", "service_id") or "answer:<question_id>" for a
    # qualification-answer value.
    field: Mapped[str] = mapped_column(String(150), nullable=False)
    operator: Mapped[ScoringOperator] = mapped_column(
        Enum(ScoringOperator, name="scoring_operator", native_enum=False, length=20), nullable=False
    )
    # {"value": ...} — a single scalar or list, shape depends on operator.
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ScoringSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per tenant. `auto_priority` governs whether a recomputed
    score also updates `Lead.priority` (skipped once a lead's priority has
    been manually set — see `Lead.priority_locked`)."""

    __tablename__ = "scoring_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_scoring_settings_tenant"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hot_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    warm_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    auto_priority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LeadScoreLog(UUIDPrimaryKeyMixin, Base):
    """Immutable record of a score computation — the "explainable" part of
    "deterministic scoring rules with explainable results": which rules
    matched and how many points each contributed."""

    __tablename__ = "lead_score_logs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    total_score: Mapped[int] = mapped_column(Integer, nullable=False)
    # [{"rule_id": "...", "rule_name": "...", "points": N}, ...] — only
    # matched rules are listed.
    breakdown: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
