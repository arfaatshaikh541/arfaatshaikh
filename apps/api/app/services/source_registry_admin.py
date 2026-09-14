from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.models.identity import User
from app.models.sources import (
    ApprovalPolicy, ClaimPassageLink, PassageCorrection, Source, SourceAuditExport,
    SourceClaim, SourceEdition, SourceLifecycleEvent, SourcePassage, SourceReview,
    SourceReviewAssignment,
)


class SourceRegistryAdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def reviewer_queue(self, reviewer: User) -> list[dict]:
        rows = await self.session.execute(
            select(SourceReviewAssignment, SourceEdition, Source)
            .join(SourceEdition, SourceEdition.id == SourceReviewAssignment.edition_id)
            .join(Source, Source.id == SourceEdition.source_id)
            .where(
                SourceReviewAssignment.reviewer_user_id == reviewer.id,
                SourceReviewAssignment.status.in_(("assigned", "in_progress")),
            )
            .order_by(SourceReviewAssignment.due_at.asc().nullslast(), SourceReviewAssignment.created_at.asc())
        )
        return [
            {
                "assignment_id": a.id,
                "edition_id": e.id,
                "source_title": s.canonical_title,
                "edition_key": e.edition_key,
                "review_domain": a.review_domain,
                "status": a.status,
                "due_at": a.due_at,
            }
            for a, e, s in rows.all()
        ]

    async def provenance_view(self, claim_id: UUID) -> dict:
        claim = await self.session.get(SourceClaim, claim_id)
        if claim is None:
            raise ApplicationError("claim_not_found", "Source claim was not found.", 404)
        rows = await self.session.execute(
            select(ClaimPassageLink, SourcePassage)
            .join(SourcePassage, SourcePassage.id == ClaimPassageLink.passage_id)
            .where(ClaimPassageLink.claim_id == claim_id)
            .order_by(ClaimPassageLink.created_at.asc())
        )
        citations = []
        for link, passage in rows.all():
            if link.citation_end > len(passage.content):
                raise ApplicationError("citation_integrity_failed", "Stored citation span no longer aligns with its immutable passage.", 500)
            citations.append({
                "link_id": link.id,
                "passage_id": passage.id,
                "relation_type": link.relation_type,
                "citation_start": link.citation_start,
                "citation_end": link.citation_end,
                "citation_text": passage.content[link.citation_start:link.citation_end],
                "citation_label": passage.citation_label,
                "source_locator": passage.source_locator,
                "rationale": link.rationale,
            })
        return {
            "claim_id": claim.id,
            "claim_text": claim.claim_text,
            "language": claim.language,
            "claim_status": claim.claim_status,
            "methodology": claim.methodology,
            "citations": citations,
        }

    async def dashboard(self) -> dict:
        source_count = await self.session.scalar(select(func.count()).select_from(Source)) or 0
        edition_count = await self.session.scalar(select(func.count()).select_from(SourceEdition)) or 0
        eligible = await self.session.scalar(select(func.count()).select_from(SourceEdition).where(SourceEdition.approved_for_retrieval.is_(True))) or 0
        pending = await self.session.scalar(select(func.count()).select_from(SourceReviewAssignment).where(SourceReviewAssignment.status.in_(("assigned", "in_progress")))) or 0
        corrections = await self.session.scalar(select(func.count()).select_from(PassageCorrection).where(PassageCorrection.status == "requested")) or 0
        return {
            "source_count": source_count,
            "edition_count": edition_count,
            "retrieval_eligible_count": eligible,
            "pending_review_count": pending,
            "open_correction_count": corrections,
        }

    async def export_audit(self, actor: User, edition_id: UUID | None, export_format: str) -> tuple[bytes, str]:
        query = select(SourceLifecycleEvent).order_by(SourceLifecycleEvent.created_at.asc())
        if edition_id is not None:
            query = query.where(SourceLifecycleEvent.edition_id == edition_id)
        events = list(await self.session.scalars(query))
        records = [{
            "id": str(e.id), "edition_id": str(e.edition_id), "actor_user_id": str(e.actor_user_id),
            "event_type": e.event_type, "from_status": e.from_status, "to_status": e.to_status,
            "rationale": e.rationale, "created_at": e.created_at.isoformat(),
        } for e in events]
        if export_format == "json":
            payload = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            media = "application/json"
        else:
            output = io.StringIO(newline="")
            writer = csv.DictWriter(output, fieldnames=["id","edition_id","actor_user_id","event_type","from_status","to_status","rationale","created_at"])
            writer.writeheader(); writer.writerows(records)
            payload = output.getvalue().encode()
            media = "text/csv"
        digest = sha256(payload).hexdigest()
        self.session.add(SourceAuditExport(
            requested_by_user_id=actor.id, edition_id=edition_id, format=export_format,
            filters_json=json.dumps({"edition_id": str(edition_id) if edition_id else None}, sort_keys=True),
            record_count=len(records), payload_sha256=digest, created_at=datetime.now(UTC),
        ))
        await self.session.flush()
        return payload, media
