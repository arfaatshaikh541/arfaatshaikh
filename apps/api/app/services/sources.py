from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.models.sources import (
    Source, SourceAcquisition, SourceAttribution, SourceEdition, SourceIntegrityRecord,
    ApprovalPolicy, SourceLifecycleEvent, SourceLicence, SourcePassage, SourceReview, SourceReviewAssignment,
)
from app.models.identity import User
from app.schemas.sources import (
    AcquisitionCreate, AttributionUpsert, EditionCreate, IngestionTransition, LicenceCreate,
    PassageCreate, ReviewAssignmentCreate, ReviewDecisionCreate, SourceCreate,
)
from app.services.source_lifecycle import RetrievalEligibility, ingestion_transition_allowed


class SourceRegistryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_licence(self, payload: LicenceCreate) -> SourceLicence:
        licence = SourceLicence(**payload.model_dump(), legal_review_status="pending")
        self.session.add(licence)
        await self.session.flush()
        return licence

    async def create_source(self, payload: SourceCreate) -> Source:
        source = Source(**payload.model_dump(), authority_status="unassessed")
        self.session.add(source)
        await self.session.flush()
        return source

    async def create_edition(self, source_id, payload: EditionCreate) -> SourceEdition:
        source = await self.session.get(Source, source_id)
        if source is None:
            raise ApplicationError("source_not_found", "Source was not found.", 404)
        if payload.licence_id is not None and await self.session.get(SourceLicence, payload.licence_id) is None:
            raise ApplicationError("licence_not_found", "Source licence was not found.", 404)
        duplicate = await self.session.scalar(
            select(SourceEdition.id).where(SourceEdition.source_id == source_id, SourceEdition.edition_key == payload.edition_key)
        )
        if duplicate:
            raise ApplicationError("edition_exists", "This edition key already exists for the source.", 409)
        edition = SourceEdition(
            source_id=source_id,
            **payload.model_dump(),
            ingestion_status="registered",
            review_status="pending",
            approved_for_retrieval=False,
        )
        self.session.add(edition)
        await self.session.flush()
        return edition

    async def record_acquisition(self, edition_id, payload: AcquisitionCreate, actor: User) -> SourceAcquisition:
        edition = await self.session.get(SourceEdition, edition_id)
        if edition is None:
            raise ApplicationError("edition_not_found", "Source edition was not found.", 404)
        acquisition = SourceAcquisition(
            edition_id=edition_id,
            recorded_by_user_id=actor.id,
            **payload.model_dump(),
        )
        self.session.add(acquisition)
        await self.session.flush()
        return acquisition



    async def update_licence_legal_review(self, licence_id: UUID, decision: str) -> SourceLicence:
        licence = await self.session.get(SourceLicence, licence_id)
        if licence is None:
            raise ApplicationError("licence_not_found", "Source licence was not found.", 404)
        licence.legal_review_status = decision
        await self.session.flush()
        return licence

    async def update_source_authority(self, source_id: UUID, status: str) -> Source:
        source = await self.session.get(Source, source_id)
        if source is None:
            raise ApplicationError("source_not_found", "Source was not found.", 404)
        source.authority_status = status
        if status != "approved":
            editions = await self.session.scalars(select(SourceEdition).where(SourceEdition.source_id == source_id))
            for edition in editions:
                edition.approved_for_retrieval = False
        await self.session.flush()
        return source

    async def transition_ingestion(self, edition_id: UUID, payload: IngestionTransition, actor: User) -> SourceEdition:
        edition = await self._edition_or_404(edition_id)
        if not ingestion_transition_allowed(edition.ingestion_status, payload.status):
            raise ApplicationError(
                "invalid_ingestion_transition",
                f"Cannot transition ingestion from {edition.ingestion_status} to {payload.status}.",
                409,
            )
        previous = edition.ingestion_status
        edition.ingestion_status = payload.status
        if payload.status != "ready":
            edition.approved_for_retrieval = False
        self.session.add(SourceLifecycleEvent(
            edition_id=edition.id, actor_user_id=actor.id, event_type="ingestion_status_changed",
            from_status=previous, to_status=payload.status, rationale=payload.rationale, created_at=datetime.now(UTC),
        ))
        await self.session.flush()
        return edition

    async def verify_integrity(self, edition_id: UUID, object_key: str, algorithm: str, actor: User, digest: str, byte_size: int) -> SourceIntegrityRecord:
        await self._edition_or_404(edition_id)
        record = SourceIntegrityRecord(
            edition_id=edition_id, object_key=object_key, algorithm=algorithm, digest=digest,
            byte_size=byte_size, verified=True, verified_at=datetime.now(UTC), created_at=datetime.now(UTC),
        )
        self.session.add(record)
        self.session.add(SourceLifecycleEvent(
            edition_id=edition_id, actor_user_id=actor.id, event_type="integrity_verified",
            from_status=None, to_status="verified", rationale=f"Verified {algorithm} digest for {object_key}.",
            created_at=datetime.now(UTC),
        ))
        await self.session.flush()
        return record

    async def assign_review(self, edition_id: UUID, payload: ReviewAssignmentCreate, actor: User) -> SourceReviewAssignment:
        await self._edition_or_404(edition_id)
        reviewer = await self.session.get(User, payload.reviewer_user_id)
        if reviewer is None or not reviewer.is_active or not reviewer.is_email_verified:
            raise ApplicationError("reviewer_unavailable", "Reviewer must be an active verified user.", 409)
        existing = await self.session.scalar(select(SourceReviewAssignment.id).where(
            SourceReviewAssignment.edition_id == edition_id,
            SourceReviewAssignment.reviewer_user_id == payload.reviewer_user_id,
            SourceReviewAssignment.review_domain == payload.review_domain,
            SourceReviewAssignment.status.in_(("assigned", "in_progress")),
        ))
        if existing:
            raise ApplicationError("review_already_assigned", "An active assignment already exists.", 409)
        assignment = SourceReviewAssignment(
            edition_id=edition_id, reviewer_user_id=payload.reviewer_user_id, assigned_by_user_id=actor.id,
            review_domain=payload.review_domain, status="assigned", due_at=payload.due_at,
        )
        self.session.add(assignment)
        edition = await self._edition_or_404(edition_id)
        edition.review_status = "in_review"
        edition.approved_for_retrieval = False
        await self.session.flush()
        return assignment

    async def submit_review(self, assignment_id: UUID, payload: ReviewDecisionCreate, actor: User) -> SourceReview:
        assignment = await self.session.get(SourceReviewAssignment, assignment_id)
        if assignment is None:
            raise ApplicationError("review_assignment_not_found", "Review assignment was not found.", 404)
        if assignment.reviewer_user_id != actor.id:
            raise ApplicationError("reviewer_mismatch", "Only the assigned reviewer may submit this review.", 403)
        if assignment.status in {"completed", "cancelled"}:
            raise ApplicationError("review_assignment_closed", "Review assignment is already closed.", 409)
        review = SourceReview(
            edition_id=assignment.edition_id, reviewer_user_id=actor.id, review_domain=assignment.review_domain,
            decision=payload.decision, rationale=payload.rationale,
            valid_until=payload.valid_until.date() if payload.valid_until else None, created_at=datetime.now(UTC),
        )
        self.session.add(review)
        assignment.status = "completed"
        assignment.completed_at = datetime.now(UTC)
        edition = await self._edition_or_404(assignment.edition_id)
        edition.review_status = payload.decision
        edition.approved_for_retrieval = False
        await self.session.flush()
        return review

    async def create_passage(self, edition_id: UUID, payload: PassageCreate, actor: User) -> SourcePassage:
        edition = await self._edition_or_404(edition_id)
        if edition.ingestion_status not in {"validating", "ready"}:
            raise ApplicationError("edition_not_ingestable", "Edition must be validating or ready.", 409)
        current = await self.session.scalar(select(SourcePassage).where(
            SourcePassage.edition_id == edition_id, SourcePassage.passage_key == payload.passage_key,
            SourcePassage.is_current.is_(True),
        ))
        version = 1
        if current is not None:
            current.is_current = False
            version = current.version + 1
        content = payload.content.replace("\r\n", "\n")
        passage = SourcePassage(
            edition_id=edition_id, passage_key=payload.passage_key, version=version, language=payload.language,
            source_locator=payload.source_locator, citation_label=payload.citation_label, content=content,
            content_sha256=sha256(content.encode("utf-8")).hexdigest(), is_current=True, created_by_user_id=actor.id,
        )
        self.session.add(passage)
        edition.approved_for_retrieval = False
        await self.session.flush()
        return passage

    async def upsert_attribution(self, edition_id: UUID, payload: AttributionUpsert) -> SourceAttribution:
        await self._edition_or_404(edition_id)
        attribution = await self.session.scalar(select(SourceAttribution).where(
            SourceAttribution.edition_id == edition_id, SourceAttribution.language == payload.language,
        ))
        if attribution is None:
            attribution = SourceAttribution(edition_id=edition_id, **payload.model_dump())
            self.session.add(attribution)
        else:
            for key, value in payload.model_dump().items():
                setattr(attribution, key, value)
        await self.session.flush()
        return attribution

    async def evaluate_retrieval(self, edition_id: UUID, actor: User) -> RetrievalEligibility:
        edition = await self._edition_or_404(edition_id)
        source = await self.session.get(Source, edition.source_id)
        licence = await self.session.get(SourceLicence, edition.licence_id) if edition.licence_id else None
        acquisition_count = await self.session.scalar(select(func.count()).select_from(SourceAcquisition).where(SourceAcquisition.edition_id == edition_id))
        integrity_count = await self.session.scalar(select(func.count()).select_from(SourceIntegrityRecord).where(SourceIntegrityRecord.edition_id == edition_id, SourceIntegrityRecord.verified.is_(True)))
        approved_reviews = list(await self.session.scalars(select(SourceReview).where(SourceReview.edition_id == edition_id, SourceReview.decision == "approved")))
        attribution_count = await self.session.scalar(select(func.count()).select_from(SourceAttribution).where(SourceAttribution.edition_id == edition_id))
        policy = await self.session.scalar(select(ApprovalPolicy).where(ApprovalPolicy.source_type == source.source_type, ApprovalPolicy.status == "active").order_by(ApprovalPolicy.policy_version.desc())) if source else None
        required_domains = set()
        if policy is not None:
            import json
            required_domains = set(json.loads(policy.required_review_domains))
        approved_domains = {review.review_domain for review in approved_reviews}
        unique_reviewers = {review.reviewer_user_id for review in approved_reviews}
        eligibility = RetrievalEligibility(
            source_approved=bool(source and source.authority_status == "approved"),
            licence_approved=bool(licence and licence.legal_review_status == "approved"),
            redistribution_allowed=bool(licence and licence.redistribution_allowed),
            acquisition_recorded=bool(acquisition_count), integrity_verified=bool(integrity_count),
            ingestion_ready=edition.ingestion_status == "ready",
            review_approved=edition.review_status == "approved" and bool(approved_reviews),
            attribution_present=bool(attribution_count),
            policy_present=policy is not None,
            policy_reviewers_met=bool(policy and len(unique_reviewers) >= policy.minimum_reviewers),
            policy_domains_met=bool(policy and required_domains.issubset(approved_domains)),
        )
        previous = edition.approved_for_retrieval
        edition.approved_for_retrieval = eligibility.eligible
        self.session.add(SourceLifecycleEvent(
            edition_id=edition.id, actor_user_id=actor.id, event_type="retrieval_eligibility_evaluated",
            from_status=str(previous).lower(), to_status=str(eligibility.eligible).lower(),
            rationale="eligible" if eligibility.eligible else "failed gates: " + ", ".join(eligibility.failed_gates()),
            created_at=datetime.now(UTC),
        ))
        await self.session.flush()
        return eligibility

    async def list_public_passages(self, edition_id: UUID) -> list[SourcePassage]:
        rows = await self.session.scalars(
            select(SourcePassage).join(SourceEdition, SourceEdition.id == SourcePassage.edition_id)
            .join(Source, Source.id == SourceEdition.source_id)
            .where(
                SourcePassage.edition_id == edition_id, SourcePassage.is_current.is_(True),
                Source.authority_status == "approved", SourceEdition.ingestion_status == "ready",
                SourceEdition.review_status == "approved", SourceEdition.approved_for_retrieval.is_(True),
            ).order_by(SourcePassage.passage_key)
        )
        return list(rows)

    async def _edition_or_404(self, edition_id: UUID) -> SourceEdition:
        edition = await self.session.get(SourceEdition, edition_id)
        if edition is None:
            raise ApplicationError("edition_not_found", "Source edition was not found.", 404)
        return edition


    async def list_public_sources(self) -> list[Source]:
        rows = await self.session.scalars(
            select(Source)
            .join(SourceEdition, SourceEdition.source_id == Source.id)
            .where(
                Source.authority_status == "approved",
                SourceEdition.review_status == "approved",
                SourceEdition.approved_for_retrieval.is_(True),
            )
            .distinct()
            .order_by(Source.canonical_title)
        )
        return list(rows)
