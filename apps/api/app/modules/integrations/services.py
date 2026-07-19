import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_client import enqueue_integration_delivery
from app.core.exceptions import ConflictError, ValidationAppError
from app.core.security import encrypt_credential
from app.modules.integrations import repositories as integrations_repo
from app.modules.integrations.models import Integration, IntegrationDelivery
from app.modules.integrations.payload import build_lead_payload
from app.modules.integrations.schemas import CreateIntegrationRequest, UpdateIntegrationRequest
from app.modules.leads import repositories as leads_repo

_ALLOWED_SCHEMES = ("http://", "https://")


def _validate_webhook_url(url: str) -> None:
    """Basic, synchronous input validation only - not the security
    boundary. The real SSRF-safety check (DNS resolve-and-validate) runs
    in `worker.crawler.safety.safe_post_json` at actual delivery time,
    since that is the only point a TOCTOU-safe check is possible (DNS can
    change between when a URL is configured and when it's used) - see
    docs/adr/0016."""
    if not url.startswith(_ALLOWED_SCHEMES):
        raise ValidationAppError("Webhook URL must start with http:// or https://.")


async def create_integration(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
    request: CreateIntegrationRequest,
) -> Integration:
    _validate_webhook_url(request.webhook_url)
    return await integrations_repo.create_integration(
        session,
        tenant_id=tenant_id,
        name=request.name,
        webhook_url=request.webhook_url,
        webhook_secret_encrypted=encrypt_credential(request.webhook_secret),
        created_by_user_id=created_by_user_id,
    )


async def update_integration(
    session: AsyncSession, integration: Integration, *, request: UpdateIntegrationRequest
) -> Integration:
    if request.name is not None:
        integration.name = request.name
    if request.webhook_url is not None:
        _validate_webhook_url(request.webhook_url)
        integration.webhook_url = request.webhook_url
    if request.webhook_secret is not None:
        integration.webhook_secret_encrypted = encrypt_credential(request.webhook_secret)
    if request.enabled is not None:
        integration.enabled = request.enabled
    await session.flush()
    return integration


async def push_lead(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    integration: Integration,
    lead_id: uuid.UUID,
    triggered_by_user_id: uuid.UUID | None,
) -> IntegrationDelivery:
    if not integration.enabled:
        raise ConflictError("This integration is disabled.")
    lead = await leads_repo.get_lead_or_raise(session, lead_id)
    payload = await build_lead_payload(session, lead)
    delivery = await integrations_repo.create_delivery(
        session,
        tenant_id=tenant_id,
        integration_id=integration.id,
        lead_id=lead.id,
        payload=payload,
        triggered_by_user_id=triggered_by_user_id,
    )
    await session.commit()
    enqueue_integration_delivery(str(delivery.id))
    return delivery


async def bulk_push_leads(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    integration: Integration,
    lead_ids: list[uuid.UUID],
    triggered_by_user_id: uuid.UUID | None,
) -> list[IntegrationDelivery]:
    deliveries = []
    for lead_id in lead_ids:
        delivery = await push_lead(
            session,
            tenant_id=tenant_id,
            integration=integration,
            lead_id=lead_id,
            triggered_by_user_id=triggered_by_user_id,
        )
        deliveries.append(delivery)
    return deliveries
