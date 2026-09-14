from fastapi import APIRouter, Depends
from app.api.dependencies.auth import get_current_user
from app.schemas.knowledge_network import RelationshipInput, SearchRequest, TraversalRequest
from app.services.knowledge_network import GraphEdge, KnowledgeNetworkPolicy

router = APIRouter(prefix='/knowledge-network', tags=['knowledge-network'], dependencies=[Depends(get_current_user)])

@router.post('/relationships/validate')
async def validate_relationship(payload: RelationshipInput, source_published: bool = True, target_published: bool = True, evidence_current_and_approved: bool = True):
    return KnowledgeNetworkPolicy.validate_relationship(payload, source_published=source_published, target_published=target_published, evidence_current_and_approved=evidence_current_and_approved)

@router.post('/search/plan')
async def search_plan(payload: SearchRequest):
    return KnowledgeNetworkPolicy.build_search_plan(payload)

@router.post('/traversal/validate')
async def traversal_contract(payload: TraversalRequest):
    return {'allowed': True, 'max_depth': payload.max_depth, 'max_nodes': payload.max_nodes, 'evidence_only': True}
