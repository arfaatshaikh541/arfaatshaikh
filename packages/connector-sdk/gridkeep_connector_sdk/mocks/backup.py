"""SIMULATOR connector — development and demonstration only."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from gridkeep_connector_sdk.base import (
    ActionNotSupportedError,
    ActionResult,
    ActionSpec,
    Connector,
    ConnectorDefinition,
    HealthCheckResult,
    NormalizedRecord,
    SyncMode,
)


def _now() -> datetime:
    return datetime.now(UTC)


class MockBackupConnector(Connector):
    definition = ConnectorDefinition(
        provider_id="mock_backup",
        name="Simulated Backup Platform",
        category="backup_platform",
        auth_method="api_key",
        required_scopes=("jobs.read",),
        permission_risk="read_only",
        supported_data_types=("backup.job",),
        supported_actions=(
            ActionSpec(
                key="trigger_restore_test", name="Trigger restore test", safety_class=1, reversible=True
            ),
        ),
        sync_modes=("full",),
        webhook_support=False,
        is_simulator=True,
        description="Deterministic fake backup job inventory for local development and demos.",
    )

    async def authenticate(self) -> bool:
        return bool(self.credential_plaintext)

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(healthy=True, message="Simulated backup platform reachable.")

    async def sync(self, *, mode: SyncMode = "full") -> AsyncIterator[NormalizedRecord]:
        now = _now()
        jobs = [
            {
                "external_id": "mock-backup-job-001",
                "job_name": "nightly-file-server-backup",
                "last_run_status": "success",
                "last_run_at": (now - timedelta(hours=10)).isoformat(),
                "immutable": True,
            },
            {
                "external_id": "mock-backup-job-002",
                "job_name": "nightly-database-backup",
                "last_run_status": "failed",  # demo scenario: failed critical backup
                "last_run_at": (now - timedelta(hours=34)).isoformat(),
                "immutable": True,
            },
        ]
        for job in jobs:
            yield NormalizedRecord(
                record_type="backup.job",
                external_id=job["external_id"],
                identifier_type="backup_job_id",
                identifier_value=job["external_id"],
                display_name=job["job_name"],
                attributes={
                    "last_run_status": job["last_run_status"],
                    "last_run_at": job["last_run_at"],
                    "immutable": job["immutable"],
                },
                raw=job,
                observed_at=now,
            )

    async def execute_action(
        self,
        action_key: str,
        *,
        target_identifier_type: str,
        target_identifier_value: str,
        params: dict | None = None,
    ) -> ActionResult:
        if action_key == "trigger_restore_test":
            return ActionResult(
                success=True, message=f"Restore test triggered for {target_identifier_value}."
            )
        raise ActionNotSupportedError(action_key)
