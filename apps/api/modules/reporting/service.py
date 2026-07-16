"""The executive summary — a pure composition over the summary
functions every other module already exposes for its own dashboard
tile. No models, no migration: like `modules.resilience`, this module
has nothing of its own to store, only existing facts to synthesize into
one board-ready view.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.assets.models import Asset
from modules.compliance import service as compliance_service
from modules.findings import service as findings_service
from modules.incidents import service as incidents_service
from modules.resilience import service as resilience_service


async def get_executive_summary(session: AsyncSession, *, tenant_id: uuid.UUID) -> dict:
    asset_total = (
        await session.execute(select(func.count()).select_from(Asset).where(Asset.tenant_id == tenant_id))
    ).scalar_one()

    risk_summary = await findings_service.get_risk_summary(session, tenant_id=tenant_id)
    incident_summary = await incidents_service.get_incident_summary(session, tenant_id=tenant_id)
    resilience_summary = await resilience_service.get_resilience_summary(session, tenant_id=tenant_id)
    compliance_summary = await compliance_service.get_compliance_summary(session, tenant_id=tenant_id)

    return {
        "generated_at": datetime.now(UTC),
        "asset_total": asset_total,
        "security_score": risk_summary["security_score"],
        "open_findings_total": risk_summary["open_findings_total"],
        "open_findings_by_severity": risk_summary["open_findings_by_severity"],
        "open_incidents_total": incident_summary["open_incidents_total"],
        "open_incidents_by_severity": incident_summary["open_incidents_by_severity"],
        "recovery_confidence_score": resilience_summary["recovery_confidence_score"],
        "backup_job_total": resilience_summary["backup_job_total"],
        "compliance_overall_score": compliance_summary["overall_score"],
        "compliance_frameworks": [
            {"id": f["id"], "key": f["key"], "name": f["name"], "score": f["score"]}
            for f in compliance_summary["frameworks"]
        ],
    }
