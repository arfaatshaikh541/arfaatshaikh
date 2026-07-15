from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import (
    TenantContext,
    get_tenant_db,
    require_csrf,
    require_permission,
    require_tenant_write,
)
from modules.audit import service as audit_service
from modules.credential_vault import service as vault_service
from modules.credential_vault.schemas import (
    CredentialCreateRequest,
    CredentialRead,
    CredentialRotateRequest,
)

router = APIRouter(prefix="/api/integrations/credentials", tags=["credential_vault"])


@router.get("", response_model=list[CredentialRead])
async def list_credentials(
    ctx: TenantContext = Depends(require_permission("integrations.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[CredentialRead]:
    credentials = await vault_service.list_credentials(db, tenant_id=ctx.tenant_id)
    return [CredentialRead.model_validate(c) for c in credentials]


@router.post("", response_model=CredentialRead, dependencies=[Depends(require_csrf)])
async def create_credential(
    payload: CredentialCreateRequest,
    ctx: TenantContext = Depends(require_permission("integrations.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> CredentialRead:
    require_tenant_write(ctx)
    credential = await vault_service.store_credential(
        db,
        tenant_id=ctx.tenant_id,
        provider_key=payload.provider_key,
        label=payload.label,
        secret_plaintext=payload.secret,
        created_by_user_id=ctx.user.id,
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="credential_vault.credential_created",
        target_type="integration_credential",
        target_id=str(credential.id),
        context={"provider_key": payload.provider_key, "label": payload.label},
    )
    await db.commit()
    return CredentialRead.model_validate(credential)


@router.post(
    "/{credential_id}/rotate", response_model=CredentialRead, dependencies=[Depends(require_csrf)]
)
async def rotate_credential(
    credential_id: uuid.UUID,
    payload: CredentialRotateRequest,
    ctx: TenantContext = Depends(require_permission("integrations.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> CredentialRead:
    require_tenant_write(ctx)
    credential = await vault_service.rotate_credential(
        db, credential_id=credential_id, tenant_id=ctx.tenant_id, new_secret_plaintext=payload.secret
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="credential_vault.credential_rotated",
        target_type="integration_credential",
        target_id=str(credential.id),
    )
    await db.commit()
    return CredentialRead.model_validate(credential)


@router.post(
    "/{credential_id}/revoke", response_model=CredentialRead, dependencies=[Depends(require_csrf)]
)
async def revoke_credential(
    credential_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("integrations.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> CredentialRead:
    require_tenant_write(ctx)
    credential = await vault_service.revoke_credential(
        db, credential_id=credential_id, tenant_id=ctx.tenant_id
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="credential_vault.credential_revoked",
        target_type="integration_credential",
        target_id=str(credential.id),
    )
    await db.commit()
    return CredentialRead.model_validate(credential)
