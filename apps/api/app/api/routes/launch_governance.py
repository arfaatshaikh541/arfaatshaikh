from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.launch_governance import LaunchReadinessRequest, SecurityAuditEvaluationRequest, TenantLifecycleValidationRequest
from app.services.launch_governance import TenantLifecycleResult, evaluate_launch_readiness, evaluate_security_audit, validate_tenant_lifecycle

router = APIRouter(prefix="/launch-governance", tags=["launch-governance"])

@router.post("/tenant-lifecycle/validate")
async def tenant_lifecycle_validate(payload: TenantLifecycleValidationRequest, _: Annotated[User, Depends(get_current_user)]):
    return validate_tenant_lifecycle(TenantLifecycleResult(**payload.model_dump()))

@router.post("/security-audit/evaluate")
async def security_audit_evaluate(payload: SecurityAuditEvaluationRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return evaluate_security_audit(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/launch-readiness/evaluate")
async def launch_readiness_evaluate(payload: LaunchReadinessRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_launch_readiness(**payload.model_dump())
