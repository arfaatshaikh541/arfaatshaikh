"""Business and BusinessSourceRecord.

A Business is the tenant-owned, individually addressable record a
discovered business becomes once a campaign task processes it - the
persistence layer the original architecture's "Business Data Model"
section calls for. Milestone 2 did not build this (it only stored a raw
JSON snapshot per campaign task page - see `CampaignTask.result_snapshot`),
which was a real gap: there was nothing with its own stable ID for
Milestone 4's website enrichment to attach evidence to. See docs/adr/0011.

Consolidated from the full architecture's larger entity list, following
the same reasoning as ADR-0008: BusinessIdentifier/BusinessCategory/
BusinessLocation/BusinessContact/BusinessWebsite/BusinessSocialProfile are
all 1:1 with Business and live as columns directly on it here; per-field
provenance (source, confidence, collected_at) lives in a `field_provenance`
JSONB column rather than a separate BusinessFieldProvenance table, for the
same "no join for a 1:1-shaped concern" reason ADR-0008 gave. This is
metadata *about* a Business's own current field values, not a 1:many
relationship in its own right.

`BusinessSourceRecord` DOES get its own real table: a business can
genuinely be rediscovered by multiple campaigns over time, and each
rediscovery's full raw connector output must be preserved, not
overwritten - this is what "preserve source provenance" and Milestone 5's
future deduplication step both need. `BusinessSnapshot` and
`BusinessMergeHistory` are Milestone 5 scope - there is nothing to
snapshot-diff or merge yet with only one discovery pipeline feeding one
Business per source record and no merge step implemented.

`Business.email` is deliberately never set by discovery - Google Places
(and the mock connector, matching it) has no email field at all in its
schema. It is populated exclusively by Milestone 4's enrichment crawler,
which is a clean, structural way to guarantee it is never fabricated.

`Business.merged_into_id`, `BusinessDuplicateCandidate`, and
`BusinessMergeHistory` are Milestone 5's deduplication entities - see
`app.modules.businesses.dedup` and docs/adr/0013. A merged-away Business
row is never deleted (its `merged_into_id` is set instead, and every
query that should only see canonical businesses filters
`merged_into_id IS NULL`), so `BusinessSourceRecord`/`BusinessEnrichment`/
`EnrichmentEvidence` rows reassigned onto the surviving business remain
attached to a real row, and a merge remains reversible.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPKMixin

DUPLICATE_CANDIDATE_STATUSES = ("pending", "confirmed", "rejected")
DUPLICATE_MATCH_TYPES = ("identifier", "domain", "phone", "name_address", "fuzzy_name")


class Business(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "businesses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_businesses_tenant_id_id"),
        # Self-referential and composite so a merge can never point across
        # a tenant boundary - the same defense-in-depth reasoning as every
        # other composite FK in this schema (see ADR-0007's RLS notes).
        ForeignKeyConstraint(
            ["tenant_id", "merged_into_id"],
            ["businesses.tenant_id", "businesses.id"],
            name="fk_businesses_tenant_merged_into",
            ondelete="SET NULL",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str | None] = mapped_column(String(150), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(150), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Indexed: dedup's name+address/fuzzy-name tiers (dedup.py) narrow
    # their candidate set to same-city businesses before comparing names,
    # rather than scanning every business a tenant has ever discovered.
    city: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Digits-only form of `phone`, kept in sync with it (see
    # dedup.normalize_phone) purely so phone-tier duplicate matching can
    # use an indexed equality lookup instead of scanning every row in
    # Python to compare normalized forms.
    normalized_phone: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    # Enrichment-only (Milestone 4) - never set by discovery. See module docstring.
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    canonical_domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    google_place_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    google_maps_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rating: Mapped[float | None] = mapped_column(Numeric(2, 1), nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    business_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # {field_name: {"source": str, "source_record_id": str, "confidence": float, "collected_at": iso str}}
    field_provenance: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # NULL = canonical (the normal case). Set when this row lost a merge -
    # points at the surviving Business. Never deleted, so the merge stays
    # reversible; every listing/lookup query filters merged_into_id IS NULL
    # unless it explicitly wants merged-away rows too. See dedup.py.
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )


class BusinessSourceRecord(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "business_source_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source",
            "source_native_id",
            name="uq_business_source_records_tenant_source_native_id",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "business_id"],
            ["businesses.tenant_id", "businesses.id"],
            name="fk_business_source_records_tenant_business",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    business_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    # Plain (non-composite) FK, deliberately: a composite ["tenant_id",
    # "campaign_id"] FK with ondelete="SET NULL" would null out *every*
    # column in that constraint on delete - including tenant_id, which
    # would corrupt the row's RLS scoping. campaign_id here is purely an
    # informational backreference ("which campaign last (re)discovered
    # this"); the row's own tenant_id (validated separately via the
    # business_id composite FK above) is what actually governs access.
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_native_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)


class BusinessDuplicateCandidate(Base, UUIDPKMixin, TimestampMixin):
    """One pair of businesses `dedup.py` found a match between, below the
    auto-merge confidence threshold - never merged silently, always
    waiting for a human `confirm`/`reject` decision (see `leads.edit`
    permission). `business_id_a`/`business_id_b` are stored with the
    smaller UUID always in slot `a`, so the same real-world pair can never
    produce two candidate rows regardless of which business was
    (re)discovered first."""

    __tablename__ = "business_duplicate_candidates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "business_id_a",
            "business_id_b",
            name="uq_business_duplicate_candidates_tenant_pair",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "business_id_a"],
            ["businesses.tenant_id", "businesses.id"],
            name="fk_business_duplicate_candidates_tenant_business_a",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "business_id_b"],
            ["businesses.tenant_id", "businesses.id"],
            name="fk_business_duplicate_candidates_tenant_business_b",
            ondelete="CASCADE",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    business_id_a: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    business_id_b: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    match_type: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    # What actually matched, e.g. {"domain": "joespizza.example"} or
    # {"name_similarity": 0.91, "name_a": "...", "name_b": "..."} - so a
    # reviewer can see *why* without re-deriving it themselves.
    matched_fields: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BusinessMergeHistory(Base, UUIDPKMixin, TimestampMixin):
    """One completed merge: `loser_business_id` lost (its row still exists,
    `merged_into_id` now points at `winner_business_id`). `moved_records`
    and `field_changes` capture exactly enough to make `dedup.undo_merge`
    a precise reversal rather than a best-effort guess - see that
    function's own docstring for the exact shape of each."""

    __tablename__ = "business_merge_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "winner_business_id"],
            ["businesses.tenant_id", "businesses.id"],
            name="fk_business_merge_history_tenant_winner",
            ondelete="CASCADE",
        ),
        # Deliberately NOT a composite FK to businesses on loser_business_id:
        # the loser row is never deleted (merges are soft), so this could
        # be a plain composite FK too, but keeping it a plain column avoids
        # any ondelete ambiguity if a future hard-delete path is ever added
        # for merged-away rows - the tenant_id column alone (validated via
        # the winner FK above, since both sides are always same-tenant by
        # construction in dedup.py) is sufficient for RLS.
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    winner_business_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    loser_business_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    match_type: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    merged_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # {"source_records": [uuid, ...], "enrichments": [uuid, ...], "evidence": [uuid, ...],
    #  "lead_moved": bool, "lead_deleted_id": str | None} - the exact set of
    # rows this merge reassigned onto the winner, so undo touches only
    # those rows, never anything created after the merge that happens to
    # share the winner's business_id.
    moved_records: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # {field_name: {"winner_before": Any, "took_loser_value": bool}} - only
    # for fields the merge actually changed on the winner (the loser had
    # strictly higher confidence for that field - see dedup.py). Undo
    # restores exactly these fields to their "winner_before" value.
    field_changes: Mapped[dict] = mapped_column(JSONB, nullable=False)
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    undone_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
