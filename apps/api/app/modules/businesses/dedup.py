"""Deduplication: find candidate duplicate `Business` rows, decide
auto-merge vs. human review, and perform (and reverse) merges.

Follows the architecture's exact priority order - identifier, then
domain, then phone, then name+address, then conservative fuzzy name
matching - stopping at the first tier that finds a match, since a
stronger signal makes a weaker one redundant. See docs/adr/0013 for the
full design and the confidence numbers chosen below.

**Auto-merge vs. candidate.** Every match tier is assigned a fixed
confidence. `AUTO_MERGE_CONFIDENCE_THRESHOLD` is the single rule that
decides "never silently merge uncertain records": a match at or above it
merges immediately; anything below becomes a `BusinessDuplicateCandidate`
for a human to confirm or reject. The four exact-match tiers
(identifier/domain/phone/name+address) are all fixed above the
threshold; fuzzy name matching is deliberately capped so it can never
reach it, no matter how similar two names look - "conservative" means
fuzzy matches always wait for a person.

**Merges are soft and reversible.** The losing `Business` row is never
deleted - `merged_into_id` is set instead, its `BusinessSourceRecord`/
`BusinessEnrichment`/`EnrichmentEvidence` rows are reassigned onto the
winner (recorded in `BusinessMergeHistory.moved_records` by exact row ID,
so `undo_merge` only touches what THIS merge moved, never anything
created afterwards that happens to share the winner's `business_id`).
Field data is combined, not overwritten: a field the loser knows with
higher confidence than the winner currently has fills in on the winner
(reusing the same "never overwrite higher-confidence data silently" rule
`field_provenance` already enforces at discovery time - see
`repositories.upsert_business_from_discovery`), and exactly what changed
is recorded in `BusinessMergeHistory.field_changes` so undo can restore
the winner's prior values precisely.

**Milestone 6 addendum: `Lead` rows follow their `Business` on merge, if
that can be done unambiguously.** If only the loser has a `Lead`, it is
reassigned onto the winner (`Lead.business_id = winner.id`) - since every
`LeadScore`/`LeadOpportunity`/`LeadRecommendation`/`LeadNote`/`LeadTag`/
`LeadStatusHistory`/`LeadAssignment` row keys off `lead_id`, not
`business_id`, moving the one `Lead` row carries its entire history along
for free, fully reversible the same way as everything else here. If
*both* businesses already have a `Lead` (both discovered independently,
scored/noted/tagged before ever being recognized as duplicates), this
merge deliberately does **not** attempt to reconcile two independent
sets of human-authored history into one - the loser's `Lead` is left
exactly as it is, simply excluded from `leads.repositories.list_leads`
(which joins through `Business.merged_into_id IS NULL`) rather than
silently deleted or blended. See docs/adr/0014.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationAppError
from app.modules.businesses import repositories as repo
from app.modules.businesses.models import (
    Business,
    BusinessDuplicateCandidate,
    BusinessMergeHistory,
    BusinessSourceRecord,
)
from app.modules.businesses.normalize import (
    canonical_domain,
    normalize_address,
    normalize_name,
    normalize_phone,
)
from app.modules.enrichment.models import BusinessEnrichment, EnrichmentEvidence
from app.modules.leads.models import Lead

# Priority order, highest confidence (strongest signal) first - matches
# the architecture's own "deduplicate in this priority" list exactly.
_MATCH_CONFIDENCE: dict[str, float] = {
    "identifier": 1.00,
    "domain": 0.95,
    "phone": 0.90,
    "name_address": 0.88,
}
AUTO_MERGE_CONFIDENCE_THRESHOLD = 0.85
# Fuzzy confidence is `similarity * _FUZZY_CONFIDENCE_SCALE`, capped so it
# can never reach AUTO_MERGE_CONFIDENCE_THRESHOLD even at a perfect 1.0
# similarity (which the exact name_address tier above would have already
# caught anyway).
_FUZZY_NAME_SIMILARITY_THRESHOLD = 0.88
_FUZZY_CONFIDENCE_SCALE = 0.75

# Fields eligible to move from a loser onto a winner during a merge, if
# the loser's own provenance confidence for that field is higher. Mirrors
# repositories.DISCOVERY_FIELDS plus "email" (enrichment-owned, but
# still a real field worth preserving from a merged-away record).
_MERGEABLE_FIELDS = (*repo.DISCOVERY_FIELDS, "email")


@dataclass
class DuplicateMatch:
    other: Business
    match_type: str
    confidence: float
    matched_fields: dict[str, Any]


def _json_safe(value: Any) -> Any:
    return float(value) if isinstance(value, Decimal) else value


async def find_duplicate_matches(session: AsyncSession, business: Business) -> list[DuplicateMatch]:
    """Checks tiers in priority order, returning as soon as one tier finds
    matches (a stronger signal makes weaker ones redundant) - except the
    fuzzy tier, which can return more than one candidate since "conservative
    similarity above a threshold" naturally may match several names."""
    if business.merged_into_id is not None:
        return []

    tenant_id = business.tenant_id
    base_filters = (
        Business.tenant_id == tenant_id,
        Business.id != business.id,
        Business.merged_into_id.is_(None),
    )

    if business.google_place_id:
        stmt = select(Business).where(
            *base_filters, Business.google_place_id == business.google_place_id
        )
        others = (await session.execute(stmt)).scalars().all()
        if others:
            return [
                DuplicateMatch(
                    o,
                    "identifier",
                    _MATCH_CONFIDENCE["identifier"],
                    {"google_place_id": business.google_place_id},
                )
                for o in others
            ]

    if business.canonical_domain:
        stmt = select(Business).where(
            *base_filters, Business.canonical_domain == business.canonical_domain
        )
        others = (await session.execute(stmt)).scalars().all()
        if others:
            return [
                DuplicateMatch(
                    o,
                    "domain",
                    _MATCH_CONFIDENCE["domain"],
                    {"canonical_domain": business.canonical_domain},
                )
                for o in others
            ]

    if business.normalized_phone:
        stmt = select(Business).where(
            *base_filters, Business.normalized_phone == business.normalized_phone
        )
        others = (await session.execute(stmt)).scalars().all()
        if others:
            return [
                DuplicateMatch(
                    o,
                    "phone",
                    _MATCH_CONFIDENCE["phone"],
                    {"normalized_phone": business.normalized_phone},
                )
                for o in others
            ]

    normalized_own_name = normalize_name(business.name)
    candidates: list[Business] = []
    if business.city:
        # Narrowed to same-city, both for correctness (a name+address or
        # fuzzy-name match across two different cities is not
        # "conservative") and to bound the comparison set - see the
        # `city` column's index comment in models.py.
        stmt = select(Business).where(*base_filters, Business.city == business.city)
        candidates = list((await session.execute(stmt)).scalars().all())

    if business.address and candidates:
        normalized_own_address = normalize_address(business.address)
        exact_matches = [
            c
            for c in candidates
            if normalize_name(c.name) == normalized_own_name
            and c.address
            and normalize_address(c.address) == normalized_own_address
        ]
        if exact_matches:
            return [
                DuplicateMatch(
                    o,
                    "name_address",
                    _MATCH_CONFIDENCE["name_address"],
                    {"name": business.name, "address": business.address},
                )
                for o in exact_matches
            ]

    fuzzy_matches: list[DuplicateMatch] = []
    for candidate in candidates:
        ratio = SequenceMatcher(None, normalized_own_name, normalize_name(candidate.name)).ratio()
        if ratio >= _FUZZY_NAME_SIMILARITY_THRESHOLD:
            fuzzy_matches.append(
                DuplicateMatch(
                    candidate,
                    "fuzzy_name",
                    round(ratio * _FUZZY_CONFIDENCE_SCALE, 2),
                    {
                        "name_similarity": round(ratio, 2),
                        "name_a": business.name,
                        "name_b": candidate.name,
                    },
                )
            )
    return fuzzy_matches


