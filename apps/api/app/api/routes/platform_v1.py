from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.platform_v1 import *
from app.services.platform_v1 import *
router=APIRouter(prefix='/platform-v1',tags=['platform-v1'])
def _call(fn,p):
 try:return fn(**p.model_dump())
 except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
@router.post('/release/manifest')
async def manifest(p:ReleaseManifestRequest,_:Annotated[User,Depends(get_current_user)]):return {'manifest_sha256':_call(compute_release_manifest,p)}
@router.post('/integration/evaluate')
async def integration(p:CrossDomainIntegrationRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_cross_domain_integration,p)
@router.post('/security/evaluate')
async def security(p:SecurityComplianceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_security_compliance_posture,p)
@router.post('/release/candidate/evaluate')
async def candidate(p:ReleaseCandidateRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_release_candidate,p)
@router.post('/operations/observability/evaluate')
async def observability(p:ObservabilitySLORequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_observability_slo,p)
@router.post('/operations/disaster-recovery/evaluate')
async def disaster(p:DisasterRecoveryRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_disaster_recovery,p)
@router.post('/performance/evaluate')
async def performance(p:PerformanceReadinessRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_performance_readiness,p)
@router.post('/release/governance/evaluate')
async def governance(p:ReleaseGovernanceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_release_governance,p)
@router.post('/acceptance/evaluate')
async def acceptance(p:V1AcceptanceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_v1_acceptance,p)
