from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.islamic_life import *
from app.services.islamic_life import *
router=APIRouter(prefix='/islamic-life',tags=['islamic-life'])
def _call(fn,p):
 try:return fn(**p.model_dump())
 except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
@router.post('/time/profile/manifest')
async def time_manifest(p:TimeProfileManifestRequest,_:Annotated[User,Depends(get_current_user)]):return {'manifest_sha256':_call(compute_time_profile_manifest,p)}
@router.post('/time/prayer/evaluate')
async def prayer(p:PrayerTimeGovernanceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_prayer_time_governance,p)
@router.post('/time/hijri/evaluate')
async def hijri(p:HijriCalendarReleaseRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_hijri_calendar_release,p)
@router.post('/halal/standards/evaluate')
async def halal_standard(p:HalalStandardRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_halal_standard,p)
@router.post('/halal/certifications/evaluate')
async def halal_cert(p:HalalCertificationRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_halal_certification,p)
@router.post('/commerce/evaluate')
async def commerce(p:EthicalCommerceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_ethical_commerce,p)
@router.post('/finance/products/evaluate')
async def finance(p:IslamicFinanceProductRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_islamic_finance_product,p)
@router.post('/family/services/evaluate')
async def family(p:FamilyServiceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_family_service,p)
@router.post('/heritage/evaluate')
async def heritage(p:HeritageStewardshipRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_heritage_stewardship,p)
@router.post('/acceptance/evaluate')
async def acceptance(p:IslamicLifeAcceptanceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_islamic_life_acceptance,p)
