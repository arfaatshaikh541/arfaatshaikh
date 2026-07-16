"""Compliance status tracking + polymorphic evidence records.

Scoring mirrors `modules.findings.scoring` and `modules.resilience.service`
in spirit: simple, linear, explainable — a framework's score is just
`met / total * 100` (a `partial` control counts as half credit,
`not_applicable` controls are excluded from the denominator entirely
since they're not part of what the tenant is being measured against).
Not a substitute for an actual audit.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import NotFoundError, ValidationAppError
from modules.compliance.models import (
    ComplianceControl,
    ComplianceFramework,
    EvidenceRecord,
    TenantControlStatus,
)
from modules.incidents.models import Incident

_CONTROL_STATUS_CREDIT = {"met": 1.0, "partial": 0.5, "not_met": 0.0}

# Which permission is required to create/delete evidence depends on what
# it's attached to — there is no standalone `evidence.manage` permission
# (see `EvidenceRecord`'s docstring for why).
TARGET_MANAGE_PERMISSION = {
    "compliance_control": "compliance.manage",
    "incident": "incidents.manage",
}


def _now() -> datetime:
    return datetime.now(UTC)


async def list_frameworks_with_status(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> list[dict]:
    frameworks = (
        await session.execute(select(ComplianceFramework).order_by(ComplianceFramework.name))
    ).scalars().all()
    controls = (
        await session.execute(select(ComplianceControl).order_by(ComplianceControl.sort_order))
    ).scalars().all()
    controls_by_framework: dict[uuid.UUID, list[ComplianceControl]] = {}
    for control in controls:
        controls_by_framework.setdefault(control.framework_id, []).append(control)

    statuses = (
        await session.execute(
            select(TenantControlStatus).where(TenantControlStatus.tenant_id == tenant_id)
        )
    ).scalars().all()
    status_by_control = {s.control_id: s for s in statuses}

    result = []
    for framework in frameworks:
        framework_controls = controls_by_framework.get(framework.id, [])
        control_rows = []
        credit = 0.0
        counted = 0
        for control in framework_controls:
            tenant_status = status_by_control.get(control.id)
            status_value = tenant_status.status if tenant_status else "not_met"
            control_rows.append(
                {
                    "id": control.id,
                    "key": control.key,
                    "title": control.title,
                    "description": control.description,
                    "status": status_value,
                    "note": tenant_status.note if tenant_status else None,
                    "updated_by_user_id": tenant_status.updated_by_user_id if tenant_status else None,
                    "updated_at": tenant_status.updated_at if tenant_status else None,
                }
            )
            if status_value != "not_applicable":
                counted += 1
                credit += _CONTROL_STATUS_CREDIT.get(status_value, 0.0)
        score = round((credit / counted) * 100) if counted else 100
        result.append(
            {
                "id": framework.id,
                "key": framework.key,
                "name": framework.name,
                "description": framework.description,
                "score": score,
                "controls": control_rows,
            }
        )
    return result


async def get_compliance_summary(session: AsyncSession, *, tenant_id: uuid.UUID) -> dict:
    frameworks = await list_frameworks_with_status(session, tenant_id=tenant_id)
    framework_scores = [
        {
            "id": f["id"],
            "key": f["key"],
            "name": f["name"],
            "score": f["score"],
            "met_count": sum(1 for c in f["controls"] if c["status"] == "met"),
            "total_count": len(f["controls"]),
        }
        for f in frameworks
        if f["controls"]
    ]
    overall_score = (
        round(sum(f["score"] for f in framework_scores) / len(framework_scores))
        if framework_scores
        else None
    )
    return {"overall_score": overall_score, "frameworks": framework_scores}


async def update_control_status(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    control_id: uuid.UUID,
    status: str,
    note: str | None,
    actor_user_id: uuid.UUID,
) -> TenantControlStatus:
    control = (
        await session.execute(select(ComplianceControl).where(ComplianceControl.id == control_id))
    ).scalar_one_or_none()
    if control is None:
        raise NotFoundError("Compliance control not found.")

    existing = (
        await session.execute(
            select(TenantControlStatus).where(
                TenantControlStatus.tenant_id == tenant_id,
                TenantControlStatus.control_id == control_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = TenantControlStatus(tenant_id=tenant_id, control_id=control_id)
        session.add(existing)
    existing.status = status
    existing.note = note
    existing.updated_by_user_id = actor_user_id
    await session.flush()
    return existing


async def get_control_detail(
    session: AsyncSession, *, tenant_id: uuid.UUID, control_id: uuid.UUID
) -> dict:
    control = (
        await session.execute(select(ComplianceControl).where(ComplianceControl.id == control_id))
    ).scalar_one_or_none()
    if control is None:
        raise NotFoundError("Compliance control not found.")
    tenant_status = (
        await session.execute(
            select(TenantControlStatus).where(
                TenantControlStatus.tenant_id == tenant_id,
                TenantControlStatus.control_id == control_id,
            )
        )
    ).scalar_one_or_none()
    return {
        "id": control.id,
        "key": control.key,
        "title": control.title,
        "description": control.description,
        "status": tenant_status.status if tenant_status else "not_met",
        "note": tenant_status.note if tenant_status else None,
        "updated_by_user_id": tenant_status.updated_by_user_id if tenant_status else None,
        "updated_at": tenant_status.updated_at if tenant_status else None,
    }


async def _validate_target_exists(
    session: AsyncSession, *, tenant_id: uuid.UUID, target_type: str, target_id: uuid.UUID
) -> None:
    if target_type == "compliance_control":
        control = (
            await session.execute(select(ComplianceControl.id).where(ComplianceControl.id == target_id))
        ).scalar_one_or_none()
        if control is None:
            raise NotFoundError("Compliance control not found.")
    elif target_type == "incident":
        incident = (
            await session.execute(
                select(Incident.id).where(Incident.id == target_id, Incident.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if incident is None:
            raise NotFoundError("Incident not found.")
    else:
        raise ValidationAppError(f"Unknown evidence target type '{target_type}'.")


async def create_evidence(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    title: str,
    description: str,
    evidence_type: str,
    source_url: str | None,
    target_type: str,
    target_id: uuid.UUID,
    collected_at: datetime | None,
    created_by_user_id: uuid.UUID,
) -> EvidenceRecord:
    await _validate_target_exists(session, tenant_id=tenant_id, target_type=target_type, target_id=target_id)
    evidence = EvidenceRecord(
        tenant_id=tenant_id,
        title=title,
        description=description,
        evidence_type=evidence_type,
        source_url=source_url,
        target_type=target_type,
        target_id=target_id,
        collected_at=collected_at or _now(),
        created_by_user_id=created_by_user_id,
    )
    session.add(evidence)
    await session.flush()
    return evidence


async def list_evidence(
    session: AsyncSession, *, tenant_id: uuid.UUID, target_type: str, target_id: uuid.UUID
) -> list[EvidenceRecord]:
    rows = (
        await session.execute(
            select(EvidenceRecord)
            .where(
                EvidenceRecord.tenant_id == tenant_id,
                EvidenceRecord.target_type == target_type,
                EvidenceRecord.target_id == target_id,
            )
            .order_by(EvidenceRecord.collected_at.desc())
        )
    ).scalars().all()
    return list(rows)


async def get_evidence_or_404(
    session: AsyncSession, *, tenant_id: uuid.UUID, evidence_id: uuid.UUID
) -> EvidenceRecord:
    evidence = (
        await session.execute(
            select(EvidenceRecord).where(
                EvidenceRecord.id == evidence_id, EvidenceRecord.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if evidence is None:
        raise NotFoundError("Evidence record not found.")
    return evidence


async def delete_evidence(session: AsyncSession, *, tenant_id: uuid.UUID, evidence_id: uuid.UUID) -> None:
    evidence = await get_evidence_or_404(session, tenant_id=tenant_id, evidence_id=evidence_id)
    await session.delete(evidence)
    await session.flush()
