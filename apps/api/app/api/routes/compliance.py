from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.compliance import ControlEvaluationRequest, DisasterRecoveryRequest, EnterpriseReadinessRequest, EvidenceValidationRequest, RiskEvaluationRequest
from app.services.compliance import EvidenceInput, evaluate_control, evaluate_disaster_recovery, evaluate_enterprise_readiness, evaluate_risk, validate_evidence

router = APIRouter(prefix="/compliance", tags=["compliance"])

@router.post("/evidence/validate")
async def evidence_validate(payload: EvidenceValidationRequest, _: Annotated[User, Depends(get_current_user)]):
    return validate_evidence(EvidenceInput(**payload.model_dump()))

@router.post("/controls/evaluate")
async def control_evaluate(payload: ControlEvaluationRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_control(**payload.model_dump())

@router.post("/risks/evaluate")
async def risk_evaluate(payload: RiskEvaluationRequest, _: Annotated[User, Depends(get_current_user)]):
    try: return evaluate_risk(**payload.model_dump())
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/disaster-recovery/evaluate")
async def dr_evaluate(payload: DisasterRecoveryRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_disaster_recovery(**payload.model_dump())

@router.post("/enterprise-readiness/evaluate")
async def readiness_evaluate(payload: EnterpriseReadinessRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_enterprise_readiness(**payload.model_dump())
