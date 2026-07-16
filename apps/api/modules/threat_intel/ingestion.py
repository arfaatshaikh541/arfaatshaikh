"""Threat-indicator ingestion — the "different subsystem" `modules.assets
.ingestion` has documented since Milestone 2. Deliberately simpler than
asset ingestion: indicators have no relationships, no identifier-based
dedup graph, and no change-log table — just an upsert keyed on
(tenant_id, external_id). Refining an indicator's confidence/last-seen
timestamp is not evidence-worthy the way an asset attribute changing is,
so there's nothing here analogous to `AssetChange`."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from gridkeep_connector_sdk import NormalizedRecord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.threat_intel.models import ThreatIndicator

THREAT_INTEL_RECORD_TYPE = "threat_intel.indicator"


@dataclass
class ThreatIntelIngestSummary:
    processed: int = 0
    created: int = 0
    updated: int = 0


async def ingest_threat_indicators(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    tenant_integration_id: uuid.UUID,
    provider_id: str,
    records: list[NormalizedRecord],
) -> ThreatIntelIngestSummary:
    summary = ThreatIntelIngestSummary()
    indicator_records = [r for r in records if r.record_type == THREAT_INTEL_RECORD_TYPE]
    if not indicator_records:
        return summary

    existing_by_external_id = {
        row.external_id: row
        for row in (
            await session.execute(
                select(ThreatIndicator).where(ThreatIndicator.tenant_id == tenant_id)
            )
        )
        .scalars()
        .all()
    }

    for record in indicator_records:
        summary.processed += 1
        existing = existing_by_external_id.get(record.external_id)
        indicator_type = record.attributes.get("indicator_type", "unknown")
        confidence = record.attributes.get("confidence", 0.5)

        if existing is None:
            session.add(
                ThreatIndicator(
                    tenant_id=tenant_id,
                    tenant_integration_id=tenant_integration_id,
                    external_id=record.external_id,
                    indicator_type=indicator_type,
                    value=record.identifier_value,
                    confidence=confidence,
                    source=provider_id,
                    first_seen_at=record.observed_at,
                    last_seen_at=record.observed_at,
                )
            )
            summary.created += 1
        else:
            existing.indicator_type = indicator_type
            existing.value = record.identifier_value
            existing.confidence = confidence
            existing.last_seen_at = record.observed_at
            summary.updated += 1

    await session.flush()
    return summary
