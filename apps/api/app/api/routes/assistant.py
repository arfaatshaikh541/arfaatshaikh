from __future__ import annotations

from typing import Annotated, Sequence
from fastapi import APIRouter, Depends

from app.api.dependencies.auth import DbSession, get_current_user
from app.models.identity import User
from app.schemas.assistant import AssembleAnswerRequest, AssistantQueryRequest, QuestionClassificationRequest
from app.services.assistant import AssemblyResult, ClaimDraft, ClassificationResult, assemble_grounded_answer, classify_question
from app.services.retrieval import EvidenceContract, search_evidence
from app.services.assistant_safety import SAFETY_POLICY_VERSION, SafetyDecision, evaluate_safety

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _refused_response(classification: ClassificationResult, safety: SafetyDecision) -> dict:
    return {
        "status": "insufficient",
        "classification": classification.classification.value,
        "risk_level": classification.risk_level,
        "requires_escalation": safety.requires_human_scholar,
        "safety_policy_version": SAFETY_POLICY_VERSION,
        "safety_action": safety.action.value,
        "response_text": None,
        "insufficiency_reason": safety.reasons[-1] if safety.reasons else "safety_policy_refusal",
        "claims": [],
        "evidence": [],
    }


def _assembled_response(result: AssemblyResult, safety: SafetyDecision, evidence: Sequence[EvidenceContract]) -> dict:
    return {
        "status": result.status,
        "classification": result.classification.classification.value,
        "risk_level": result.classification.risk_level,
        "requires_escalation": result.classification.requires_escalation,
        "grounding_policy_version": "claim-grounding-v1",
        "safety_policy_version": SAFETY_POLICY_VERSION,
        "safety_action": safety.action.value,
        "response_text": result.response_text,
        "insufficiency_reason": result.insufficiency_reason,
        "claims": [
            {"position": item.position, "claim_type": item.claim_type, "text": item.text, "citations": list(item.citations)}
            for item in result.claims
        ],
        "evidence": [
            {"label": f"[{index + 1}]", "canonical_reference": item.canonical_reference, "attribution": item.attribution,
             "source_edition_id": item.source_edition_id, "source_passage_id": item.source_passage_id,
             "exact_text": item.exact_text, "text_sha256": item.text_sha256}
            for index, item in enumerate(evidence)
        ] if result.status == "assembled" else [],
    }


@router.post("/classify")
async def classify(payload: QuestionClassificationRequest, _: Annotated[User, Depends(get_current_user)]):
    result = classify_question(payload.question)
    return {
        "classification": result.classification.value,
        "risk_level": result.risk_level,
        "required_corpora": list(result.required_corpora),
        "requires_escalation": result.requires_escalation,
        "classifier_version": "question-classifier-v1",
    }


@router.post("/assemble")
async def assemble(payload: AssembleAnswerRequest, _: Annotated[User, Depends(get_current_user)]):
    evidence = [EvidenceContract(**item.model_dump()) for item in payload.evidence]
    claims = [ClaimDraft(item.claim_type, item.text, tuple(item.evidence_indices)) for item in payload.claims]
    classification = classify_question(payload.question)
    safety = evaluate_safety(payload.question, classification.classification.value, [item.exact_text for item in evidence])
    if safety.action.value == "refuse":
        return _refused_response(classification, safety)
    result = assemble_grounded_answer(payload.question, evidence, claims)
    return _assembled_response(result, safety, evidence)


@router.post("/query")
async def query(payload: AssistantQueryRequest, db: DbSession, _: Annotated[User, Depends(get_current_user)]):
    """End-to-end evidence-grounded answer: classify, retrieve approved evidence, then assemble.

    Every claim is a verbatim quotation of retrieved evidence (claim_type="direct_quote"),
    so the assembler's own verbatim-match check is the guarantee that nothing here is
    generated or paraphrased beyond what an approved, published source actually says.
    """
    classification = classify_question(payload.question)
    if not classification.required_corpora:
        safety = evaluate_safety(payload.question, classification.classification.value, [])
        return _assembled_response(assemble_grounded_answer(payload.question, [], []), safety, [])
    evidence = await search_evidence(db, classification.required_corpora, payload.question, payload.limit)
    safety = evaluate_safety(payload.question, classification.classification.value, [item.exact_text for item in evidence])
    if safety.action.value == "refuse":
        return _refused_response(classification, safety)
    claims = [ClaimDraft("direct_quote", item.exact_text, (index,)) for index, item in enumerate(evidence)]
    result = assemble_grounded_answer(payload.question, evidence, claims)
    return _assembled_response(result, safety, evidence)
