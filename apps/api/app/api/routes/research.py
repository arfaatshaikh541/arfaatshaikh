from typing import Annotated
from fastapi import APIRouter, Depends
from app.api.dependencies.auth import get_current_user, require_csrf
from app.models.identity import User
from app.schemas.research import PermissionCheckRequest, ResearchItemValidationRequest, AnnotationValidationRequest, CitationRenderRequest
from app.services.research import require_workspace_role, validate_research_item, validate_annotation, canonical_citation_key, render_woi_citation
router=APIRouter(prefix='/research',tags=['research'])
CurrentUser=Annotated[User,Depends(get_current_user)]
@router.post('/permissions/check',dependencies=[Depends(require_csrf)])
async def permissions(body:PermissionCheckRequest,user:CurrentUser): require_workspace_role(body.actual_role,body.required_role); return {'allowed':True}
@router.post('/items/validate',dependencies=[Depends(require_csrf)])
async def items(body:ResearchItemValidationRequest,user:CurrentUser): validate_research_item(**body.model_dump()); return {'valid':True}
@router.post('/annotations/validate',dependencies=[Depends(require_csrf)])
async def annotations(body:AnnotationValidationRequest,user:CurrentUser): validate_annotation(**body.model_dump()); return {'valid':True,'eligible_as_evidence':False}
@router.post('/citations/render',dependencies=[Depends(require_csrf)])
async def citations(body:CitationRenderRequest,user:CurrentUser):
    return {'citation_key':canonical_citation_key(body.title,body.sequence),'rendered_text':render_woi_citation(title=body.title,source_label=body.source_label,locator=body.locator,canonical_url=body.canonical_url)}
