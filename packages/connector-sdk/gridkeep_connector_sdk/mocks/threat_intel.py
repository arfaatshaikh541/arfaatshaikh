"""SIMULATOR connector — development and demonstration only.

Yields threat-intelligence indicators rather than assets. Milestone 2's
asset-graph ingestion service intentionally does not persist these (no
`threat_intelligence` storage exists yet — that lands in Milestone 6);
this connector exists now so the catalogue and contract-test harness
cover all five Milestone-1-approved mock providers together."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from gridkeep_connector_sdk.base import (
    Connector,
    ConnectorDefinition,
    HealthCheckResult,
    NormalizedRecord,
    SyncMode,
)


def _now() -> datetime:
    return datetime.now(UTC)


class MockThreatIntelConnector(Connector):
    definition = ConnectorDefinition(
        provider_id="mock_threat_intel",
        name="Simulated Threat Intelligence Feed",
        category="threat_intelligence_feed",
        auth_method="api_key",
        required_scopes=("indicators.read",),
        permission_risk="read_only",
        supported_data_types=("threat_intel.indicator",),
        supported_actions=(),
        sync_modes=("full",),
        webhook_support=False,
        is_simulator=True,
        description="Deterministic fake indicator feed for local development and demos.",
    )

    async def authenticate(self) -> bool:
        return bool(self.credential_plaintext)

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(healthy=True, message="Simulated threat intelligence feed reachable.")

    async def sync(self, *, mode: SyncMode = "full") -> AsyncIterator[NormalizedRecord]:
        now = _now()
        indicators = [
            {
                "external_id": "mock-ioc-001",
                "value": "203.0.113.55",
                "indicator_type": "ip",
                "confidence": 0.8,
            },
            {
                "external_id": "mock-ioc-002",
                "value": "malicious-lookalike.example",
                "indicator_type": "domain",
                "confidence": 0.6,
            },
        ]
        for indicator in indicators:
            yield NormalizedRecord(
                record_type="threat_intel.indicator",
                external_id=indicator["external_id"],
                identifier_type="indicator_value",
                identifier_value=indicator["value"],
                display_name=indicator["value"],
                attributes={
                    "indicator_type": indicator["indicator_type"],
                    "confidence": indicator["confidence"],
                },
                raw=indicator,
                observed_at=now,
            )
