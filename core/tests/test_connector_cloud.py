from __future__ import annotations

import json

from aura_core.connectors import CloudConnector, ConnectorRegistry, MockCloudProvider
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine, RiskTier
from aura_core.status import CapabilityStatus


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/cloud.db"
    policy = PolicyEngine(db_url)
    risk = RiskEngine()
    broker = ActionBroker(policy, risk, ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    return broker, policy, risk


def test_mock_provider_health_check_is_honestly_ready_to_connect_not_live():
    connector = CloudConnector(MockCloudProvider())
    assert connector.health_check().status == CapabilityStatus.READY_TO_CONNECT


def test_deploy_and_rollback_are_amber_get_status_is_green(tmp_path):
    _broker, _policy, risk = make_broker(tmp_path)
    assert risk.classify(ActionRequest(action_type="cloud.deploy")).tier == RiskTier.AMBER
    assert risk.classify(ActionRequest(action_type="cloud.rollback")).tier == RiskTier.AMBER
    assert risk.classify(ActionRequest(action_type="cloud.get_deployment_status")).tier == RiskTier.GREEN


def test_deploy_is_denied_by_default_fails_closed(tmp_path):
    broker, _policy, _risk = make_broker(tmp_path)  # no autonomy level set -> level 0
    provider = MockCloudProvider()
    ConnectorRegistry(broker).register(CloudConnector(provider))

    outcome = broker.submit(ActionRequest(
        action_type="cloud.deploy", params={"service": "web", "version": "1.2.3"},
    ))

    assert outcome.status == OutcomeStatus.DENIED  # level 0 default -- fails closed
    assert provider.deployments == {}  # never reached the provider


def test_a_real_deploy_actually_executes_through_the_broker_once_authorized(tmp_path):
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("cloud.deploy", 4)
    ConnectorRegistry(broker).register(CloudConnector(MockCloudProvider()))

    outcome = broker.submit(ActionRequest(
        action_type="cloud.deploy", params={"service": "web", "version": "1.2.3"},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    body = json.loads(outcome.message)
    assert body["service"] == "web"
    assert body["version"] == "1.2.3"
    assert body["status"] == "live"
    assert body["environment"] == "production"  # default
    assert body["previous_deployment_id"] is None
    assert body["provider"] == "mock"


def test_deploying_a_new_version_records_the_previous_deployment_id(tmp_path):
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("cloud.deploy", 4)
    ConnectorRegistry(broker).register(CloudConnector(MockCloudProvider()))

    first = json.loads(broker.submit(ActionRequest(
        action_type="cloud.deploy", params={"service": "web", "version": "1.0.0"},
    )).message)
    second = json.loads(broker.submit(ActionRequest(
        action_type="cloud.deploy", params={"service": "web", "version": "2.0.0"},
    )).message)

    assert second["previous_deployment_id"] == first["id"]


def test_a_real_rollback_restores_the_previous_deployment_to_live(tmp_path):
    """Proves rollback is genuine state management, not just a label
    change on the record being rolled back."""
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("cloud.deploy", 4)
    policy.set_autonomy_level("cloud.rollback", 4)
    policy.set_autonomy_level("cloud.get_deployment_status", 4)
    provider = MockCloudProvider()
    ConnectorRegistry(broker).register(CloudConnector(provider))

    first = json.loads(broker.submit(ActionRequest(
        action_type="cloud.deploy", params={"service": "web", "version": "1.0.0"},
    )).message)
    second = json.loads(broker.submit(ActionRequest(
        action_type="cloud.deploy", params={"service": "web", "version": "2.0.0"},
    )).message)

    rollback_outcome = broker.submit(ActionRequest(
        action_type="cloud.rollback", params={"deployment_id": second["id"]},
    ))
    assert rollback_outcome.status == OutcomeStatus.EXECUTED
    rolled_back = json.loads(rollback_outcome.message)
    assert rolled_back["status"] == "rolled_back"

    first_status = json.loads(broker.submit(ActionRequest(
        action_type="cloud.get_deployment_status", params={"deployment_id": first["id"]},
    )).message)
    assert first_status["status"] == "live"


def test_rolling_back_an_unknown_deployment_is_reported_honestly_not_as_executed(tmp_path):
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("cloud.rollback", 4)
    ConnectorRegistry(broker).register(CloudConnector(MockCloudProvider()))

    outcome = broker.submit(ActionRequest(
        action_type="cloud.rollback", params={"deployment_id": "does-not-exist"},
    ))

    assert outcome.status == OutcomeStatus.DENIED
    assert "DEGRADED" in outcome.message
