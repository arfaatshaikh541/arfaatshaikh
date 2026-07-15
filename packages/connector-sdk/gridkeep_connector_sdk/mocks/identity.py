"""SIMULATOR connector — development and demonstration only. Never
presented as real protection; excluded from the production integration
catalogue (see modules.integrations.service.list_catalog)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from gridkeep_connector_sdk.base import (
    ActionSpec,
    Connector,
    ConnectorDefinition,
    HealthCheckResult,
    NormalizedRecord,
    SyncMode,
)


def _now() -> datetime:
    return datetime.now(UTC)


class MockIdentityConnector(Connector):
    definition = ConnectorDefinition(
        provider_id="mock_identity",
        name="Simulated Identity Provider",
        category="identity_provider",
        auth_method="api_key",
        required_scopes=("directory.read",),
        permission_risk="read_only",
        supported_data_types=("identity.user",),
        supported_actions=(
            ActionSpec(key="revoke_session", name="Revoke session", safety_class=1, reversible=True),
            ActionSpec(key="disable_user", name="Disable user", safety_class=2, reversible=True),
        ),
        sync_modes=("full",),
        webhook_support=False,
        is_simulator=True,
        description="Deterministic fake identity directory for local development and demos.",
    )

    async def authenticate(self) -> bool:
        return bool(self.credential_plaintext)

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(healthy=True, message="Simulated identity provider reachable.")

    async def sync(self, *, mode: SyncMode = "full") -> AsyncIterator[NormalizedRecord]:
        now = _now()
        users = [
            {
                "external_id": "mock-user-001",
                "email": "amara.owner@example-tenant.local",
                "display_name": "Amara Osei",
                "is_admin": True,
                "mfa_enabled": False,  # demo scenario: administrator without MFA
                "last_sign_in_at": (now - timedelta(hours=3)).isoformat(),
            },
            {
                "external_id": "mock-user-002",
                "email": "farid.secadmin@example-tenant.local",
                "display_name": "Farid Haddad",
                "is_admin": True,
                "mfa_enabled": True,
                "last_sign_in_at": (now - timedelta(hours=6)).isoformat(),
            },
            {
                "external_id": "mock-user-003",
                "email": "former.employee@example-tenant.local",
                "display_name": "Former Employee",
                "is_admin": False,
                "mfa_enabled": True,
                "last_sign_in_at": (now - timedelta(days=145)).isoformat(),  # demo scenario: dormant
            },
        ]
        for user in users:
            yield NormalizedRecord(
                record_type="identity.user",
                external_id=user["external_id"],
                identifier_type="email",
                identifier_value=user["email"],
                display_name=user["display_name"],
                attributes={
                    "is_admin": user["is_admin"],
                    "mfa_enabled": user["mfa_enabled"],
                    "last_sign_in_at": user["last_sign_in_at"],
                },
                raw=user,
                observed_at=now,
            )
