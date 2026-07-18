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
dismiss one without touching the others), a shape JSONB does not
represent well.

Milestone 6 (Lead Workspace) adds `assigned_to_user_id` directly on
`Lead` (the current assignment - a fast column for list filtering/
sorting, the same "current state on the parent row" pattern `Campaign.
status` already uses) plus four new tables: `LeadAssignment` and
`LeadStatusHistory` are append-only audit trails (the same shape as
`CampaignEvent`) recording every assignment/status change, who made it,
and when; `LeadNote` is a plain 1:many; `LeadTag` is a plain string tag
applied to a lead (no separate tag-vocabulary table - nothing here asks
for tag metadata/renaming/color, just applying and filtering by tags);
`SavedLeadView` stores a named, reusable filter/sort/column-selection
state, visible tenant-wide like everything else in this schema.

Lead status deliberately has **no transition state machine** (unlike
`state_machine.py`'s explicit campaign-status graph) - the architecture
gives Lead an enumerated status list but no transition rules, and real
sales workflows are non-linear (a rep can move a lead back to
"reviewed" from "contacted," or straight from "new" to "do_not_contact").
`services.change_status` validates only that the target is one of
`LEAD_STATUSES`, not that the transition is "legal" - see docs/adr/0014.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Numeric, String, UniqueConstraint
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
    # Current assignment (fast column for list filtering/sorting) - the
    # full history of who was assigned when lives in LeadAssignment.
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )


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


class LeadAssignment(Base, UUIDPKMixin, TimestampMixin):
    """One row per assignment event (append-only) - `unassigned_at` is set
    when this assignment is superseded by a later one or explicitly
    cleared, so "who was this lead assigned to on date X" stays
    answerable. `Lead.assigned_to_user_id` is always the assignment with
    `unassigned_at IS NULL`, if any."""

    __tablename__ = "lead_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            name="fk_lead_assignments_tenant_lead",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    assigned_to_user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LeadStatusHistory(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "lead_status_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            name="fk_lead_status_history_tenant_lead",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    from_status: Mapped[str] = mapped_column(String(20), nullable=False)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class LeadNote(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "lead_notes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            name="fk_lead_notes_tenant_lead",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(String(4000), nullable=False)


class LeadTag(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "lead_tags"
    __table_args__ = (
        UniqueConstraint("tenant_id", "lead_id", "tag", name="uq_lead_tags_tenant_lead_tag"),
        ForeignKeyConstraint(
            ["tenant_id", "lead_id"],
            ["leads.tenant_id", "leads.id"],
            name="fk_lead_tags_tenant_lead",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    tag: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SavedLeadView(Base, UUIDPKMixin, TimestampMixin):
    """A named, reusable filter/sort/column-selection state for the lead
    list - `filters` mirrors the same query-parameter shape
    `repositories.list_leads` accepts, so applying a saved view is just
    replaying its stored filters. Visible tenant-wide (like every other
    entity in this schema), but only its creator (or anyone with
    `leads.edit`) may delete it - enforced in the service layer, not by a
    DB constraint, since "who may delete" is a permission question, not a
    data-integrity one."""

    __tablename__ = "saved_lead_views"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_saved_lead_views_tenant_name"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False)
