import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_uuid
from app.models.pipeline import Tag

LEAD_SOURCES = ("public_form", "widget", "manual", "api", "webhook", "csv_import", "whatsapp")
LEAD_PRIORITIES = ("hot", "warm", "standard", "low_priority")
PREFERRED_CONTACT_METHODS = ("phone", "whatsapp", "email", "online_meeting")


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "reference_number", name="uq_lead_tenant_reference"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reference_number: Mapped[str] = mapped_column(String(20), nullable=False)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    company: Mapped[str | None] = mapped_column(String(200))

    service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_stages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score_reasons: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    estimated_value: Mapped[float | None] = mapped_column(Numeric(12, 2))

    assigned_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    preferred_contact_method: Mapped[str | None] = mapped_column(String(20))
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_text_shown: Mapped[str | None] = mapped_column(Text)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    utm_source: Mapped[str | None] = mapped_column(String(200))
    utm_medium: Mapped[str | None] = mapped_column(String(200))
    utm_campaign: Mapped[str | None] = mapped_column(String(200))
    utm_term: Mapped[str | None] = mapped_column(String(200))
    utm_content: Mapped[str | None] = mapped_column(String(200))
    referrer_url: Mapped[str | None] = mapped_column(Text)

    loss_reason_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loss_reasons.id", ondelete="SET NULL"), nullable=True
    )

    is_possible_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_of_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True
    )

    answers: Mapped[list["LeadAnswer"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )
    tag_links: Mapped[list["LeadTagLink"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )


class LeadAnswer(Base):
    """Snapshotted so editing/deactivating a question later never corrupts
    what was actually asked/answered at submission time."""

    __tablename__ = "lead_answers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("qualification_questions.id", ondelete="SET NULL"),
        nullable=True,
    )
    question_label_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    field_type_snapshot: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    lead: Mapped["Lead"] = relationship(back_populates="answers")


class LeadTagLink(Base):
    __tablename__ = "lead_tags"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    lead: Mapped["Lead"] = relationship(back_populates="tag_links")
    tag: Mapped["Tag"] = relationship(lazy="selectin")


class LeadStageHistory(Base):
    __tablename__ = "lead_stage_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_stages.id", ondelete="SET NULL"), nullable=True
    )
    to_stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_stages.id", ondelete="RESTRICT"), nullable=False
    )
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LeadNote(Base):
    __tablename__ = "lead_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
