from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import NotFoundError, ValidationAppError
from modules.assets.models import Asset
from modules.findings.models import ACTIVE_STATUSES, Finding
from modules.findings.schemas import FindingListItem
from modules.findings.scoring import compute_finding_risk_score, compute_tenant_security_score
from modules.permissions.models import Membership


def _now() -> datetime:
    return datetime.now(UTC)


async def list_findings(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    severity: str | None = None,
    status: str | None = None,
    asset_id: uuid.UUID | None = None,
    search: str | None = None,
) -> list[tuple[Finding, Asset]]:
    query = (
        select(Finding, Asset)
        .join(Asset, Asset.id == Finding.asset_id)
        .where(Finding.tenant_id == tenant_id)
    )
    if severity:
        query = query.where(Finding.severity == severity)
    if status:
        query = query.where(Finding.status == status)
    if asset_id:
        query = query.where(Finding.asset_id == asset_id)
    if search:
        query = query.where(Finding.title.ilike(f"%{search}%"))
    query = query.order_by(Finding.last_observed_at.desc())
    result = await session.execute(query)
    return [(finding, asset) for finding, asset in result.all()]


def to_finding_list_item(finding: Finding, asset: Asset) -> FindingListItem:
    """Milestone 18: promoted out of `findings.routes`'s route-private
    `_to_list_item` so `modules.platform_admin`'s grant-gated findings
    drill-down can reuse the exact same risk-scoring mapping instead of
    duplicating it."""
    return FindingListItem(
        id=finding.id,
        rule_key=finding.rule_key,
        title=finding.title,
        category=finding.category,
        severity=finding.severity,
        status=finding.status,
        risk_score=compute_finding_risk_score(finding.severity, asset.criticality),
        asset_id=asset.id,
        asset_display_name=asset.display_name,
        asset_criticality=asset.criticality,
        assigned_to_user_id=finding.assigned_to_user_id,
        first_observed_at=finding.first_observed_at,
        last_observed_at=finding.last_observed_at,
    )


async def get_finding_detail(
    session: AsyncSession, *, tenant_id: uuid.UUID, finding_id: uuid.UUID
) -> tuple[Finding, Asset]:
    row = (
        await session.execute(
            select(Finding, Asset)
            .join(Asset, Asset.id == Finding.asset_id)
            .where(Finding.id == finding_id, Finding.tenant_id == tenant_id)
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError("Finding not found.")
    return row


async def get_risk_summary(session: AsyncSession, *, tenant_id: uuid.UUID) -> dict:
    active_findings = (
        await session.execute(
            select(Finding.severity).where(
                Finding.tenant_id == tenant_id, Finding.status.in_(ACTIVE_STATUSES)
            )
        )
    ).scalars().all()
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for severity in active_findings:
        counts[severity] += 1
    return {
        "security_score": compute_tenant_security_score(list(active_findings)),
        "open_findings_total": len(active_findings),
        "open_findings_by_severity": counts,
    }


async def _get_finding_or_404(
    session: AsyncSession, *, tenant_id: uuid.UUID, finding_id: uuid.UUID
) -> tuple[Finding, Asset]:
    row = (
        await session.execute(
            select(Finding, Asset)
            .join(Asset, Asset.id == Finding.asset_id)
            .where(Finding.id == finding_id, Finding.tenant_id == tenant_id)
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError("Finding not found.")
    return row


async def assign_finding(
    session: AsyncSession, *, tenant_id: uuid.UUID, finding_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Finding, Asset]:
    finding, asset = await _get_finding_or_404(session, tenant_id=tenant_id, finding_id=finding_id)
    is_member = (
        await session.execute(
            select(Membership.id).where(Membership.tenant_id == tenant_id, Membership.user_id == user_id)
        )
    ).scalar_one_or_none()
    if is_member is None:
        raise ValidationAppError("Can only assign findings to a member of this workspace.")
    finding.assigned_to_user_id = user_id
    if finding.status == "open":
        finding.status = "assigned"
    await session.flush()
    return finding, asset


async def accept_risk(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    finding_id: uuid.UUID,
    reason: str,
    expires_at: datetime | None,
) -> tuple[Finding, Asset]:
    finding, asset = await _get_finding_or_404(session, tenant_id=tenant_id, finding_id=finding_id)
    finding.status = "accepted_risk"
    finding.resolution_note = reason
    finding.accepted_risk_expires_at = expires_at
    finding.closed_at = None
    await session.flush()
    return finding, asset


async def remediate_finding(
    session: AsyncSession, *, tenant_id: uuid.UUID, finding_id: uuid.UUID, note: str | None
) -> tuple[Finding, Asset]:
    finding, asset = await _get_finding_or_404(session, tenant_id=tenant_id, finding_id=finding_id)
    finding.status = "remediated"
    finding.resolution_note = note
    finding.closed_at = _now()
    await session.flush()
    return finding, asset


async def dismiss_finding(
    session: AsyncSession, *, tenant_id: uuid.UUID, finding_id: uuid.UUID, reason: str
) -> tuple[Finding, Asset]:
    finding, asset = await _get_finding_or_404(session, tenant_id=tenant_id, finding_id=finding_id)
    finding.status = "false_positive"
    finding.resolution_note = reason
    finding.closed_at = _now()
    await session.flush()
    return finding, asset


async def reopen_finding(
    session: AsyncSession, *, tenant_id: uuid.UUID, finding_id: uuid.UUID
) -> tuple[Finding, Asset]:
    finding, asset = await _get_finding_or_404(session, tenant_id=tenant_id, finding_id=finding_id)
    finding.status = "open"
    finding.closed_at = None
    finding.accepted_risk_expires_at = None
    await session.flush()
    return finding, asset
