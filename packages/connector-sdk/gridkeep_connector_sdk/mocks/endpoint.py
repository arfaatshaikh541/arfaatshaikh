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


class MockEndpointConnector(Connector):
    definition = ConnectorDefinition(
        provider_id="mock_endpoint",
        name="Simulated Endpoint Platform",
        category="endpoint_platform",
        auth_method="api_key",
        required_scopes=("devices.read",),
        permission_risk="read_only",
        supported_data_types=("endpoint.device",),
        supported_actions=(
            ActionSpec(key="isolate_endpoint", name="Isolate endpoint", safety_class=2, reversible=True),
            ActionSpec(key="request_scan", name="Request malware scan", safety_class=1, reversible=True),
        ),
        sync_modes=("full",),
        webhook_support=False,
        is_simulator=True,
        description="Deterministic fake device inventory for local development and demos.",
    )

    async def authenticate(self) -> bool:
        return bool(self.credential_plaintext)

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(healthy=True, message="Simulated endpoint platform reachable.")

    async def sync(self, *, mode: SyncMode = "full") -> AsyncIterator[NormalizedRecord]:
        now = _now()
        devices = [
            {
                "external_id": "mock-device-001",
                "hostname": "fin-laptop-07.example-tenant.local",
                "os": "macOS 14.5",
                "encrypted": True,
                "edr_status": "healthy",
                "last_seen_at": (now - timedelta(minutes=12)).isoformat(),
            },
            {
                "external_id": "mock-device-002",
                "hostname": "hr-laptop-03.example-tenant.local",
                "os": "Windows 11",
                "encrypted": False,  # demo scenario: unencrypted endpoint
                "edr_status": "healthy",
                "last_seen_at": (now - timedelta(minutes=40)).isoformat(),
            },
            {
                "external_id": "mock-device-003",
                "hostname": "sales-laptop-11.example-tenant.local",
                "os": "Windows 10",
                "encrypted": True,
                "edr_status": "unresponsive",
                "last_seen_at": (now - timedelta(days=9)).isoformat(),  # demo scenario: lost/stale device
                # demo scenario: this stale, EDR-unresponsive device also
                # last communicated with a known-malicious IP (matches
                # mock_threat_intel's mock-ioc-001) — a realistic
                # combination of independent risk signals converging on
                # one asset.
                "last_known_public_ip": "203.0.113.55",
            },
        ]
        for device in devices:
            yield NormalizedRecord(
                record_type="endpoint.device",
                external_id=device["external_id"],
                identifier_type="hostname",
                identifier_value=device["hostname"],
                display_name=device["hostname"],
                attributes={
                    "os": device["os"],
                    "encrypted": device["encrypted"],
                    "edr_status": device["edr_status"],
                    "last_seen_at": device["last_seen_at"],
                    **(
                        {"last_known_public_ip": device["last_known_public_ip"]}
                        if "last_known_public_ip" in device
                        else {}
                    ),
                },
                raw=device,
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
        if action_key == "isolate_endpoint":
            return ActionResult(success=True, message=f"Isolated {target_identifier_value} from the network.")
        if action_key == "request_scan":
            return ActionResult(success=True, message=f"Requested a malware scan on {target_identifier_value}.")
        raise ActionNotSupportedError(action_key)
