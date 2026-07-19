import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.dependencies import TenantContext, require_permission
from app.modules.integrations import repositories as integrations_repo
from app.modules.integrations import services
from app.modules.integrations.schemas import (
    BulkPushRequest,
    CreateIntegrationRequest,
    DeliveryListResponse,
    DeliveryResponse,
    IntegrationListResponse,
    IntegrationResponse,
    UpdateIntegrationRequest,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.post("", response_model=IntegrationResponse)
async def create_integration(
    request: CreateIntegrationRequest,
    ctx: TenantContext = Depends(require_permission("integrations.manage")),
    db: AsyncSession = Depends(get_db),
):
    integration = await services.create_integration(
        db, tenant_id=ctx.tenant_id, created_by_user_id=ctx.user_id, request=request
    )
    return IntegrationResponse.from_model(integration)


@router.get("", response_model=IntegrationListResponse)
async def list_integrations(
    ctx: TenantContext = Depends(require_permission("integrations.view")),
    db: AsyncSession = Depends(get_db),
):
    integrations = await integrations_repo.list_integrations_for_tenant(db, ctx.tenant_id)
    return IntegrationListResponse(
        integrations=[IntegrationResponse.from_model(i) for i in integrations]
    )


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("integrations.view")),
    db: AsyncSession = Depends(get_db),
):
    integration = await integrations_repo.get_integration_or_raise(db, integration_id)
    return IntegrationResponse.from_model(integration)


@router.patch("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: uuid.UUID,
    request: UpdateIntegrationRequest,
    ctx: TenantContext = Depends(require_permission("integrations.manage")),
    db: AsyncSession = Depends(get_db),
):
    integration = await integrations_repo.get_integration_or_raise(db, integration_id)
    updated = await services.update_integration(db, integration, request=request)
    return IntegrationResponse.from_model(updated)


@router.delete("/{integration_id}", status_code=204)
async def delete_integration(
    integration_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("integrations.manage")),
    db: AsyncSession = Depends(get_db),
):
    integration = await integrations_repo.get_integration_or_raise(db, integration_id)
    await integrations_repo.delete_integration(db, integration)


# `/push/bulk` (literal) is registered before `/push/{lead_id}`
# (parameterized) - both are two-segment paths after `/{integration_id}`,
# and Starlette matches routes in registration order with a parameterized
# segment matching any string, including the literal "bulk". Registering
# `/push/{lead_id}` first would make a request to `/push/bulk` try to
# parse "bulk" as a UUID and 422 instead of reaching the bulk handler -
# the exact class of bug ADR-0014 already found and fixed once in
# `leads.routes` (`/leads/bulk/status` vs. `/leads/{lead_id}/status`).
@router.post("/{integration_id}/push/bulk", response_model=DeliveryListResponse)
async def bulk_push_leads(
    integration_id: uuid.UUID,
    request: BulkPushRequest,
    ctx: TenantContext = Depends(require_permission("integrations.view")),
    db: AsyncSession = Depends(get_db),
):
    integration = await integrations_repo.get_integration_or_raise(db, integration_id)
    deliveries = await services.bulk_push_leads(
        db,
        tenant_id=ctx.tenant_id,
        integration=integration,
        lead_ids=request.lead_ids,
        triggered_by_user_id=ctx.user_id,
    )
    return DeliveryListResponse(deliveries=[DeliveryResponse.from_model(d) for d in deliveries])


@router.post("/{integration_id}/push/{lead_id}", response_model=DeliveryResponse)
async def push_lead(
    integration_id: uuid.UUID,
    lead_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("integrations.view")),
    db: AsyncSession = Depends(get_db),
):
    integration = await integrations_repo.get_integration_or_raise(db, integration_id)
    delivery = await services.push_lead(
        db,
        tenant_id=ctx.tenant_id,
        integration=integration,
        lead_id=lead_id,
        triggered_by_user_id=ctx.user_id,
    )
    return DeliveryResponse.from_model(delivery)


@router.get("/{integration_id}/deliveries", response_model=DeliveryListResponse)
async def list_deliveries(
    integration_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("integrations.view")),
    db: AsyncSession = Depends(get_db),
):
    await integrations_repo.get_integration_or_raise(db, integration_id)
    deliveries = await integrations_repo.list_deliveries_for_integration(db, integration_id)
    return DeliveryListResponse(deliveries=[DeliveryResponse.from_model(d) for d in deliveries])
