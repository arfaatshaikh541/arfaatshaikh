import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AssignmentStrategy(str, enum.Enum):
    ROUND_ROBIN = "round_robin"
    SERVICE_BASED = "service_based"
    PRIORITY_BASED = "priority_based"


class AssignmentRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Evaluated in `sort_order` for a newly-created (or re-scored) lead —
    the first active rule whose condition matches and whose eligible pool
    is non-empty wins. Branch-based assignment is intentionally not
    modelled yet: `Lead.branch_id` has no populated values or admin UI
    until the Multi-Branch milestone, so a branch strategy would have
    nothing to match against."""

    __tablename__ = "assignment_rules"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    strategy: Mapped[AssignmentStrategy] = mapped_column(
        Enum(AssignmentStrategy, name="assignment_strategy", native_enum=False, length=20), nullable=False
    )
    # service_based: {"service_ids": ["...", ...]}; priority_based:
    # {"priorities": ["high", ...]}; round_robin: {} (matches every lead).
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    eligible_user_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AssignmentRuleRoundRobinState(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "assignment_rule_round_robin_state"
    __table_args__ = (UniqueConstraint("rule_id", name="uq_assignment_rrs_rule"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignment_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    last_assigned_index: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
