from typing import Annotated
from fastapi import APIRouter, Depends
from app.api.dependencies.auth import get_current_user, require_csrf
from app.models.identity import User
from app.schemas.scholarly import ScholarProfileValidationRequest,ReviewAssignmentRequest,ReviewValidationRequest,PublicationDecisionRequest,VersionCompareRequest
from app.services.scholarly import validate_scholar_profile,validate_review_assignment,validate_review,publication_decision,compare_versions
router=APIRouter(prefix='/scholarly',tags=['scholarly-collaboration'])
CurrentUser=Annotated[User,Depends(get_current_user)]
@router.post('/profiles/validate',dependencies=[Depends(require_csrf)])
async def profiles(body:ScholarProfileValidationRequest,user:CurrentUser): return validate_scholar_profile(**body.model_dump())
@router.post('/reviews/assign/validate',dependencies=[Depends(require_csrf)])
async def assignments(body:ReviewAssignmentRequest,user:CurrentUser): validate_review_assignment(**body.model_dump()); return {'valid':True}
@router.post('/reviews/validate',dependencies=[Depends(require_csrf)])
async def reviews(body:ReviewValidationRequest,user:CurrentUser): validate_review(**body.model_dump()); return {'valid':True}
@router.post('/publication/evaluate',dependencies=[Depends(require_csrf)])
async def publication(body:PublicationDecisionRequest,user:CurrentUser): return publication_decision(**body.model_dump())
@router.post('/versions/compare',dependencies=[Depends(require_csrf)])
async def versions(body:VersionCompareRequest,user:CurrentUser): return compare_versions(**body.model_dump())
