from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.institutional_network import *
from app.services.institutional_network import *

router = APIRouter(prefix="/institutional-network", tags=["institutional-network"])

def _call(fn, payload):
    try: return fn(**payload.model_dump())
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/institutions/evaluate")
async def institutions(payload: InstitutionRegistrationRequest, _: Annotated[User, Depends(get_current_user)]): return _call(evaluate_institution_registration, payload)
@router.post("/accreditations/evaluate")
async def accreditations(payload: AccreditationRequest, _: Annotated[User, Depends(get_current_user)]): return _call(evaluate_accreditation, payload)
@router.post("/portals/evaluate")
async def portals(payload: PortalPublicationRequest, _: Annotated[User, Depends(get_current_user)]): return _call(evaluate_portal_publication, payload)
@router.post("/residency/evaluate")
async def residency(payload: DataResidencyRequest, _: Annotated[User, Depends(get_current_user)]): return _call(evaluate_data_residency, payload)
@router.post("/localization/evaluate")
async def localization(payload: LocalizationReleaseRequest, _: Annotated[User, Depends(get_current_user)]): return _call(evaluate_localization_release, payload)
@router.post("/transparency/evaluate")
async def transparency(payload: PublicTransparencyRequest, _: Annotated[User, Depends(get_current_user)]): return _call(evaluate_public_transparency, payload)
@router.post("/corrections/evaluate")
async def corrections(payload: CorrectionReleaseRequest, _: Annotated[User, Depends(get_current_user)]): return _call(evaluate_correction_release, payload)
@router.post("/transparency/fingerprint")
async def fingerprint(payload: TransparencyFingerprintRequest, _: Annotated[User, Depends(get_current_user)]): return {"fingerprint": _call(compute_transparency_fingerprint, payload)}
@router.post("/rollouts/evaluate")
async def rollouts(payload: RegionalRolloutRequest, _: Annotated[User, Depends(get_current_user)]): return _call(evaluate_regional_rollout, payload)
@router.post("/acceptance/evaluate")
async def acceptance(payload: GlobalAcceptanceRequest, _: Annotated[User, Depends(get_current_user)]): return _call(evaluate_global_acceptance, payload)
