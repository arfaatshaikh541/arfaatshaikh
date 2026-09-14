from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.multilingual_ai import ClaimIdentityRequest, TranslationAlignmentRequest
from app.services.multilingual_ai import LANGUAGE_POLICY_VERSION, TranslationAlignment, require_claim_count_alignment, validate_alignment

router = APIRouter(prefix="/multilingual-ai", tags=["multilingual-ai"])

@router.post("/align")
async def align(payload: TranslationAlignmentRequest, _: Annotated[User, Depends(get_current_user)]):
    result = validate_alignment(TranslationAlignment(**payload.model_dump()))
    return {"decision": result.decision, "reason_code": result.reason_code, "requires_human_review": result.requires_human_review, "policy_version": LANGUAGE_POLICY_VERSION}

@router.post("/claims/validate")
async def validate_claims(payload: ClaimIdentityRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        require_claim_count_alignment(tuple(payload.source_claim_ids), tuple(payload.target_claim_ids))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"valid": True, "policy_version": LANGUAGE_POLICY_VERSION}
