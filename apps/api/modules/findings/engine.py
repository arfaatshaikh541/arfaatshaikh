"""The correlation engine — runs every rule in `modules.findings.rules`
against a tenant's current asset graph and reconciles the result against
existing `Finding` rows. Idempotent and lifecycle-aware: see the module
docstring on `run_correlation` for exactly what re-running does to a
finding in each possible state.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.assets.models import Asset, AssetType
from modules.audit import service as audit_service
from modules.findings.models import ACTIVE_STATUSES, Finding
from modules.findings.rules import RULES_BY_ASSET_TYPE

_ENGINE_ACTOR_LABEL = "correlation_engine"


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class CorrelationSummary:
    evaluated_assets: int = 0
    created: int = 0
    updated: int = 0
    reopened: int = 0
    auto_resolved: int = 0
    accepted_risk_expired: int = 0


async def run_correlation(session: AsyncSession, *, tenant_id: uuid.UUID) -> CorrelationSummary:
    """Re-running against unchanged asset state is a no-op beyond
    refreshing `last_observed_at`/`evidence` on already-open findings —
    it never creates duplicates (dedup_key is unique per tenant) and
    never overrides a human decision:

    - No existing finding for a matching rule/asset pair -> create one,
      status "open".
    - Existing finding still matching, status open/assigned -> refresh
      evidence, leave status alone.
    - Existing finding still matching, status accepted_risk -> refresh
      evidence unless the acceptance has expired, in which case reopen
      it (status back to "open").
    - Existing finding still matching, status remediated/resolved -> the
      underlying condition came back; reopen it.
    - Existing finding still matching, status false_positive -> leave it
      alone permanently; a human said this doesn't count.
    - Existing finding NOT matching any more, status open/assigned/
      accepted_risk -> auto-resolve it (the condition cleared).
    - Existing finding NOT matching any more, status remediated/
      false_positive -> leave it alone; already a closed/dismissed state.
    """
    summary = CorrelationSummary()
    now = _now()

    assets = (
        await session.execute(
            select(Asset, AssetType.key)
            .join(AssetType, AssetType.id == Asset.asset_type_id)
            .where(Asset.tenant_id == tenant_id)
        )
    ).all()

    existing_findings: dict[str, Finding] = {
        f.dedup_key: f
        for f in (await session.execute(select(Finding).where(Finding.tenant_id == tenant_id)))
        .scalars()
        .all()
    }
    matched_dedup_keys: set[str] = set()

    for asset, asset_type_key in assets:
        summary.evaluated_assets += 1
        for rule in RULES_BY_ASSET_TYPE.get(asset_type_key, ()):
            evidence = rule.evaluate(asset.attributes)
            if evidence is None:
                continue

            dedup_key = f"{rule.key}:{asset.id}"
            matched_dedup_keys.add(dedup_key)
            existing = existing_findings.get(dedup_key)

            if existing is None:
                finding = Finding(
                    tenant_id=tenant_id,
                    rule_key=rule.key,
                    dedup_key=dedup_key,
                    title=rule.title,
                    description=rule.description,
                    category=rule.category,
                    severity=rule.severity,
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
                    context={"rule_key": rule.key, "asset_id": str(asset.id)},
                )
                continue

            existing.evidence = evidence
            existing.last_observed_at = now

            if existing.status == "false_positive":
                continue  # a human dismissed this permanently — the engine never overrides that.

            if existing.status == "accepted_risk":
                if existing.accepted_risk_expires_at is not None and existing.accepted_risk_expires_at <= now:
                    existing.status = "open"
                    existing.accepted_risk_expires_at = None
                    existing.closed_at = None
                    summary.accepted_risk_expired += 1
                    await audit_service.record(
                        session,
                        tenant_id=tenant_id,
                        actor_user_id=None,
                        actor_label=_ENGINE_ACTOR_LABEL,
                        action="findings.accept_risk_expired",
                        target_type="finding",
                        target_id=str(existing.id),
                    )
                else:
                    summary.updated += 1
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

            summary.updated += 1  # status in ("open", "assigned") — still active, nothing to transition.

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