def _pick_winner(a: Business, b: Business) -> tuple[Business, Business]:
    """The business with richer existing data wins (so a thinly-populated
    fresh discovery never displaces an already-enriched record); ties
    broken by whichever was discovered first."""
    score_a, score_b = len(a.field_provenance), len(b.field_provenance)
    if score_a != score_b:
        return (a, b) if score_a > score_b else (b, a)
    return (a, b) if a.created_at <= b.created_at else (b, a)


async def merge_businesses(
    session: AsyncSession,
    *,
    winner_id: uuid.UUID,
    loser_id: uuid.UUID,
    match_type: str,
    confidence: float,
    merged_by_user_id: uuid.UUID | None = None,
) -> BusinessMergeHistory:
    if winner_id == loser_id:
        raise ValidationAppError("Cannot merge a business into itself.")
    winner = await repo.get_business_or_raise(session, winner_id)
    loser = await repo.get_business_or_raise(session, loser_id)
    if winner.tenant_id != loser.tenant_id:
        raise ValidationAppError("Cannot merge businesses belonging to different tenants.")
    if winner.merged_into_id is not None or loser.merged_into_id is not None:
        raise ConflictError("Both businesses must be canonical (not already merged) to merge.")

    source_stmt = select(BusinessSourceRecord).where(BusinessSourceRecord.business_id == loser.id)
    source_records = list((await session.execute(source_stmt)).scalars().all())
    for source_record in source_records:
        source_record.business_id = winner.id

    enrichment_stmt = select(BusinessEnrichment).where(BusinessEnrichment.business_id == loser.id)
    enrichments = list((await session.execute(enrichment_stmt)).scalars().all())
    for enrichment in enrichments:
        enrichment.business_id = winner.id

    evidence_stmt = select(EnrichmentEvidence).where(EnrichmentEvidence.business_id == loser.id)
    evidence_rows = list((await session.execute(evidence_stmt)).scalars().all())
    for evidence in evidence_rows:
        evidence.business_id = winner.id

    field_changes: dict[str, Any] = {}
    winner_provenance = dict(winner.field_provenance)
    loser_provenance = loser.field_provenance
    for field_name in _MERGEABLE_FIELDS:
        loser_entry = loser_provenance.get(field_name)
        if loser_entry is None:
            continue
        winner_entry = winner_provenance.get(field_name)
        winner_confidence = winner_entry["confidence"] if winner_entry else -1.0
        if loser_entry["confidence"] > winner_confidence:
            field_changes[field_name] = {
                "winner_before_value": _json_safe(getattr(winner, field_name)),
                "winner_before_provenance": winner_entry,
            }
            setattr(winner, field_name, getattr(loser, field_name))
            winner_provenance[field_name] = loser_entry

    if field_changes:
        winner.field_provenance = winner_provenance
        if "website" in field_changes:
            winner.canonical_domain = canonical_domain(winner.website) if winner.website else None
        if "phone" in field_changes:
            winner.normalized_phone = normalize_phone(winner.phone) if winner.phone else None

    loser.merged_into_id = winner.id

    # Milestone 6: move the loser's Lead onto the winner, only if the
    # winner doesn't already have one - see module docstring for why the
    # both-have-a-Lead case is deliberately left alone rather than
    # reconciled here.
    moved_lead_id: str | None = None
    loser_lead_stmt = select(Lead).where(Lead.business_id == loser.id)
    loser_lead = (await session.execute(loser_lead_stmt)).scalar_one_or_none()
    if loser_lead is not None:
        winner_lead_stmt = select(Lead).where(Lead.business_id == winner.id)
        winner_lead = (await session.execute(winner_lead_stmt)).scalar_one_or_none()
        if winner_lead is None:
            loser_lead.business_id = winner.id
            moved_lead_id = str(loser_lead.id)

    merge_history = BusinessMergeHistory(
        tenant_id=winner.tenant_id,
        winner_business_id=winner.id,
        loser_business_id=loser.id,
        match_type=match_type,
        confidence=confidence,
        merged_by_user_id=merged_by_user_id,
        moved_records={
            "source_records": [str(r.id) for r in source_records],
            "enrichments": [str(r.id) for r in enrichments],
            "evidence": [str(r.id) for r in evidence_rows],
            "lead": moved_lead_id,
        },
        field_changes=field_changes,
    )
    session.add(merge_history)
    await session.flush()
    return merge_history


