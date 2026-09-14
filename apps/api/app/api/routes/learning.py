from typing import Annotated
from fastapi import APIRouter, Depends
from app.api.dependencies.auth import get_current_user, require_csrf
from app.models.identity import User
from app.schemas.learning import TransitionRequest, PublicationValidationRequest, ScoreRequest, RecommendationRequest, ChildDefaultsRequest
from app.services.learning import transition_content, validate_publication, calculate_score, deterministic_recommendations, validate_child_defaults
router=APIRouter(prefix='/learning',tags=['learning'])
CurrentUser=Annotated[User,Depends(get_current_user)]
@router.post('/governance/transition',dependencies=[Depends(require_csrf)])
async def transition(body:TransitionRequest,user:CurrentUser): return {'status':transition_content(body.current,body.target)}
@router.post('/governance/validate-publication',dependencies=[Depends(require_csrf)])
async def validate_publish(body:PublicationValidationRequest,user:CurrentUser):
    validate_publication(evidence_ids=body.evidence_ids,reviews=body.reviews,author_id=body.author_id,reviewer_ids=body.reviewer_ids); return {'publishable':True}
@router.post('/assessments/calculate-score',dependencies=[Depends(require_csrf)])
async def score(body:ScoreRequest,user:CurrentUser): return {'score':calculate_score(body.earned,body.possible)}
@router.post('/recommendations',dependencies=[Depends(require_csrf)])
async def recommendations(body:RecommendationRequest,user:CurrentUser): return {'items':deterministic_recommendations([x.model_dump() for x in body.candidates],body.preferred_language,set(body.completed_course_ids))}
@router.post('/children/validate-defaults',dependencies=[Depends(require_csrf)])
async def child_defaults(body:ChildDefaultsRequest,user:CurrentUser): validate_child_defaults(**body.model_dump()); return {'safe':True}
