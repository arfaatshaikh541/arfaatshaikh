from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.assets.models import Asset
from modules.findings.models import Finding
from modules.threat_intel.engine import RULE_KEY
from modules.threat_intel.models import ThreatIndicator


async def list_indicators(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[dict]:
    indicators = (
        await session.execute(
            select(ThreatIndicator)
            .where(ThreatIndicator.tenant_id == tenant_id)
            .order_by(ThreatIndicator.last_seen_at.desc())
        )
    ).scalars().all()

    findings = (
        await session.execute(
            select(Finding, Asset)
            .join(Asset, Asset.id == Finding.asset_id)
            .where(Finding.tenant_id == tenant_id, Finding.rule_key == RULE_KEY)
        )
    ).all()
    matches_by_indicator_id: dict[str, list[dict]] = {}
    for finding, asset in findings:
        indicator_id = finding.evidence.get("indicator_id")
        if indicator_id is None:
            continue
        matches_by_indicator_id.setdefault(indicator_id, []).append(
            {
                "asset_id": asset.id,
                "asset_display_name": asset.display_name,
                "finding_id": finding.id,
                "finding_status": finding.status,
            }
        )

    return [
        {
            "id": indicator.id,
            "indicator_type": indicator.indicator_type,
            "value": indicator.value,
            "confidence": indicator.confidence,
            "source": indicator.source,
            "first_seen_at": indicator.first_seen_at,
            "last_seen_at": indicator.last_seen_at,
            "matches": matches_by_indicator_id.get(str(indicator.id), []),
        }
        for indicator in indicators
    ]
