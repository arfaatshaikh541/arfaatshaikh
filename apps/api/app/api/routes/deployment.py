from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.deployment import DeploymentConfigRequest, ReleaseReadinessRequest
from app.services.deployment import DeploymentConfig, evaluate_release_readiness, validate_deployment_config

router = APIRouter(prefix="/deployment", tags=["deployment"])

@router.post("/config/validate")
async def validate_config(payload: DeploymentConfigRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        config = DeploymentConfig(
            environment=payload.environment,
            public_base_url=str(payload.public_base_url),
            allowed_origins=tuple(str(item) for item in payload.allowed_origins),
            cookie_secure=payload.cookie_secure,
            secret_key_length=payload.secret_key_length,
            image_digest=payload.image_digest,
            migration_revision=payload.migration_revision,
            secrets_provider=payload.secrets_provider,
        )
        return validate_deployment_config(config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/release/readiness")
async def release_readiness(payload: ReleaseReadinessRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return evaluate_release_readiness(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
