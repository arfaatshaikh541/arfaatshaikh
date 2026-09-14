from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.living_civilization import *
from app.services.living_civilization import *
router=APIRouter(prefix='/living-civilization',tags=['living-civilization'])
def _call(fn,p):
 try:return fn(**p.model_dump())
 except ValueError as e:raise HTTPException(status_code=422,detail=str(e)) from e
@router.post('/scholarly/councils/evaluate')
async def councils(p:ScholarlyCouncilRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_scholarly_council,p)
@router.post('/scholarly/decisions/evaluate')
async def decisions(p:ScholarlyDecisionRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_scholarly_decision,p)
@router.post('/provenance/lineage/hash')
async def lineage(p:ProvenanceLineageRequest,_:Annotated[User,Depends(get_current_user)]):return {'fingerprint':_call(compute_provenance_lineage,p)}
@router.post('/provenance/releases/evaluate')
async def provenance(p:ProvenanceReleaseRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_provenance_release,p)
@router.post('/research/projects/evaluate')
async def research(p:ResearchProjectRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_research_project,p)
@router.post('/education/curricula/evaluate')
async def curricula(p:CurriculumReleaseRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_curriculum_release,p)
@router.post('/education/certifications/evaluate')
async def certifications(p:CertificationAwardRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_certification_award,p)
@router.post('/community/contributions/evaluate')
async def contributions(p:CommunityContributionRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_community_contribution,p)
@router.post('/community/stewardship/evaluate')
async def stewardship(p:StewardshipTransferRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_stewardship_transfer,p)
@router.post('/analytics/releases/evaluate')
async def analytics(p:AnalyticsReleaseRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_analytics_release,p)
@router.post('/ecosystem/apis/evaluate')
async def api_ecosystem(p:APIEcosystemRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_api_ecosystem,p)
@router.post('/acceptance/evaluate')
async def acceptance(p:PlatformMaturityRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_platform_maturity,p)
