from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.global_ummah_network import *
from app.services.global_ummah_network import *
router=APIRouter(prefix="/global-ummah-network",tags=["global-ummah-network"])
def _call(fn,p):
 try:return fn(**p.model_dump())
 except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
@router.post('/federation/manifest')
async def manifest(p:FederationManifestRequest,_:Annotated[User,Depends(get_current_user)]):return {'manifest_sha256':_call(compute_federation_manifest,p)}
@router.post('/federation/evaluate')
async def federation(p:InstitutionFederationRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_institution_federation,p)
@router.post('/identity/evaluate')
async def identity(p:TrustedIdentityRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_trusted_identity,p)
@router.post('/interoperability/evaluate')
async def interoperability(p:InteroperabilityProfileRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_interoperability_profile,p)
@router.post('/search/evaluate')
async def search(p:FederatedSearchRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_federated_search,p)
@router.post('/privacy/data-sharing/evaluate')
async def sharing(p:DataSharingAgreementRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_data_sharing_agreement,p)
@router.post('/scholarship/evaluate')
async def scholarship(p:CrossBorderScholarshipRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_cross_border_scholarship,p)
@router.post('/privacy/consent/evaluate')
async def consent(p:ConsentReceiptRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_consent_receipt,p)
@router.post('/resilience/evaluate')
async def resilience(p:NetworkResilienceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_network_resilience,p)
@router.post('/transparency/evaluate')
async def transparency(p:PublicTrustReportRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_public_trust_report,p)
@router.post('/audit/evaluate')
async def audit(p:FederationAuditRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_federation_audit,p)
@router.post('/acceptance/evaluate')
async def acceptance(p:GlobalUmmahAcceptanceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_global_ummah_acceptance,p)
