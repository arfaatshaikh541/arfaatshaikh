from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.personalization_ai import AccessibilityRequest, RecommendationRequest
from app.services.personalization_ai import PERSONALIZATION_POLICY_VERSION, RecommendationInput, evaluate_recommendation, validate_accessibility_profile

router = APIRouter(prefix="/personalization-ai", tags=["personalization-ai"])

@router.post("/recommendations/evaluate")
async def evaluate(payload: RecommendationRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        result = evaluate_recommendation(RecommendationInput(**payload.model_dump(exclude={"signal_types", "inferred_attributes"}), signal_types=tuple(payload.signal_types), inferred_attributes=tuple(payload.inferred_attributes)))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"decision": result.decision, "score": result.score, "reason_codes": result.reason_codes, "explanation": result.explanation, "policy_version": PERSONALIZATION_POLICY_VERSION}

@router.post("/accessibility/validate")
async def validate_accessibility(payload: AccessibilityRequest, _: Annotated[User, Depends(get_current_user)]):
    return validate_accessibility_profile(**payload.model_dump())
