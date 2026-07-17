from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import NotFoundError, ValidationAppError
from modules.assets.models import Asset, AssetType
from modules.findings.models import Finding
from modules.incidents.models import Incident, IncidentAsset, IncidentFinding
from modules.incidents.schemas import IncidentListItem
from modules.permissions.models import Membership


def _now() -> datetime:
    return datetime.now(UTC)


async def _validate_member(session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    is_member = (
        await session.execute(
            select(Membership.id).where(Membership.tenant_id == tenant_id, Membership.user_id == user_id)
        )
    ).scalar_one_or_none()
    if is_member is None:
        raise ValidationAppError("Can only assign incidents to a member of this workspace.")


async def get_incident_or_404(
    session: AsyncSession, *, tenant_id: uuid.UUID, incident_id: uuid.UUID
) -> Incident:
    incident = (
        await session.execute(
            select(Incident).where(Incident.id == incident_id, Incident.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if incident is None:
        raise NotFoundError("Incident not found.")
    return incident


async def link_asset(
    session: AsyncSession, *, tenant_id: uuid.UUID, incident_id: uuid.UUID, asset_id: uuid.UUID
) -> Asset:
    asset = (
        await session.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if asset is None:
        raise NotFoundError("Asset not found.")
    existing = (
        await session.execute(
            select(IncidentAsset.id).where(
                IncidentAsset.tenant_id == tenant_id,
                IncidentAsset.incident_id == incident_id,
                IncidentAsset.asset_id == asset_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(IncidentAsset(tenant_id=tenant_id, incident_id=incident_id, asset_id=asset_id))
        await session.flush()
    return asset


async def link_finding(
    session: AsyncSession, *, tenant_id: uuid.UUID, incident_id: uuid.UUID, finding_id: uuid.UUID
) -> Finding:
    finding = (
        await session.execute(select(Finding).where(Finding.id == finding_id, Finding.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if finding is None:
        raise NotFoundError("Finding not found.")
    existing = (
        await session.execute(
            select(IncidentFinding.id).where(
                IncidentFinding.tenant_id == tenant_id,
                IncidentFinding.incident_id == incident_id,
                IncidentFinding.finding_id == finding_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(IncidentFinding(tenant_id=tenant_id, incident_id=incident_id, finding_id=finding_id))
        await session.flush()
    # A finding's own affected asset is part of the incident too — the whole
    # point of escalating a finding is that the asset it's about is involved.
    await link_asset(session, tenant_id=tenant_id, incident_id=incident_id, asset_id=finding.asset_id)
    return finding


async def declare_incident(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    title: str,
    description: str,
    severity: str,
    finding_ids: list[uuid.UUID],
    asset_ids: list[uuid.UUID],
) -> Incident:
    incident = Incident(
        tenant_id=tenant_id,
        title=title,
        description=description,
        severity=severity,
        status="declared",
        declared_by_user_id=actor_user_id,
        declared_at=_now(),
    )
    session.add(incident)
    await session.flush()

    for finding_id in finding_ids:
        await link_finding(session, tenant_id=tenant_id, incident_id=incident.id, finding_id=finding_id)
    for asset_id in asset_ids:
        await link_asset(session, tenant_id=tenant_id, incident_id=incident.id, asset_id=asset_id)

    return incident


async def update_incident(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    incident_id: uuid.UUID,
    title: str | None,
    description: str | None,
    severity: str | None,
    assigned_to_user_id: uuid.UUID | None,
) -> Incident:
    incident = await get_incident_or_404(session, tenant_id=tenant_id, incident_id=incident_id)
    if assigned_to_user_id is not None:
        await _validate_member(session, tenant_id=tenant_id, user_id=assigned_to_user_id)
        incident.assigned_to_user_id = assigned_to_user_id
    if title is not None:
        incident.title = title
    if description is not None:
        incident.description = description
    if severity is not None:
        incident.severity = severity
    await session.flush()
    return incident


async def update_status(
    session: AsyncSession, *, tenant_id: uuid.UUID, incident_id: uuid.UUID, status: str
) -> Incident:
    incident = await get_incident_or_404(session, tenant_id=tenant_id, incident_id=incident_id)
    if incident.status == "closed":
        raise ValidationAppError("Cannot change the status of a closed incident directly — reopen it first.")
    incident.status = status
    if status == "resolved":
        incident.resolved_at = _now()
    await session.flush()
    return incident


async def close_incident(
    session: AsyncSession, *, tenant_id: uuid.UUID, incident_id: uuid.UUID, closure_summary: str
) -> Incident:
    incident = await get_incident_or_404(session, tenant_id=tenant_id, incident_id=incident_id)
    if incident.status == "closed":
        raise ValidationAppError("Incident is already closed.")
    incident.status = "closed"
    incident.closed_at = _now()
    incident.closure_summary = closure_summary
    await session.flush()
    return incident


async def reopen_incident(session: AsyncSession, *, tenant_id: uuid.UUID, incident_id: uuid.UUID) -> Incident:
    incident = await get_incident_or_404(session, tenant_id=tenant_id, incident_id=incident_id)
    if incident.status != "closed":
        raise ValidationAppError("Incident is not closed.")
    incident.status = "investigating"
    incident.closed_at = None
    await session.flush()
    return incident


async def list_incidents(
    session: AsyncSession, *, tenant_id: uuid.UUID, status: str | None, severity: str | None
) -> list[tuple[Incident, int, int]]:
    query = select(Incident).where(Incident.tenant_id == tenant_id)
    if status:
        query = query.where(Incident.status == status)
    if severity:
        query = query.where(Incident.severity == severity)
    query = query.order_by(Incident.declared_at.desc())
    incidents = (await session.execute(query)).scalars().all()

    finding_counts = dict(
        (
            await session.execute(
                select(IncidentFinding.incident_id, func.count(IncidentFinding.id))
                .where(IncidentFinding.tenant_id == tenant_id)
                .group_by(IncidentFinding.incident_id)
            )
        ).all()
    )
    asset_counts = dict(
        (
            await session.execute(
                select(IncidentAsset.incident_id, func.count(IncidentAsset.id))
                .where(IncidentAsset.tenant_id == tenant_id)
                .group_by(IncidentAsset.incident_id)
            )
        ).all()
    )
    return [(i, finding_counts.get(i.id, 0), asset_counts.get(i.id, 0)) for i in incidents]


def to_incident_list_item(incident: Incident, finding_count: int, asset_count: int) -> IncidentListItem:
    """Milestone 19: promoted out of `incidents.routes`'s route-private
    `_to_list_item` so `modules.platform_admin`'s grant-gated incidents
    drill-down can reuse the exact same mapping instead of duplicating
    it — the same refactor Milestone 18 did for findings."""
    return IncidentListItem(
        id=incident.id,
        title=incident.title,
        severity=incident.severity,
        status=incident.status,
        assigned_to_user_id=incident.assigned_to_user_id,
        finding_count=finding_count,
        asset_count=asset_count,
        declared_at=incident.declared_at,
        resolved_at=incident.resolved_at,
        closed_at=incident.closed_at,
    )


async def get_incident_detail(session: AsyncSession, *, tenant_id: uuid.UUID, incident_id: uuid.UUID):
    incident = await get_incident_or_404(session, tenant_id=tenant_id, incident_id=incident_id)

    findings_rows = (
        await session.execute(
            select(Finding, Asset.display_name)
            .join(IncidentFinding, IncidentFinding.finding_id == Finding.id)
            .join(Asset, Asset.id == Finding.asset_id)
            .where(IncidentFinding.tenant_id == tenant_id, IncidentFinding.incident_id == incident_id)
        )
    ).all()

    assets_rows = (
        await session.execute(
            select(Asset, AssetType.key)
            .join(IncidentAsset, IncidentAsset.asset_id == Asset.id)
            .join(AssetType, AssetType.id == Asset.asset_type_id)
            .where(IncidentAsset.tenant_id == tenant_id, IncidentAsset.incident_id == incident_id)
        )
    ).all()

    return incident, findings_rows, assets_rows


async def get_incident_summary(session: AsyncSession, *, tenant_id: uuid.UUID) -> dict:
    severities = (
        await session.execute(
            select(Incident.severity).where(Incident.tenant_id == tenant_id, Incident.status != "closed")
        )
    ).scalars().all()
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for severity in severities:
        counts[severity] += 1
    return {"open_incidents_total": len(severities), "open_incidents_by_severity": counts}
