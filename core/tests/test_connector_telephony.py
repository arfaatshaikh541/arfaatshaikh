from __future__ import annotations

from aura_core.connectors import ConnectorRegistry
from aura_core.connectors.telephony_connector import CallRecord, MockTelephonyProvider, TelephonyConnector, TelephonyProvider
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine
from aura_core.status import CapabilityStatus


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/telephony.db"
    policy = PolicyEngine(db_url)
    broker = ActionBroker(policy, RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    return broker, policy


def test_mock_provider_health_check_is_live():
    connector = TelephonyConnector(MockTelephonyProvider())
    assert connector.health_check().status == CapabilityStatus.LIVE


def test_telephony_call_is_amber_and_requires_approval_by_default(tmp_path):
    broker, _policy = make_broker(tmp_path)  # no autonomy level set -> level 0
    provider = MockTelephonyProvider()
    ConnectorRegistry(broker).register(TelephonyConnector(provider))

    outcome = broker.submit(ActionRequest(action_type="telephony.call", params={"to": "+15551234567", "message": "hi"}))

    assert outcome.status == OutcomeStatus.DENIED  # level 0 default -- fails closed
    assert provider.calls == []  # never reached the provider


def test_telephony_call_executes_once_authorized_and_is_recorded(tmp_path):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("telephony.call", 4)
    provider = MockTelephonyProvider()
    ConnectorRegistry(broker).register(TelephonyConnector(provider, from_number="+19998887777"))

    outcome = broker.submit(ActionRequest(
        action_type="telephony.call", params={"to": "+15551234567", "message": "Your appointment is confirmed."},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call.to == "+15551234567"
    assert call.from_ == "+19998887777"
    assert call.message == "Your appointment is confirmed."


def test_manifest_reflects_credential_requirements_for_a_real_backend():
    class FakeRealProvider(TelephonyProvider):
        """Stands in for a real backend (Twilio/SIP) without needing
        one — implements the interface directly rather than subclassing
        MockTelephonyProvider, so the connector's is_mock check (which
        distinguishes "no real calls possible" from "a real backend that
        needs credentials") is exercised honestly."""

        def is_available(self) -> bool:
            return True

        def place_call(self, *, to: str, from_: str, message: str) -> CallRecord:
            raise NotImplementedError("not used in this test")

    connector = TelephonyConnector(FakeRealProvider())
    assert connector.manifest.auth_method == "custom"
    assert "account_sid" in connector.manifest.required_credentials
