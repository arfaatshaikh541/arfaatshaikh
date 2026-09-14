from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.ummah_services import *
from app.services.ummah_services import *
router=APIRouter(prefix='/ummah-services',tags=['ummah-services'])
def _call(fn,p):
 try:return fn(**p.model_dump())
 except ValueError as e:raise HTTPException(status_code=422,detail=str(e)) from e
@router.post('/zakat/funds/evaluate')
async def zakat_fund(p:ZakatFundRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_zakat_fund,p)
@router.post('/zakat/distributions/evaluate')
async def zakat_distribution(p:ZakatDistributionRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_zakat_distribution,p)
@router.post('/waqf/assets/evaluate')
async def waqf_asset(p:WaqfAssetRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_waqf_asset,p)
@router.post('/humanitarian/cases/fingerprint')
async def aid_fingerprint(p:AidCaseFingerprintRequest,_:Annotated[User,Depends(get_current_user)]):return {'fingerprint':_call(compute_aid_case_fingerprint,p)}
@router.post('/humanitarian/cases/evaluate')
async def beneficiary_case(p:BeneficiaryCaseRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_beneficiary_case,p)
@router.post('/humanitarian/programmes/evaluate')
async def aid_program(p:AidProgramRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_aid_program,p)
@router.post('/mosques/services/evaluate')
async def mosque_service(p:MosqueServiceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_mosque_service,p)
@router.post('/volunteers/assignments/evaluate')
async def volunteer(p:VolunteerAssignmentRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_volunteer_assignment,p)
@router.post('/services/referrals/evaluate')
async def referral(p:ServiceReferralRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_service_referral,p)
@router.post('/crisis/responses/evaluate')
async def crisis(p:CrisisResponseRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_crisis_response,p)
@router.post('/analytics/releases/evaluate')
async def analytics(p:PublicServiceAnalyticsRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_public_service_analytics,p)
@router.post('/acceptance/evaluate')
async def acceptance(p:UmmahServicesAcceptanceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_ummah_services_acceptance,p)
