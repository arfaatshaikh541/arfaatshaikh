from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.ai_quality import EvaluationRequest, RedTeamFindingRequest, ReleaseGateRequest
from app.services.ai_quality import EvaluationObservation, evaluate_observation, evaluate_release_gate, validate_red_team_finding

router = APIRouter(prefix="/ai-quality", tags=["ai-quality"])

@router.post("/evaluations/evaluate")
async def evaluate(payload: EvaluationRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        result = evaluate_observation(EvaluationObservation(
            expected_action=payload.expected_action, observed_action=payload.observed_action,
            response_text=payload.response_text, evidence_fingerprints=tuple(payload.evidence_fingerprints),
            required_evidence_fingerprints=tuple(payload.required_evidence_fingerprints),
            forbidden_patterns=tuple(payload.forbidden_patterns), risk_level=payload.risk_level,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.__dict__

@router.post("/red-team/validate")
async def validate_finding(payload: RedTeamFindingRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return validate_red_team_finding(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/release-gate/evaluate")
async def release_gate(payload: ReleaseGateRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_release_gate(**payload.model_dump())
