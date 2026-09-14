from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.civilization_os import *
from app.services.civilization_os import *
router=APIRouter(prefix='/civilization-os',tags=['civilization-os'])
def _call(fn,p):
 try:return fn(**p.model_dump())
 except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
@router.post('/lineage/manifest')
async def lineage_manifest(p:LineageManifestRequest,_:Annotated[User,Depends(get_current_user)]):return {'manifest_sha256':_call(compute_lineage_manifest,p)}
@router.post('/lineage/evaluate')
async def lineage(p:ScholarlyLineageRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_scholarly_lineage,p)
@router.post('/translations/evaluate')
async def translations(p:TranslationGovernanceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_translation_governance,p)
@router.post('/credentials/evaluate')
async def credentials(p:VerifiableCredentialRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_verifiable_credential,p)
@router.post('/events/evaluate')
async def events(p:CivilizationalEventRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_civilizational_event,p)
@router.post('/policies/evaluate')
async def policies(p:PolicyLifecycleRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_policy_lifecycle,p)
@router.post('/operations/intelligence/evaluate')
async def operations(p:OperationalIntelligenceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_operational_intelligence,p)
@router.post('/continuity/evaluate')
async def continuity(p:ContinuityPlanRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_continuity_plan,p)
@router.post('/acceptance/evaluate')
async def acceptance(p:ICOSAcceptanceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_icos_acceptance,p)