async def undo_merge(
    session: AsyncSession, *, merge_history_id: uuid.UUID, actor_user_id: uuid.UUID | None = None
) -> BusinessMergeHistory:
    merge_history = await repo.get_merge_history_or_raise(session, merge_history_id)
    if merge_history.undone_at is not None:
        raise ConflictError("This merge has already been undone.")

    winner = await repo.get_business_or_raise(session, merge_history.winner_business_id)
    loser = await repo.get_business_or_raise(session, merge_history.loser_business_id)

    loser.merged_into_id = None

    moved = merge_history.moved_records
    if moved.get("source_records"):
        source_record_ids = [uuid.UUID(i) for i in moved["source_records"]]
        source_stmt = select(BusinessSourceRecord).where(
            BusinessSourceRecord.id.in_(source_record_ids)
        )
        for record in (await session.execute(source_stmt)).scalars().all():
            record.business_id = loser.id
    if moved.get("enrichments"):
        enrichment_ids = [uuid.UUID(i) for i in moved["enrichments"]]
        enrichment_stmt = select(BusinessEnrichment).where(
            BusinessEnrichment.id.in_(enrichment_ids)
        )
        for enrichment in (await session.execute(enrichment_stmt)).scalars().all():
            enrichment.business_id = loser.id
    if moved.get("evidence"):
        evidence_ids = [uuid.UUID(i) for i in moved["evidence"]]
        evidence_stmt = select(EnrichmentEvidence).where(EnrichmentEvidence.id.in_(evidence_ids))
        for evidence in (await session.execute(evidence_stmt)).scalars().all():
            evidence.business_id = loser.id
    if moved.get("lead"):
        lead_stmt = select(Lead).where(Lead.id == uuid.UUID(moved["lead"]))
        moved_lead = (await session.execute(lead_stmt)).scalar_one_or_none()
        if moved_lead is not None:
            moved_lead.business_id = loser.id

    if merge_history.field_changes:
        winner_provenance = dict(winner.field_provenance)
        for field_name, change in merge_history.field_changes.items():
            setattr(winner, field_name, change["winner_before_value"])
            if change["winner_before_provenance"] is None:
                winner_provenance.pop(field_name, None)
            else:
                winner_provenance[field_name] = change["winner_before_provenance"]
        winner.field_provenance = winner_provenance
        if "website" in merge_history.field_changes:
            winner.canonical_domain = canonical_domain(winner.website) if winner.website else None
        if "phone" in merge_history.field_changes:
            winner.normalized_phone = normalize_phone(winner.phone) if winner.phone else None

    merge_history.undone_at = datetime.now(UTC)
    merge_history.undone_by_user_id = actor_user_id
    await session.flush()
    return merge_history


