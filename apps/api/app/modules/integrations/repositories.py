import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.modules.integrations.models import Integration, IntegrationDelivery


async def create_integration(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    name: str,
    webhook_url: str,
    webhook_secret_encrypted: str,
    created_by_user_id: uuid.UUID | None,
) -> Integration:
    integration = Integration(
        tenant_id=tenant_id,
        name=name,
        type="webhook",
        webhook_url=webhook_url,
        webhook_secret_encrypted=webhook_secret_encrypted,
        created_by_user_id=created_by_user_id,
    )
    session.add(integration)
    await session.flush()
    return integration


async def get_integration(session: AsyncSession, integration_id: uuid.UUID) -> Integration | None:
    stmt = select(Integration).where(Integration.id == integration_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_integration_or_raise(session: AsyncSession, integration_id: uuid.UUID) -> Integration:
    integration = await get_integration(session, integration_id)
    if integration is None:
        raise ResourceNotFoundError("Integration not found.")
    return integration


async def list_integrations_for_tenant(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[Integration]:
    stmt = select(Integration).where(Integration.tenant_id == tenant_id).order_by(Integration.name)
    return list((await session.execute(stmt)).scalars().all())


async def delete_integration(session: AsyncSession, integration: Integration) -> None:
    await session.delete(integration)
    await session.flush()


async def create_delivery(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    integration_id: uuid.UUID,
    lead_id: uuid.UUID | None,
    payload: dict,
    triggered_by_user_id: uuid.UUID | None,
) -> IntegrationDelivery:
    delivery = IntegrationDelivery(
        tenant_id=tenant_id,
        integration_id=integration_id,
        lead_id=lead_id,
        status="pending",
        payload=payload,
        triggered_by_user_id=triggered_by_user_id,
    )
    session.add(delivery)
    await session.flush()
    return delivery


async def get_delivery(session: AsyncSession, delivery_id: uuid.UUID) -> IntegrationDelivery | None:
    stmt = select(IntegrationDelivery).where(IntegrationDelivery.id == delivery_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_delivery_or_raise(
    session: AsyncSession, delivery_id: uuid.UUID
) -> IntegrationDelivery:
    delivery = await get_delivery(session, delivery_id)
    if delivery is None:
        raise ResourceNotFoundError("Delivery not found.")
    return delivery


async def mark_delivery_result(
    session: AsyncSession,
    delivery: IntegrationDelivery,
    *,
    status: str,
    http_status_code: int | None,
    response_snippet: str | None,
    error_message: str | None,
    attempt_count: int,
    delivered_at: datetime | None,
) -> None:
    delivery.status = status
    delivery.http_status_code = http_status_code
    delivery.response_snippet = response_snippet
    delivery.error_message = error_message
    delivery.attempt_count = attempt_count
    delivery.delivered_at = delivered_at
    await session.flush()


async def list_deliveries_for_integration(
    session: AsyncSession, integration_id: uuid.UUID, *, limit: int = 100
) -> list[IntegrationDelivery]:
    stmt = (
        select(IntegrationDelivery)
        .where(IntegrationDelivery.integration_id == integration_id)
        .order_by(IntegrationDelivery.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_deliveries_for_tenant(
    session: AsyncSession, tenant_id: uuid.UUID, *, limit: int = 100
) -> list[IntegrationDelivery]:
    stmt = (
        select(IntegrationDelivery)
        .where(IntegrationDelivery.tenant_id == tenant_id)
        .order_by(IntegrationDelivery.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
