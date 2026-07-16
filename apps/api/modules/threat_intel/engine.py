"""Threat-intelligence correlation — cross-references stored
`ThreatIndicator` rows against every tenant asset's own attributes,
rather than evaluating one asset's attributes against a fixed rule (the
shape `modules.findings.engine` uses). This is a genuinely different
detection problem — "does this external threat feed's data show up
anywhere in what we discovered" — so it stays a separate engine that
writes into the same `Finding` table, not a new entry in
`modules.findings.rules.RULES`.

Reuses the exact create/update/reopen/auto-resolve lifecycle
`modules.findings.engine.run_correlation` established: re-running this
against unchanged data is a no-op beyond refreshing timestamps, and a
human's `false_positive`/dismissal decision is never overridden.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.assets.models import Asset
from modules.audit import service as audit_service
from modules.findings.models import ACTIVE_STATUSES, Finding
from modules.threat_intel.models import ThreatIndicator

RULE_KEY = "threat_intel_ioc_match"
_ENGINE_ACTOR_LABEL = "threat_intel_engine"

# A live match against a known indicator is treated as more serious than
# a static misconfiguration finding — this asset actually communicated
# with (or otherwise matched) something on a threat feed, not just a
# theoretical weakness. Thresholds are a judgment call, same category as
# the resilience/compliance scoring weights in Milestones 6-7.
_CRITICAL_CONFIDENCE = 0.7
_HIGH_CONFIDENCE = 0.4


def _now() -> datetime:
    return datetime.now(UTC)


def _severity_for_confidence(confidence: float) -> str:
    if confidence >= _CRITICAL_CONFIDENCE:
        return "critical"
    if confidence >= _HIGH_CONFIDENCE:
        return "high"
    return "medium"


@dataclass
class ThreatIntelCorrelationSummary:
    indicators_evaluated: int = 0
    assets_evaluated: int = 0
    created: int = 0
    updated: int = 0
    reopened: int = 0
    auto_resolved: int = 0


def _find_matching_attribute(asset: Asset, indicator_value: str) -> str | None:
    """Returns the attribute key whose value matches the indicator,
    case-insensitively, or None. Matching against every attribute value
    (rather than one fixed key like "ip_address") keeps this working
    across whatever shape of attributes any current or future connector
    happens to produce, without a schema change here."""
    needle = indicator_value.lower()
    for key, value in asset.attributes.items():
        if isinstance(value, str) and value.lower() == needle:
            return key
    return None


async def run_threat_intel_correlation(
    session: AsyncSession, *, tenant_id: uuid.UUID
) -> ThreatIntelCorrelationSummary:
    summary = ThreatIntelCorrelationSummary()
    now = _now()

    indicators = (
        await session.execute(select(ThreatIndicator).where(ThreatIndicator.tenant_id == tenant_id))
    ).scalars().all()
    assets = (await session.execute(select(Asset).where(Asset.tenant_id == tenant_id))).scalars().all()
    summary.indicators_evaluated = len(indicators)
    summary.assets_evaluated = len(assets)

    existing_findings = {
        f.dedup_key: f
        for f in (
            await session.execute(
                select(Finding).where(Finding.tenant_id == tenant_id, Finding.rule_key == RULE_KEY)
            )
        )
        .scalars()
        .all()
    }
    matched_dedup_keys: set[str] = set()

    for indicator in indicators:
        for asset in assets:
            matched_key = _find_matching_attribute(asset, indicator.value)
            if matched_key is None:
                continue

            dedup_key = f"{RULE_KEY}:{indicator.id}:{asset.id}"
            matched_dedup_keys.add(dedup_key)
            existing = existing_findings.get(dedup_key)
            evidence = {
                "indicator_id": str(indicator.id),
                "indicator_type": indicator.indicator_type,
                "indicator_value": indicator.value,
                "confidence": indicator.confidence,
                "source": indicator.source,
                "matched_attribute": matched_key,
            }
            severity = _severity_for_confidence(indicator.confidence)

            if existing is None:
                finding = Finding(
                    tenant_id=tenant_id,
                    rule_key=RULE_KEY,
                    dedup_key=dedup_key,
                    title=f"Asset matched a known threat indicator ({indicator.indicator_type})",
                    description=(
                        f"This asset's '{matched_key}' attribute matches a threat-intelligence "
                        f"indicator ({indicator.value}) from {indicator.source}."
                    ),
                    category="threat_intelligence",
                    severity=severity,
                    status="open",
                    asset_id=asset.id,
                    evidence=evidence,
                    first_observed_at=now,
                    last_observed_at=now,
                )
                session.add(finding)
                await session.flush()
                summary.created += 1
                await audit_service.record(
                    session,
                    tenant_id=tenant_id,
                    actor_user_id=None,
                    actor_label=_ENGINE_ACTOR_LABEL,
                    action="findings.detected",
                    target_type="finding",
                    target_id=str(finding.id),
                    context={"rule_key": RULE_KEY, "asset_id": str(asset.id)},
                )
                continue

            existing.evidence = evidence
            existing.severity = severity
            existing.last_observed_at = now

            if existing.status == "false_positive":
                continue
            if existing.status in ("remediated", "resolved"):
                existing.status = "open"
                existing.closed_at = None
                summary.reopened += 1
                await audit_service.record(
                    session,
                    tenant_id=tenant_id,
                    actor_user_id=None,
                    actor_label=_ENGINE_ACTOR_LABEL,
                    action="findings.reopened",
                    target_type="finding",
                    target_id=str(existing.id),
                    context={"reason": "condition_still_present"},
                )
                continue
            summary.updated += 1

    for dedup_key, finding in existing_findings.items():
        if dedup_key in matched_dedup_keys:
            continue
        if finding.status in ACTIVE_STATUSES:
            finding.status = "resolved"
            finding.closed_at = now
            summary.auto_resolved += 1
            await audit_service.record(
                session,
                tenant_id=tenant_id,
                actor_user_id=None,
                actor_label=_ENGINE_ACTOR_LABEL,
                action="findings.auto_resolved",
                target_type="finding",
                target_id=str(finding.id),
            )

    await session.flush()
    return summary