async def _create_or_update_candidate(
    session: AsyncSession, business: Business, match: DuplicateMatch
) -> BusinessDuplicateCandidate:
    business_id_a, business_id_b = sorted([business.id, match.other.id])
    existing = await repo.get_duplicate_candidate_by_pair(
        session,
        tenant_id=business.tenant_id,
        business_id_a=business_id_a,
        business_id_b=business_id_b,
    )
    if existing is not None:
        if existing.status == "pending" and match.confidence > float(existing.confidence):
            existing.match_type = match.match_type
            existing.confidence = match.confidence
            existing.matched_fields = match.matched_fields
        return existing

    candidate = BusinessDuplicateCandidate(
        tenant_id=business.tenant_id,
        business_id_a=business_id_a,
        business_id_b=business_id_b,
        match_type=match.match_type,
        confidence=match.confidence,
        matched_fields=match.matched_fields,
        status="pending",
    )
    session.add(candidate)
    await session.flush()
    return candidate


async def process_new_business_for_duplicates(session: AsyncSession, business: Business) -> None:
    """Called once per (re)discovered business, right after
    `repositories.upsert_business_from_discovery`. Finds the best match
    (if any); auto-merges it if confidence clears the threshold, otherwise
    records/updates a `BusinessDuplicateCandidate` for every match found at
    this tier for a human to review. Never merges more than one pair per
    call - if three+ businesses are genuinely the same real place, later
    (re)discoveries of any of them will keep finding and resolving the
    remaining pairs, converging over time rather than in one pass."""
    matches = await find_duplicate_matches(session, business)
    if not matches:
        return

    best = max(matches, key=lambda m: m.confidence)
    if best.confidence >= AUTO_MERGE_CONFIDENCE_THRESHOLD:
        winner, loser = _pick_winner(business, best.other)
        await merge_businesses(
            session,
            winner_id=winner.id,
            loser_id=loser.id,
            match_type=best.match_type,
            confidence=best.confidence,
        )
        return

    for match in matches:
        await _create_or_update_candidate(session, business, match)


async def confirm_candidate(
    session: AsyncSession, *, candidate_id: uuid.UUID, actor_user_id: uuid.UUID | None = None
) -> BusinessMergeHistory:
    """A human confirms a below-threshold match really is the same
    business - performs the merge the automatic pass declined to do
    silently."""
    candidate = await repo.get_duplicate_candidate_or_raise(session, candidate_id)
    if candidate.status != "pending":
        raise ConflictError(f"Duplicate candidate has already been {candidate.status}.")

    business_a = await repo.get_business_or_raise(session, candidate.business_id_a)
    business_b = await repo.get_business_or_raise(session, candidate.business_id_b)
    winner, loser = _pick_winner(business_a, business_b)
    merge_history = await merge_businesses(
        session,
        winner_id=winner.id,
        loser_id=loser.id,
        match_type=candidate.match_type,
        confidence=float(candidate.confidence),
        merged_by_user_id=actor_user_id,
    )
    candidate.status = "confirmed"
    candidate.reviewed_by_user_id = actor_user_id
    candidate.reviewed_at = datetime.now(UTC)
    return merge_history


async def reject_candidate(
    session: AsyncSession, *, candidate_id: uuid.UUID, actor_user_id: uuid.UUID | None = None
) -> BusinessDuplicateCandidate:
    """A human decides a below-threshold match is a false positive -
    the pair stays two distinct businesses, and (per
    `_create_or_update_candidate`) will not be re-proposed on a future
    (re)discovery, since a rejected decision should stick."""
    candidate = await repo.get_duplicate_candidate_or_raise(session, candidate_id)
    if candidate.status != "pending":
        raise ConflictError(f"Duplicate candidate has already been {candidate.status}.")

    candidate.status = "rejected"
    candidate.reviewed_by_user_id = actor_user_id
    candidate.reviewed_at = datetime.now(UTC)
    await session.flush()
    return candidate
