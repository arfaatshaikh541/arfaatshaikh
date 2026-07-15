"""Milestone 1 maintenance tasks. Real, scheduled, idempotent — not
placeholders. Milestone 2+ adds connector sync / ingestion / correlation /
action-execution / report tasks alongside these in their respective
queues (see celery_app.QUEUE_*)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update

from db.session import AsyncSessionLocal, set_tenant_context
from modules.identity.models import Session as SessionModel
from modules.platform_admin.models import SupportAccessGrant
from modules.tenancy.models import Tenant
from worker.celery_app import celery_app

logger = structlog.get_logger("gridkeep.worker.tasks")

SESSION_RETENTION_AFTER_EXPIRY = timedelta(days=7)


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
