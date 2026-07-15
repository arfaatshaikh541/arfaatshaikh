"""SIMULATOR connector — development and demonstration only."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from gridkeep_connector_sdk.base import (
    ActionNotSupportedError,
    ActionResult,
    ActionSpec,
    Connector,
    ConnectorDefinition,
    HealthCheckResult,
    NormalizedRecord,
    RelationshipRecord,
    SyncMode,
)


def _now() -> datetime:
    return datetime.now(UTC)


class MockCloudConnector(Connector):
    definition = ConnectorDefinition(
        provider_id="mock_cloud",
        name="Simulated Cloud Provider",
        category="cloud_provider",
        auth_method="service_account",
        required_scopes=("resources.read",),
        permission_risk="read_only",
        supported_data_types=("cloud.account", "cloud.resource"),
        supported_actions=(
            ActionSpec(
                key="disable_public_sharing", name="Disable public sharing", safety_class=2, reversible=True
            ),
        ),
        sync_modes=("full",),
        webhook_support=False,
        is_simulator=True,
        description="Deterministic fake cloud account/resource inventory for local development and demos.",
    )

    async def authenticate(self) -> bool:
        return bool(self.credential_plaintext)

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(healthy=True, message="Simulated cloud provider reachable.")

    async def sync(self, *, mode: SyncMode = "full") -> AsyncIterator[NormalizedRecord]:
        now = _now()

        account_id = "mock-cloud-account-001"
        yield NormalizedRecord(
            record_type="cloud.account",
            external_id=account_id,
            identifier_type="cloud_account_id",
            identifier_value=account_id,
            display_name="Simulated Production Cloud Account",
            attributes={"provider": "simulated", "region": "me-central-1"},
            raw={"account_id": account_id},
            observed_at=now,
        )

        resources = [
            {
                "external_id": "mock-bucket-001",
                "resource_id": "mock-bucket-001",
                "resource_type": "storage_bucket",
                "public_access": True,  # demo scenario: exposed cloud storage
            },
            {
                "external_id": "mock-db-001",
                "resource_id": "mock-db-001",
                "resource_type": "database",
                "public_access": False,
            },
        ]
        for resource in resources:
            yield NormalizedRecord(
                record_type="cloud.resource",
                external_id=resource["external_id"],
                identifier_type="cloud_resource_id",
                identifier_value=resource["resource_id"],
                display_name=resource["resource_id"],
                attributes={
                    "resource_type": resource["resource_type"],
                    "public_access": resource["public_access"],
                },
                raw=resource,
                observed_at=now,
                relationships=(
                    RelationshipRecord(
                        relationship_type="belongs_to",
                        target_identifier_type="cloud_account_id",
                        target_identifier_value=account_id,
                    ),
                ),
            )

    async def execute_action(
        self,
        action_key: str,
        *,
        target_identifier_type: str,
        target_identifier_value: str,
        params: dict | None = None,
    ) -> ActionResult:
        if action_key == "disable_public_sharing":
            return ActionResult(
                success=True, message=f"Disabled public access on {target_identifier_value}."
            )
        raise ActionNotSupportedError(action_key)
