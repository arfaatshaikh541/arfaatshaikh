from typing import Annotated
from fastapi import APIRouter, Depends
from app.api.dependencies.auth import get_current_user, require_csrf
from app.models.identity import User
from app.schemas.community import DiscussionValidationRequest, ReportValidationRequest, ModerationDecisionRequest, ReputationRequest
from app.services.community import validate_discussion_content, validate_report, validate_moderation_decision, reputation_points
router=APIRouter(prefix='/community',tags=['community'])
CurrentUser=Annotated[User,Depends(get_current_user)]
@router.post('/discussions/validate',dependencies=[Depends(require_csrf)])
async def discussions(body:DiscussionValidationRequest,user:CurrentUser): return validate_discussion_content(**body.model_dump())
@router.post('/reports/validate',dependencies=[Depends(require_csrf)])
async def reports(body:ReportValidationRequest,user:CurrentUser): return {'valid':True,'risk_score':validate_report(**body.model_dump())}
@router.post('/moderation/validate',dependencies=[Depends(require_csrf)])
async def moderation(body:ModerationDecisionRequest,user:CurrentUser): validate_moderation_decision(**body.model_dump()); return {'valid':True}
@router.post('/reputation/score',dependencies=[Depends(require_csrf)])
async def reputation(body:ReputationRequest,user:CurrentUser): return {'points':reputation_points(**body.model_dump()),'grants_religious_authority':False}
