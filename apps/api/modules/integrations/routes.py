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
from core.task_queue import enqueue_integration_sync
from modules.audit import service as audit_service
from modules.integrations import service as integrations_service
from modules.integrations.schemas import (
    CatalogEntryRead,
    IntegrationHealthRead,
    SyncRunRead,
    TenantIntegrationCreateRequest,
    TenantIntegrationRead,
    TriggerSyncResponse,
)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("/catalog", response_model=list[CatalogEntryRead])
async def get_catalog(
    ctx: TenantContext = Depends(require_permission("integrations.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[CatalogEntryRead]:
    entries = await integrations_service.list_catalog(db)
    return [CatalogEntryRead.model_validate(e) for e in entries]


@router.get("", response_model=list[TenantIntegrationRead])
async def list_integrations(
    ctx: TenantContext = Depends(require_permission("integrations.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[TenantIntegrationRead]:
    integrations = await integrations_service.list_tenant_integrations(db, tenant_id=ctx.tenant_id)
    return [integrations_service.to_tenant_integration_read(ti) for ti in integrations]


@router.post("", response_model=TenantIntegrationRead, dependencies=[Depends(require_csrf)])
async def connect_integration(
    payload: TenantIntegrationCreateRequest,
    ctx: TenantContext = Depends(require_permission("integrations.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> TenantIntegrationRead:
    require_tenant_write(ctx)
    tenant_integration = await integrations_service.connect_integration(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        provider_id=payload.provider_id,
        label=payload.label,
        secret_plaintext=payload.secret,
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="integrations.connected",
        target_type="tenant_integration",
        target_id=str(tenant_integration.id),
        context={"provider_id": payload.provider_id, "label": payload.label},
    )
    response = integrations_service.to_tenant_integration_read(tenant_integration)
    await db.commit()
    return response


@router.post(
    "/{tenant_integration_id}/disconnect",
    response_model=TenantIntegrationRead,
    dependencies=[Depends(require_csrf)],
)
async def disconnect_integration(
    tenant_integration_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("integrations.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> TenantIntegrationRead:
    require_tenant_write(ctx)
    tenant_integration = await integrations_service.disconnect_integration(
        db, tenant_id=ctx.tenant_id, tenant_integration_id=tenant_integration_id
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="integrations.disconnected",
        target_type="tenant_integration",
        target_id=str(tenant_integration.id),
    )
    response = integrations_service.to_tenant_integration_read(tenant_integration)
    await db.commit()
    return response


@router.get("/{tenant_integration_id}/health", response_model=list[IntegrationHealthRead])
async def get_health_history(
    tenant_integration_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("integrations.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[IntegrationHealthRead]:
    history = await integrations_service.list_health_history(
        db, tenant_id=ctx.tenant_id, tenant_integration_id=tenant_integration_id
    )
    return [IntegrationHealthRead.model_validate(h) for h in history]


@router.get("/{tenant_integration_id}/sync-runs", response_model=list[SyncRunRead])
async def get_sync_runs(
    tenant_integration_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("integrations.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[SyncRunRead]:
    runs = await integrations_service.list_sync_runs(
        db, tenant_id=ctx.tenant_id, tenant_integration_id=tenant_integration_id
    )
    return [SyncRunRead.model_validate(r) for r in runs]


@router.post(
    "/{tenant_integration_id}/sync",
    response_model=TriggerSyncResponse,
    dependencies=[Depends(require_csrf)],
)
async def trigger_sync(
    tenant_integration_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("integrations.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> TriggerSyncResponse:
    require_tenant_write(ctx)
    # Confirms the integration exists and is connected before enqueuing —
    # fail fast in the request/response cycle rather than in the worker.
    tenant_integration = await integrations_service.get_tenant_integration_or_404(
        db, tenant_id=ctx.tenant_id, tenant_integration_id=tenant_integration_id
    )
    sync_run = await integrations_service.create_sync_run(
        db, tenant_id=ctx.tenant_id, tenant_integration_id=tenant_integration.id
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="integrations.sync_triggered",
        target_type="tenant_integration",
        target_id=str(tenant_integration.id),
        context={"sync_run_id": str(sync_run.id)},
    )
    await db.commit()

    task_id = enqueue_integration_sync(str(ctx.tenant_id), str(tenant_integration.id), str(sync_run.id))
    return TriggerSyncResponse(sync_run_id=sync_run.id, task_id=task_id)
