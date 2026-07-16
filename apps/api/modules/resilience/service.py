"""Recovery Confidence — a read-only rollup over the existing asset graph.

Deliberately has no models of its own: a `backup_job` is just an `Asset`
(as produced by a backup-platform connector, e.g. `mock_backup`), so this
module is pure aggregation, not a new system of record. This mirrors
`modules.findings.scoring`'s "simple, explainable, linear" approach: the
per-job score starts at 100 and takes a fixed deduction for each of three
independent risk factors (last run didn't succeed, no immutability
protection, no recent-enough run) — it is not a sophisticated backup
maturity model, and refining it is reasonable future work.

The tenant-wide `recovery_confidence_score` is the average of per-job
scores, `None` when the tenant has no backup jobs yet (nothing to
score, distinct from "everything is broken").
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.assets.models import Asset, AssetType
from modules.findings.rules import BACKUP_STALE_THRESHOLD

_LAST_RUN_NOT_SUCCESS_PENALTY = 50
_NOT_IMMUTABLE_PENALTY = 30
_STALE_PENALTY = 20


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _score_job(attributes: dict) -> tuple[int, bool]:
    score = 100
    if attributes.get("last_run_status") != "success":
        score -= _LAST_RUN_NOT_SUCCESS_PENALTY
    if attributes.get("immutable") is not True:
        score -= _NOT_IMMUTABLE_PENALTY

    last_run_at = _parse_timestamp(attributes.get("last_run_at"))
    is_stale = last_run_at is None or (datetime.now(UTC) - last_run_at) > BACKUP_STALE_THRESHOLD
    if is_stale:
        score -= _STALE_PENALTY

    return max(0, score), is_stale


async def get_resilience_summary(session: AsyncSession, *, tenant_id: uuid.UUID) -> dict:
    rows = (
        await session.execute(
            select(Asset)
            .join(AssetType, AssetType.id == Asset.asset_type_id)
            .where(Asset.tenant_id == tenant_id, AssetType.key == "backup_job")
        )
    ).scalars().all()

    jobs = []
    immutable_count = 0
    stale_count = 0
    failed_count = 0
    for asset in rows:
        attributes = asset.attributes
        score, is_stale = _score_job(attributes)
        if attributes.get("immutable") is True:
            immutable_count += 1
        if is_stale:
            stale_count += 1
        if attributes.get("last_run_status") != "success":
            failed_count += 1
        jobs.append(
            {
                "asset_id": asset.id,
                "job_name": asset.display_name,
                "last_run_status": attributes.get("last_run_status"),
                "last_run_at": _parse_timestamp(attributes.get("last_run_at")),
                "immutable": attributes.get("immutable"),
                "is_stale": is_stale,
                "score": score,
            }
        )

    recovery_confidence_score = round(sum(j["score"] for j in jobs) / len(jobs)) if jobs else None

    return {
        "recovery_confidence_score": recovery_confidence_score,
        "backup_job_total": len(jobs),
        "backup_jobs_immutable": immutable_count,
        "backup_jobs_stale": stale_count,
        "backup_jobs_failed": failed_count,
        "jobs": jobs,
    }
