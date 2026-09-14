from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.civilizational_infrastructure import *
from app.services.civilizational_infrastructure import *
router=APIRouter(prefix='/civilizational-infrastructure',tags=['civilizational-infrastructure'])
def _call(fn,p):
 try:return fn(**p.model_dump())
 except ValueError as e:raise HTTPException(status_code=422,detail=str(e)) from e
@router.post('/archives/evaluate')
async def archives(p:ArchiveDepositRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_archive_deposit,p)
@router.post('/archives/manifest')
async def manifest(p:ArchiveManifestRequest,_:Annotated[User,Depends(get_current_user)]):return {'fingerprint':_call(compute_archive_manifest,p)}
@router.post('/archives/replicas/evaluate')
async def replicas(p:ReplicaSetRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_replica_set,p)
@router.post('/archives/fixity/evaluate')
async def fixity(p:FixityCheckRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_fixity_check,p)
@router.post('/search/indexes/evaluate')
async def indexes(p:SemanticIndexRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_semantic_index,p)
@router.post('/search/releases/evaluate')
async def search_release(p:SearchReleaseRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_search_release,p)
@router.post('/offline/packages/evaluate')
async def packages(p:OfflinePackageRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_offline_package,p)
@router.post('/offline/updates/evaluate')
async def updates(p:OfflineUpdateRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_offline_update,p)
@router.post('/resilience/failover/evaluate')
async def failover(p:FailoverRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_failover,p)
@router.post('/operations/observability/evaluate')
async def observability(p:ObservabilityRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_observability,p)
@router.post('/performance/capacity/evaluate')
async def capacity(p:CapacityRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_capacity,p)
@router.post('/acceptance/evaluate')
async def acceptance(p:Milestone14AcceptanceRequest,_:Annotated[User,Depends(get_current_user)]):return _call(evaluate_milestone_acceptance,p)
