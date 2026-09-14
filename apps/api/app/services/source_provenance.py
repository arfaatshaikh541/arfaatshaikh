from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.models.identity import User
from app.models.sources import (
    ApprovalPolicy, ClaimPassageLink, PassageCorrection, SourceClaim, SourceEdition,
    SourcePassage, SourceSupersession,
)
from app.schemas.sources import (
    ApprovalPolicyCreate, ClaimPassageLinkCreate, PassageCorrectionDecision,
    SourceClaimCreate, SupersessionCreate,
)


class SourceProvenanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_claim(self, payload: SourceClaimCreate, actor: User) -> SourceClaim:
        claim = SourceClaim(**payload.model_dump(), claim_status="draft", created_by_user_id=actor.id)
        self.session.add(claim)
        await self.session.flush()
        return claim

    async def link_passage(self, claim_id: UUID, payload: ClaimPassageLinkCreate, actor: User) -> ClaimPassageLink:
        claim = await self.session.get(SourceClaim, claim_id)
        passage = await self.session.get(SourcePassage, payload.passage_id)
        if claim is None or passage is None:
            raise ApplicationError("provenance_record_not_found", "Claim or source passage was not found.", 404)
        if payload.citation_end > len(passage.content):
            raise ApplicationError("citation_span_invalid", "Citation span exceeds the immutable passage content.", 422)
        link = ClaimPassageLink(claim_id=claim_id, created_by_user_id=actor.id, **payload.model_dump())
        self.session.add(link)
        await self.session.flush()
        return link

    async def request_correction(self, passage_id: UUID, reason: str, actor: User) -> PassageCorrection:
        if await self.session.get(SourcePassage, passage_id) is None:
            raise ApplicationError("passage_not_found", "Source passage was not found.", 404)
        correction = PassageCorrection(
            passage_id=passage_id, requested_by_user_id=actor.id, reason=reason,
            status="requested", created_at=datetime.now(UTC),
        )
        self.session.add(correction)
        await self.session.flush()
        return correction

    async def decide_correction(self, correction_id: UUID, payload: PassageCorrectionDecision, actor: User) -> PassageCorrection:
        correction = await self.session.get(PassageCorrection, correction_id)
        if correction is None:
            raise ApplicationError("correction_not_found", "Correction request was not found.", 404)
        if correction.status != "requested":
            raise ApplicationError("correction_already_decided", "Correction request has already been decided.", 409)
        if payload.status == "accepted" and payload.replacement_passage_id is None:
            raise ApplicationError("replacement_required", "Accepted corrections require a replacement passage.", 422)
        if payload.replacement_passage_id is not None and await self.session.get(SourcePassage, payload.replacement_passage_id) is None:
            raise ApplicationError("replacement_not_found", "Replacement passage was not found.", 404)
        correction.status = payload.status
        correction.replacement_passage_id = payload.replacement_passage_id
        correction.decision_notes = payload.decision_notes
        correction.decided_by_user_id = actor.id
        correction.decided_at = datetime.now(UTC)
        await self.session.flush()
        return correction

    async def supersede_edition(self, edition_id: UUID, payload: SupersessionCreate, actor: User) -> SourceSupersession:
        old = await self.session.get(SourceEdition, edition_id)
        new = await self.session.get(SourceEdition, payload.replacement_edition_id)
        if old is None or new is None:
            raise ApplicationError("edition_not_found", "Superseded or replacement edition was not found.", 404)
        if old.source_id != new.source_id:
            raise ApplicationError("cross_source_supersession", "Replacement edition must belong to the same source.", 422)
        old.ingestion_status = "retired"
        old.approved_for_retrieval = False
        record = SourceSupersession(
            superseded_edition_id=old.id, replacement_edition_id=new.id,
            rationale=payload.rationale, recorded_by_user_id=actor.id, created_at=datetime.now(UTC),
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def create_policy(self, payload: ApprovalPolicyCreate, actor: User) -> ApprovalPolicy:
        policy = ApprovalPolicy(
            source_type=payload.source_type, policy_version=payload.policy_version, status="draft",
            minimum_reviewers=payload.minimum_reviewers,
            require_legal_approval=payload.require_legal_approval,
            require_integrity_verification=payload.require_integrity_verification,
            required_review_domains=json.dumps(sorted(payload.required_review_domains)),
            created_by_user_id=actor.id,
        )
        self.session.add(policy)
        await self.session.flush()
        return policy

    async def activate_policy(self, policy_id: UUID) -> ApprovalPolicy:
        policy = await self.session.get(ApprovalPolicy, policy_id)
        if policy is None:
            raise ApplicationError("approval_policy_not_found", "Approval policy was not found.", 404)
        active = await self.session.scalars(
            select(ApprovalPolicy).where(ApprovalPolicy.source_type == policy.source_type, ApprovalPolicy.status == "active")
        )
        for current in active:
            current.status = "retired"
        policy.status = "active"
        await self.session.flush()
        return policy
