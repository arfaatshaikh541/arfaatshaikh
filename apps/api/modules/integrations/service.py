from __future__ import annotations

import uuid
from datetime import UTC, datetime

from gridkeep_connector_sdk.registry import get_connector_class
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import settings
from core.errors import NotFoundError, ValidationAppError
from modules.credential_vault import service as vault_service
from modules.integrations.models import (
    IntegrationCatalogEntry,
    IntegrationHealth,
    IntegrationSyncRun,
    TenantIntegration,
)
from modules.integrations.schemas import TenantIntegrationRead


def _now() -> datetime:
    return datetime.now(UTC)


async def list_catalog(session: AsyncSession) -> list[IntegrationCatalogEntry]:
    """Simulator connectors are hidden from a production environment's
    catalogue — they exist for development and demonstration only and must
    never be presented as real protection (Rule 9)."""
    query = select(IntegrationCatalogEntry).where(IntegrationCatalogEntry.is_active.is_(True))
    if settings.is_production:
        query = query.where(IntegrationCatalogEntry.is_simulator.is_(False))
    result = await session.execute(query)
    return list(result.scalars().all())


async def connect_integration(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    provider_id: str,
    label: str,
    secret_plaintext: str,
) -> TenantIntegration:
    catalog_entry = (
        await session.execute(
            select(IntegrationCatalogEntry).where(
                IntegrationCatalogEntry.provider_id == provider_id,
                IntegrationCatalogEntry.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if catalog_entry is None:
        raise NotFoundError(f"Unknown or inactive integration provider '{provider_id}'.")
    if settings.is_production and catalog_entry.is_simulator:
        raise ValidationAppError("Simulated providers cannot be connected in production.")

    connector_class = get_connector_class(provider_id)
    connector = connector_class(credential_plaintext=secret_plaintext)
    authenticated = await connector.authenticate()
    if not authenticated:
        raise ValidationAppError(
            "Could not authenticate with the provider using the credential you supplied."
        )

    credential = await vault_service.store_credential(
        session,
        tenant_id=tenant_id,
        provider_key=provider_id,
        label=label,
        secret_plaintext=secret_plaintext,
        created_by_user_id=actor_user_id,
    )

    tenant_integration = TenantIntegration(
        tenant_id=tenant_id,
        catalog_entry_id=catalog_entry.id,
        credential_id=credential.id,
        label=label,
        status="connected",
        sync_mode=catalog_entry.sync_modes[0] if catalog_entry.sync_modes else "full",
        created_by_user_id=actor_user_id,
    )
    tenant_integration.catalog_entry = catalog_entry  # populate the relationship in-memory —
    # avoids a lazy-load (which would need a DB round trip after this
    # function's caller commits, see routes.py's "no queries after commit"
    # rule for tenant_scoped_session-backed requests)
    session.add(tenant_integration)
    await session.flush()

    health = await connector.health_check()
    session.add(
        IntegrationHealth(
            tenant_id=tenant_id,
            tenant_integration_id=tenant_integration.id,
            status="healthy" if health.healthy else "error",
            message=health.message,
            checked_at=health.checked_at,
        )
    )
    await connector.disconnect()
    await session.flush()
    return tenant_integration


async def disconnect_integration(
    session: AsyncSession, *, tenant_id: uuid.UUID, tenant_integration_id: uuid.UUID
) -> TenantIntegration:
    tenant_integration = (
        await session.execute(
            select(TenantIntegration)
            .options(selectinload(TenantIntegration.catalog_entry))
            .where(TenantIntegration.id == tenant_integration_id, TenantIntegration.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if tenant_integration is None:
        raise NotFoundError("Integration not found.")

    await vault_service.revoke_credential(
        session, credential_id=tenant_integration.credential_id, tenant_id=tenant_id
    )
    tenant_integration.status = "disconnected"
    tenant_integration.disconnected_at = _now()
    await session.flush()
    return tenant_integration


async def list_tenant_integrations(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[TenantIntegration]:
    result = await session.execute(
        select(TenantIntegration)
        .options(selectinload(TenantIntegration.catalog_entry))
        .where(TenantIntegration.tenant_id == tenant_id)
    )
    return list(result.scalars().all())


def to_tenant_integration_read(tenant_integration: TenantIntegration) -> TenantIntegrationRead:
    """Milestone 20: promoted out of `integrations.routes`'s route-private
    `_to_tenant_integration_read` so `modules.platform_admin`'s grant-gated
    integrations drill-down can reuse the exact same mapping — the same
    refactor Milestone 18 did for findings and Milestone 19 did for
    incidents. Requires `catalog_entry` to already be eager-loaded (see
    `list_tenant_integrations`'s `selectinload`)."""
    return TenantIntegrationRead(
        id=tenant_integration.id,
        provider_id=tenant_integration.catalog_entry.provider_id,
        provider_name=tenant_integration.catalog_entry.name,
        label=tenant_integration.label,
        status=tenant_integration.status,
        sync_mode=tenant_integration.sync_mode,
        last_synced_at=tenant_integration.last_synced_at,
        created_at=tenant_integration.created_at,
    )


async def create_sync_run(
    session: AsyncSession, *, tenant_id: uuid.UUID, tenant_integration_id: uuid.UUID
) -> IntegrationSyncRun:
    run = IntegrationSyncRun(
        tenant_id=tenant_id,
        tenant_integration_id=tenant_integration_id,
        status="running",
        started_at=_now(),
    )
    session.add(run)
    await session.flush()
    return run


async def list_sync_runs(
    session: AsyncSession, *, tenant_id: uuid.UUID, tenant_integration_id: uuid.UUID
) -> list[IntegrationSyncRun]:
    result = await session.execute(
        select(IntegrationSyncRun)
        .where(
            IntegrationSyncRun.tenant_id == tenant_id,
            IntegrationSyncRun.tenant_integration_id == tenant_integration_id,
        )
        .order_by(IntegrationSyncRun.started_at.desc())
    )
    return list(result.scalars().all())


async def get_tenant_integration_or_404(
    session: AsyncSession, *, tenant_id: uuid.UUID, tenant_integration_id: uuid.UUID
) -> TenantIntegration:
    tenant_integration = (
        await session.execute(
            select(TenantIntegration)
            .options(selectinload(TenantIntegration.catalog_entry))
            .where(TenantIntegration.id == tenant_integration_id, TenantIntegration.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if tenant_integration is None:
        raise NotFoundError("Integration not found.")
    return tenant_integration


async def list_health_history(
    session: AsyncSession, *, tenant_id: uuid.UUID, tenant_integration_id: uuid.UUID
) -> list[IntegrationHealth]:
    result = await session.execute(
        select(IntegrationHealth)
        .where(
            IntegrationHealth.tenant_id == tenant_id,
            IntegrationHealth.tenant_integration_id == tenant_integration_id,
        )
        .order_by(IntegrationHealth.checked_at.desc())
    )
    return list(result.scalars().all())
