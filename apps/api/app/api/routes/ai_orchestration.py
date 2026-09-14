from typing import Annotated
from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.ai_orchestration import OrchestrationEvaluateRequest
from app.services.ai_orchestration import (
    CitationEvidence, ClaimCandidate, GROUNDING_POLICY_VERSION,
    ORCHESTRATION_POLICY_VERSION, orchestrate_claims,
)

router = APIRouter(prefix="/ai-orchestration", tags=["ai-orchestration"])

@router.post("/evaluate")
async def evaluate(payload: OrchestrationEvaluateRequest, _: Annotated[User, Depends(get_current_user)]):
    evidence = [CitationEvidence(**item.model_dump()) for item in payload.evidence]
    claims = [ClaimCandidate(item.claim_type, item.text, tuple(item.evidence_indices)) for item in payload.claims]
    result = orchestrate_claims(claims, evidence, risk_level=payload.risk_level)
    return {
        "status": result.status,
        "requires_scholar": result.requires_scholar,
        "terminal_reason": result.terminal_reason,
        "orchestration_policy_version": ORCHESTRATION_POLICY_VERSION,
        "grounding_policy_version": GROUNDING_POLICY_VERSION,
        "claims": [
            {"position": c.position, "decision": c.decision, "reason_code": c.reason_code, "citation_labels": list(c.citation_labels)}
            for c in result.claims
        ],
    }
