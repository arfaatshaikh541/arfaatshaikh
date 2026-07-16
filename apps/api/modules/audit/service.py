from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.audit.models import AuditLog


async def record(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    actor_label: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    context: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Write one append-only audit record. Callers pass the same session
    used for the surrounding operation so the audit row commits atomically
    with the change it documents — an action that isn't recorded didn't,
    from GRIDKEEP's perspective, verifiably happen (Rule 25)."""
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_label=actor_label,
        action=action,
        target_type=target_type,
        target_id=target_id,
        context=context or {},
        ip_address=ip_address,
    )
    session.add(entry)
    await session.flush()
    return entry


async def list_for_target(
    session: AsyncSession, *, tenant_id: uuid.UUID, target_type: str, target_id: str
) -> list[AuditLog]:
    """Read helper for module-specific timelines (e.g. a finding's
    activity log) that want to reuse the generic audit trail rather than
    maintaining their own append-only history table. RLS still restricts
    this to the caller's tenant regardless of the filter passed here."""
    result = await session.execute(
        select(AuditLog)
        .where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.target_type == target_type,
            AuditLog.target_id == target_id,
        )
        .order_by(AuditLog.created_at.desc())
    )
    return list(result.scalars().all())


async def list_platform_wide(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None = None,
    action: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLog]:
    """Milestone 12: the platform-wide audit trail view. Only visible
    through a `platform_admin_scoped_session` (see db/session.py) — the
    widened `audit_logs_select` policy is what actually makes rows from
    every tenant visible here; the `tenant_id`/`action` params below are
    ordinary WHERE-clause filters on top of that, not the access-control
    boundary itself."""
    query = select(AuditLog)
    if tenant_id is not None:
        query = query.where(AuditLog.tenant_id == tenant_id)
    if action is not None:
        query = query.where(AuditLog.action == action)
    query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars().all())
