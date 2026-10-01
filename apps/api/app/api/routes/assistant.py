from __future__ import annotations

from typing import Annotated, Any, Sequence
from fastapi import APIRouter, Depends

from app.api.dependencies.auth import DbSession, get_current_user, require_csrf
from app.models.identity import Session, User
from app.schemas.assistant import AssembleAnswerRequest, AssistantQueryRequest, QuestionClassificationRequest
from app.services.assistant import AssemblyResult, ClaimDraft, ClassificationResult, assemble_grounded_answer, classify_question
from app.api.dependencies.platform_admin import require_platform_administrator
from app.core.config import get_settings
from app.services.ai_provider import get_ai_provider
from app.services.assistant_runs import persist_run, recent_runs
from app.services.knowledge_retrieval import authority_summary, hits_view, search_knowledge
from app.services.rag import INSUFFICIENT, assess_confidence, build_sections, build_synthesis_prompt, detect_scholarly_views, rank_evidence, validate_synthesis
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
async def query(payload: AssistantQueryRequest, db: DbSession, user: Annotated[User, Depends(get_current_user)], _: Annotated[Session, Depends(require_csrf)]):
    """Evidence-grounded answer: classify, retrieve verified evidence, rank, assess confidence, abstain if weak, assemble.

    The core answer is verbatim quotation of retrieved evidence (claim_type="direct_quote"), so the assembler's own
    verbatim check guarantees nothing is paraphrased. Sections keep primary sources, scholarly explanation and secondary
    sources apart. An optional AI synthesis (include_synthesis) is shown only if every sentence passes citation
    validation; otherwise it is discarded and reported as rejected.
    """
    classification = classify_question(payload.question)
    if not classification.required_corpora:
        safety = evaluate_safety(payload.question, classification.classification.value, [])
        return _with_pipeline(_assembled_response(assemble_grounded_answer(payload.question, [], []), safety, []), None, None, [])
    candidates = await search_evidence(db, classification.required_corpora, payload.question, payload.limit * 6)
    ranked = rank_evidence(payload.question, candidates, payload.limit)
    evidence = [r.evidence for r in ranked]
    safety = evaluate_safety(payload.question, classification.classification.value, [item.exact_text for item in evidence])
    if safety.action.value == "refuse":
        return _refused_response(classification, safety)
    confidence = assess_confidence(payload.question, ranked)
    if confidence.abstain:
        result = AssemblyResult("insufficient", classification, None, (), "insufficient_verified_sources:" + ",".join(confidence.reasons))
        evidence, ranked_for_view = [], []
    else:
        claims = [ClaimDraft("direct_quote", item.exact_text, (index,)) for index, item in enumerate(evidence)]
        result = assemble_grounded_answer(payload.question, evidence, claims)
        ranked_for_view = ranked
    synthesis: dict[str, Any] = {"status": "not_requested", "text": None, "label": "AI SYNTHESIS", "notice": "Generated by a language model from the cited sources above. It is not itself a source."}
    synthesis_text, synthesis_ok = None, False
    if payload.include_synthesis and result.status == "assembled":
        provider = get_ai_provider(get_settings())
        generated = await provider.generate(build_synthesis_prompt(payload.question, ranked))
        if not generated.available or not generated.text:
            synthesis["status"] = "unavailable"
        else:
            check = validate_synthesis(generated.text, ranked)
            synthesis_text, synthesis_ok = generated.text.strip(), check.ok
            if check.ok and generated.text.strip() != INSUFFICIENT:
                synthesis.update(status="validated", text=generated.text.strip())
            else:
                synthesis.update(status="rejected", reasons=check.reasons[:5] if not check.ok else ["model_reported_insufficient"])
    try:
        run_id = await persist_run(db, user_id=user.id, question=payload.question, locale=payload.locale, result=result, ranked=ranked_for_view,
                                   synthesis_text=synthesis_text, synthesis_ok=synthesis_ok)
        await db.commit()
    except Exception:  # an audit-store failure must not hide a correct, source-backed answer
        await db.rollback()
        run_id = None
    response = _with_pipeline(_assembled_response(result, safety, evidence), confidence, synthesis, detect_scholarly_views(ranked_for_view))
    response["sections"] = build_sections(ranked_for_view)
    response["knowledge_sources"] = hits_view(await search_knowledge(db, payload.question))
    response["authority_summary"] = authority_summary(response["sections"], response["knowledge_sources"])
    response["answer_run_id"] = str(run_id) if run_id else None
    return response


def _with_pipeline(response: dict, confidence, synthesis, views: list[dict]) -> dict:
    response["confidence"] = ({"score": confidence.score, "level": confidence.level, "abstained": confidence.abstain, "reasons": list(confidence.reasons)}
                              if confidence else {"score": 0.0, "level": "none", "abstained": True, "reasons": ["no_supported_scope"]})
    response["ai_synthesis"] = synthesis or {"status": "not_requested", "text": None, "label": "AI SYNTHESIS"}
    response["scholarly_views"] = views
    response.setdefault("knowledge_sources", [])
    response.setdefault("authority_summary", {"unavailable": 1})
    response["sections"] = response.get("sections", {"primary_source": [], "scholarly_explanation": [], "secondary_source": []})
    if response["status"] == "insufficient":
        response["message"] = INSUFFICIENT
    return response


@router.get("/admin/runs")
async def admin_runs(db: DbSession, _: Annotated[User, Depends(require_platform_administrator)], limit: int = 50):
    """Review which sources each answer cited (the question text itself is never stored, only its hash)."""
    return {"runs": await recent_runs(db, max(1, min(limit, 200)))}
