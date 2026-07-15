"""Milestone 1 maintenance tasks. Real, scheduled, idempotent — not
placeholders. Milestone 2+ adds connector sync / ingestion / correlation /
action-execution / report tasks alongside these in their respective
queues (see celery_app.QUEUE_*)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from gridkeep_connector_sdk.registry import get_connector_class
from sqlalchemy import select, update

from core.task_queue import enqueue_run_correlation
from db.session import AsyncSessionLocal, set_tenant_context
from modules.assets.ingestion import ingest_sync_records
from modules.credential_vault import service as vault_service
from modules.findings.engine import run_correlation
from modules.identity.models import Session as SessionModel
from modules.integrations.models import IntegrationCatalogEntry, IntegrationHealth, IntegrationSyncRun, TenantIntegration
from modules.platform_admin.models import SupportAccessGrant
from modules.tenancy.models import Tenant
from worker.celery_app import celery_app

logger = structlog.get_logger("gridkeep.worker.tasks")

SESSION_RETENTION_AFTER_EXPIRY = timedelta(days=7)


def _now() -> datetime:
    return datetime.now(UTC)


async def _cleanup_expired_sessions_async() -> int:
    """Deletes session rows that expired (or were revoked) more than
    SESSION_RETENTION_AFTER_EXPIRY ago. Sessions are kept briefly past
    expiry/revocation for support/audit troubleshooting, then purged —
    they carry no evidentiary value once gone (audit_logs is the
    permanent record of the auth events themselves)."""
    cutoff = datetime.now(UTC) - SESSION_RETENTION_AFTER_EXPIRY
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SessionModel.id).where(
                (SessionModel.expires_at < cutoff) | (SessionModel.revoked_at < cutoff)
            )
        )
        ids = [row[0] for row in result.all()]
        if ids:
            from sqlalchemy import delete

            await session.execute(delete(SessionModel).where(SessionModel.id.in_(ids)))
            await session.commit()
        return len(ids)


async def _expire_support_access_grants_async() -> int:
    """Flips `active` support-access grants whose `expires_at` has passed
    to `expired`. This is the enforcement backstop for the JIT time-box —
    the API also checks `expires_at` on every read (platform_admin.service
    .is_grant_active), but this keeps the stored status field truthful for
    anyone querying the table directly (audit tooling, reporting).

    `support_access_grants` has RLS with no platform-wide bypass (Rule 19
    — never trust a blanket bypass, even for background jobs), so a
    cross-tenant sweep must iterate tenant-by-tenant rather than issuing
    one unscoped query. `tenants` itself carries no RLS (it's the registry,
    not tenant-owned data), so listing tenant ids is safe."""
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        tenant_ids = [row[0] for row in (await session.execute(select(Tenant.id))).all()]

        count = 0
        for tenant_id in tenant_ids:
            await set_tenant_context(session, tenant_id)
            result = await session.execute(
                update(SupportAccessGrant)
                .where(
                    SupportAccessGrant.tenant_id == tenant_id,
                    SupportAccessGrant.status == "active",
                    SupportAccessGrant.expires_at < now,
                )
                .values(status="expired")
            )
            count += result.rowcount

        if count:
            await session.commit()
        return count


async def _run_integration_sync_async(
    tenant_id: str, tenant_integration_id: str, sync_run_id: str
) -> dict:
    """Runs one connector sync end-to-end: decrypt credential, authenticate,
    pull the full record stream, ingest into the asset graph, record the
    sync run outcome and a fresh health check. Atomic — a failure rolls
    back any partial asset writes from this attempt (the next sync
    re-derives the same state from upstream, so partial ingestion has no
    value to keep)."""
    tenant_uuid = uuid.UUID(tenant_id)
    integration_uuid = uuid.UUID(tenant_integration_id)
    run_uuid = uuid.UUID(sync_run_id)

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_uuid)
        try:
            tenant_integration = await session.get(TenantIntegration, integration_uuid)
            if tenant_integration is None:
                raise ValueError(f"Tenant integration {tenant_integration_id} not found.")
            catalog_entry = await session.get(
                IntegrationCatalogEntry, tenant_integration.catalog_entry_id
            )
            sync_run = await session.get(IntegrationSyncRun, run_uuid)
            if sync_run is None:
                raise ValueError(f"Sync run {sync_run_id} not found.")

            secret = await vault_service.get_decrypted_secret(session, tenant_integration.credential_id)
            connector_class = get_connector_class(catalog_entry.provider_id)
            connector = connector_class(credential_plaintext=secret)

            if not await connector.authenticate():
                raise RuntimeError("Authentication failed during sync.")

            records = [r async for r in connector.sync(mode=tenant_integration.sync_mode)]
            summary = await ingest_sync_records(
                session,
                tenant_id=tenant_uuid,
                tenant_integration_id=integration_uuid,
                provider_id=catalog_entry.provider_id,
                records=records,
            )
            health = await connector.health_check()
            await connector.disconnect()

            sync_run.status = "success"
            sync_run.completed_at = _now()
            sync_run.records_processed = summary.processed
            sync_run.records_created = summary.created
            sync_run.records_updated = summary.updated

            tenant_integration.last_synced_at = _now()
            session.add(
                IntegrationHealth(
                    tenant_id=tenant_uuid,
                    tenant_integration_id=integration_uuid,
                    status="healthy" if health.healthy else "degraded",
                    message=health.message,
                    checked_at=health.checked_at,
                )
            )
            await session.commit()
            # Chain correlation after a successful sync so findings stay
            # current without a separate manual step — the same
            # one-directional enqueue pattern used to kick off this sync
            # task in the first place (core/task_queue.py), not a direct
            # function call, so a correlation failure can't roll back the
            # sync that already committed.
            enqueue_run_correlation(tenant_id)
            return {
                "status": "success",
                "processed": summary.processed,
                "created": summary.created,
                "updated": summary.updated,
            }
        except Exception as exc:
            await session.rollback()
            await _record_sync_failure(
                tenant_id=tenant_uuid, sync_run_id=run_uuid, tenant_integration_id=integration_uuid, error=exc
            )
            raise


async def _record_sync_failure(
    *, tenant_id: uuid.UUID, sync_run_id: uuid.UUID, tenant_integration_id: uuid.UUID, error: Exception
) -> None:
    """Runs in a fresh session/transaction since the one that hit the
    error was rolled back — its ORM objects are stale."""
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        sync_run = await session.get(IntegrationSyncRun, sync_run_id)
        if sync_run is not None:
            sync_run.status = "failed"
            sync_run.completed_at = _now()
            sync_run.error_message = str(error)[:1000]
        session.add(
            IntegrationHealth(
                tenant_id=tenant_id,
                tenant_integration_id=tenant_integration_id,
                status="error",
                message=str(error)[:500],
                checked_at=_now(),
            )
        )
        await session.commit()


async def _run_correlation_async(tenant_id: str) -> dict:
    tenant_uuid = uuid.UUID(tenant_id)
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_uuid)
        summary = await run_correlation(session, tenant_id=tenant_uuid)
        await session.commit()
        return {
            "evaluated_assets": summary.evaluated_assets,
            "created": summary.created,
            "updated": summary.updated,
            "reopened": summary.reopened,
            "auto_resolved": summary.auto_resolved,
            "accepted_risk_expired": summary.accepted_risk_expired,
        }


@celery_app.task(name="worker.tasks.run_integration_sync")
def run_integration_sync(tenant_id: str, tenant_integration_id: str, sync_run_id: str) -> dict:
    result = asyncio.run(
        _run_integration_sync_async(tenant_id, tenant_integration_id, sync_run_id)
    )
    logger.info("integration_sync_complete", tenant_integration_id=tenant_integration_id, **result)
    return result


@celery_app.task(name="worker.tasks.run_correlation")
def run_correlation_task(tenant_id: str) -> dict:
    result = asyncio.run(_run_correlation_async(tenant_id))
    logger.info("correlation_complete", tenant_id=tenant_id, **result)
    return result


@celery_app.task(name="worker.tasks.cleanup_expired_sessions")
def cleanup_expired_sessions() -> int:
    deleted = asyncio.run(_cleanup_expired_sessions_async())
    logger.info("cleanup_expired_sessions_complete", deleted=deleted)
    return deleted


@celery_app.task(name="worker.tasks.expire_support_access_grants")
def expire_support_access_grants() -> int:
    expired = asyncio.run(_expire_support_access_grants_async())
    logger.info("expire_support_access_grants_complete", expired=expired)
    return expired


@celery_app.task(name="worker.tasks.health_check")
def health_check() -> str:
    return "ok"
