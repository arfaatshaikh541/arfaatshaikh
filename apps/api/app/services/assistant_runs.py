"""Persist each assistant answer (hash of the question, never the raw text) with its claims and evidence so an
administrator can review exactly which sources an answer cited."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import AssistantAnswerRun, AssistantClaim, AssistantClaimEvidence
from app.models.retrieval import RetrievalChunk
from app.services.assistant import CLASSIFIER_VERSION, GROUNDING_POLICY_VERSION, AssemblyResult
from app.services.rag import Ranked
from app.services.retrieval import sha256_text


async def persist_run(db: AsyncSession, *, user_id: UUID | None, question: str, locale: str, result: AssemblyResult, ranked: list[Ranked],
                      synthesis_text: str | None, synthesis_ok: bool) -> UUID:
    run = AssistantAnswerRun(
        user_id=user_id, question_sha256=sha256_text(question), question_language=locale[:16], classification=result.classification.classification.value,
        risk_level=result.classification.risk_level, classifier_version=CLASSIFIER_VERSION, grounding_policy_version=GROUNDING_POLICY_VERSION,
        status=result.status, insufficiency_reason=result.insufficiency_reason, response_text=result.response_text,
        response_sha256=sha256_text(result.response_text) if result.response_text else None)
    db.add(run)
    await db.flush()
    label_by_chunk = {r.evidence.chunk_id: f"[{i + 1}]" for i, r in enumerate(ranked)}
    position = 0
    for claim in result.claims:
        row = AssistantClaim(answer_run_id=run.id, position=position, claim_type=claim.claim_type, text=claim.text, text_sha256=sha256_text(claim.text), status="verified")
        db.add(row)
        await db.flush()
        for label in claim.citations:
            r = next((x for x in ranked if label_by_chunk[x.evidence.chunk_id] == label), None)
            if r is not None and await db.get(RetrievalChunk, UUID(r.evidence.chunk_id)) is not None:
                db.add(AssistantClaimEvidence(claim_id=row.id, chunk_id=UUID(r.evidence.chunk_id), support_type="quotes", citation_label=label, evidence_text_sha256=r.evidence.text_sha256))
        position += 1
    if synthesis_text:
        db.add(AssistantClaim(answer_run_id=run.id, position=position, claim_type="general_explanation", text=synthesis_text, text_sha256=sha256_text(synthesis_text),
                              status="verified" if synthesis_ok else "rejected", rejection_reason=None if synthesis_ok else "citation_validation_failed"))
    return run.id


async def recent_runs(db: AsyncSession, limit: int = 50) -> list[dict]:
    runs = (await db.scalars(select(AssistantAnswerRun).order_by(AssistantAnswerRun.created_at.desc()).limit(limit))).all()
    out = []
    for run in runs:
        claims = (await db.scalars(select(AssistantClaim).where(AssistantClaim.answer_run_id == run.id).order_by(AssistantClaim.position))).all()
        items = []
        for claim in claims:
            ev = (await db.scalars(select(AssistantClaimEvidence).where(AssistantClaimEvidence.claim_id == claim.id))).all()
            items.append({"position": claim.position, "type": claim.claim_type, "status": claim.status, "text": claim.text[:400], "rejection_reason": claim.rejection_reason,
                          "citations": [{"label": e.citation_label, "chunk_id": str(e.chunk_id), "sha256": e.evidence_text_sha256} for e in ev]})
        out.append({"id": str(run.id), "created_at": run.created_at.isoformat(), "classification": run.classification, "risk_level": run.risk_level, "status": run.status,
                    "insufficiency_reason": run.insufficiency_reason, "claims": items})
    return out
