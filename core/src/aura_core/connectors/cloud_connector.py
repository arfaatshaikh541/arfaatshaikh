"""Cloud/deployment connector -- interface only until a real provider
(AWS/GCP/Azure/Fly.io/etc.) is chosen and authorized. Building the
concrete adapter for a specific cloud is REQUIRES_EXTERNAL_PROVIDER
(which cloud) + REQUIRES_OWNER_CREDENTIAL (its API key); the provider
abstraction and the deploy/rollback state machine around it are
IMPLEMENTABLE_NOW and built here. MockCloudProvider deploys and rolls
back against an in-memory deployment ledger only -- no real
infrastructure is ever touched -- so the Action Broker/policy/audit
pipeline can be exercised for real today, the same "interface now, real
backend later" shape as MockPaymentProvider/MockTelephonyProvider.
"""
from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..governance.action_broker import ActionRequest, HandlerResult
from ..status import CapabilityStatus
from .base import Connector, ConnectorManifest


class DeploymentNotFoundError(RuntimeError):
    pass


@dataclass
class Deployment:
    id: str
    service: str
    version: str
    environment: str
    status: str  # "live" | "rolled_back"
    deployed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    previous_deployment_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "service": self.service, "version": self.version,
            "environment": self.environment, "status": self.status,
            "deployed_at": self.deployed_at.isoformat(), "previous_deployment_id": self.previous_deployment_id,
        }


class CloudProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def deploy(self, *, service: str, version: str, environment: str) -> Deployment: ...

    @abstractmethod
    def rollback(self, *, deployment_id: str) -> Deployment: ...

    @abstractmethod
    def get_status(self, *, deployment_id: str) -> Deployment: ...


class MockCloudProvider(CloudProvider):
    """No real cloud account involved. Tracks, per (service, environment),
    which deployment is currently live, so a rollback genuinely restores
    the previous version's status -- not just a label change on the
    rolled-back record."""

    def __init__(self) -> None:
        self.deployments: dict[str, Deployment] = {}
        self._live_by_service_env: dict[tuple[str, str], str] = {}

    def is_available(self) -> bool:
        return True

    def deploy(self, *, service: str, version: str, environment: str) -> Deployment:
        key = (service, environment)
        previous_id = self._live_by_service_env.get(key)
        deployment = Deployment(
            id=str(uuid.uuid4()), service=service, version=version,
            environment=environment, status="live", previous_deployment_id=previous_id,
        )
        self.deployments[deployment.id] = deployment
        self._live_by_service_env[key] = deployment.id
        return deployment

    def rollback(self, *, deployment_id: str) -> Deployment:
        deployment = self.deployments.get(deployment_id)
        if deployment is None:
            raise DeploymentNotFoundError(f"no deployment '{deployment_id}'")

        deployment.status = "rolled_back"
        key = (deployment.service, deployment.environment)
        if deployment.previous_deployment_id and deployment.previous_deployment_id in self.deployments:
            previous = self.deployments[deployment.previous_deployment_id]
            previous.status = "live"
            self._live_by_service_env[key] = previous.id
        else:
            self._live_by_service_env.pop(key, None)
        return deployment

    def get_status(self, *, deployment_id: str) -> Deployment:
        deployment = self.deployments.get(deployment_id)
        if deployment is None:
            raise DeploymentNotFoundError(f"no deployment '{deployment_id}'")
        return deployment


class CloudConnector(Connector):
    def __init__(self, provider: CloudProvider) -> None:
        self._provider = provider
        is_mock = isinstance(provider, MockCloudProvider)
        self.manifest = ConnectorManifest(
            name="cloud",
            auth_method="none" if is_mock else "custom",
            required_credentials=[] if is_mock else ["cloud_provider_api_key"],
            capabilities=["cloud.deploy", "cloud.rollback", "cloud.get_deployment_status"],
            notes=(
                "mock provider (in-memory deployment ledger, no real infrastructure)"
                if is_mock else "real backend"
            ),
        )

    def health_check(self) -> HandlerResult:
        if self._provider.is_available():
            status = CapabilityStatus.LIVE if isinstance(self._provider, MockCloudProvider) else CapabilityStatus.READY_TO_CONNECT
            return HandlerResult(status, "provider reports available")
        return HandlerResult(CapabilityStatus.UNAVAILABLE, "provider reports unavailable")

    def deploy(self, request: ActionRequest) -> HandlerResult:
        deployment = self._provider.deploy(
            service=request.params["service"], version=request.params["version"],
            environment=request.params.get("environment", "production"),
        )
        return HandlerResult(CapabilityStatus.LIVE, json.dumps(deployment.to_dict()))

    def rollback(self, request: ActionRequest) -> HandlerResult:
        try:
            deployment = self._provider.rollback(deployment_id=request.params["deployment_id"])
        except DeploymentNotFoundError as exc:
            return HandlerResult(CapabilityStatus.DEGRADED, str(exc))
        return HandlerResult(CapabilityStatus.LIVE, json.dumps(deployment.to_dict()))

    def get_status(self, request: ActionRequest) -> HandlerResult:
        try:
            deployment = self._provider.get_status(deployment_id=request.params["deployment_id"])
        except DeploymentNotFoundError as exc:
            return HandlerResult(CapabilityStatus.DEGRADED, str(exc))
        return HandlerResult(CapabilityStatus.LIVE, json.dumps(deployment.to_dict()))

    def handlers(self) -> dict:
        return {
            "cloud.deploy": self.deploy,
            "cloud.rollback": self.rollback,
            "cloud.get_deployment_status": self.get_status,
        }
