from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.operations import AlertRuleRequest, IncidentReadinessRequest, ResilienceGateRequest
from app.services.operations import AlertRuleInput, evaluate_incident_readiness, evaluate_resilience_gate, validate_alert_rule

router = APIRouter(prefix="/operations", tags=["operations"])

@router.post("/alerts/validate")
async def alert_validate(payload: AlertRuleRequest, _: Annotated[User, Depends(get_current_user)]):
    return validate_alert_rule(AlertRuleInput(**payload.model_dump()))

@router.post("/incidents/readiness")
async def incident_readiness(payload: IncidentReadinessRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return evaluate_incident_readiness(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/resilience/evaluate")
async def resilience_evaluate(payload: ResilienceGateRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_resilience_gate(**payload.model_dump())
