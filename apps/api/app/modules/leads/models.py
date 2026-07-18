"""Lead, LeadScore, LeadOpportunity, LeadRecommendation.

`Lead` is the commercially-facing wrapper around a canonical
(non-merged) `Business` - one row, created the first time a business is
scored (`scoring.score_lead`), unique per (tenant, business). Milestone 5
only creates Lead rows and sets their initial "new" status; the full
status workflow (transitions, notes, tags, assignments -
LeadStatusHistory/LeadNote/LeadTag/LeadAssignment/SavedLeadView in the
architecture's Lead Model section) is Milestone 6's "Lead Workspace"
scope, not built here. `LeadCampaign` is not a separate table: a lead's
originating campaign(s) are already recoverable via
`BusinessSourceRecord.campaign_id` on its underlying Business, so a
redundant attribution join table would only duplicate data that already
exists - the same consolidation reasoning as ADR-0008/0011.

`LeadScore` is versioned and append-only: every call to
`scoring.score_lead` creates a NEW row rather than updating one in place,
so a lead's score history is preserved and each row's own
`calculated_at`/`algorithm_version` stay meaningful (the architecture's
explicit requirement - "every score must store... calculation timestamp"
- implies history, not an overwritten single value). Its `factors` JSONB
column holds the complete breakdown (key, label, score, max_score,
explanation, evidence reference per factor) rather than a separate
LeadScoreFactor table, since factors are always read and written
together as "the whole breakdown for this one score run" - the same "no
join for what's never queried independently" reasoning `field_provenance`
already established in Milestone 4 (see docs/adr/0011, docs/adr/0013).

`LeadOpportunity` and `LeadRecommendation` DO get their own tables:
unlike score factors, opportunities/recommendations accumulate as
independent facts about a lead (detected once, potentially referenced by
several recommendations, and a human may eventually want to review/
dismiss one without touching the others - a later Milestone 6 concern
this schema already accommodates), a shape JSONB does not represent well.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin

# The architecture's full Lead status lifecycle - stored now so a future
# Milestone 6 status-transition feature never needs a migration just to
# widen this column, even though only "new" is ever set by Milestone 5.
LEAD_STATUSES = (
    "new",
    "reviewed",
    "qualified",
    "unqualified",
    "assigned",
    "contacted",
    "interested",
    "converted",
    "do_not_contact",
    "archived",
)

SCORING_ALGORITHM_VERSION = "v1"


class Lead(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_leads_tenant_id_id"),
        UniqueConstraint("tenant_id", "business_id", name="uq_leads_tenant_business"),
        ForeignKeyConstraint(
            ["tenant_id", "business_id"],
            ["businesses.tenant_id", "businesses.id"],
            name="fk_leads_tenant_business",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    business_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="new", nullable=False, index=True)


class LeadScore(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "lead_scores"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            name="fk_lead_scores_tenant_lead",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    algorithm_version: Mapped[str] = mapped_column(String(20), nullable=False)
    total_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    max_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    # [{"key": str, "label": str, "score": float, "max_score": float,
    #   "explanation": str, "evidence": dict}, ...] - see scoring.py.
    factors: Mapped[list] = mapped_column(JSONB, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LeadOpportunity(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "lead_opportunities"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "lead_id",
            "opportunity_type",
            name="uq_lead_opportunities_tenant_lead_type",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            name="fk_lead_opportunities_tenant_lead",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    opportunity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    # What this opportunity is based on - an EnrichmentEvidence id, or a
    # plain Business field observation ({"business_field": "website",
    # "observed_value": null}) when it's not a crawl-derived signal. Never
    # empty - "never invent problems" means every opportunity must point
    # at something real that was actually observed.
    evidence_reference: Mapped[dict] = mapped_column(JSONB, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LeadRecommendation(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "lead_recommendations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "lead_id",
            "recommendation_type",
            name="uq_lead_recommendations_tenant_lead_type",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            name="fk_lead_recommendations_tenant_lead",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    recommendation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    # [str, ...] of LeadOpportunity ids this recommendation is based on -
    # never empty, per "recommendations must be evidence-based."
    supporting_opportunity_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    recommended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
