from __future__ import annotations

from aura_core.connectors import ConnectorRegistry
from aura_core.connectors.finance_connector import FinanceConnector, MockPaymentProvider, PaymentProvider, TransactionDraft
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine, RiskTier
from aura_core.status import CapabilityStatus


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/finance.db"
    policy = PolicyEngine(db_url)
    risk = RiskEngine()
    broker = ActionBroker(policy, risk, ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    return broker, policy, risk


def test_mock_provider_health_check_is_honestly_ready_to_connect_not_live():
    connector = FinanceConnector(MockPaymentProvider())
    assert connector.health_check().status == CapabilityStatus.READY_TO_CONNECT


def test_prepare_transaction_is_amber_and_requires_approval_by_default(tmp_path):
    broker, _policy, _risk = make_broker(tmp_path)  # no autonomy level set -> level 0
    provider = MockPaymentProvider()
    ConnectorRegistry(broker).register(FinanceConnector(provider))

    outcome = broker.submit(ActionRequest(
        action_type="finance.prepare_transaction",
        params={"amount": 500, "currency": "USD", "recipient": "acme-vendor"},
    ))

    assert outcome.status == OutcomeStatus.DENIED  # level 0 default -- fails closed
    assert provider.drafts == []  # never reached the provider -- no real or fake funds moved


def test_prepare_transaction_is_classified_amber_never_below(tmp_path):
    _broker, _policy, risk = make_broker(tmp_path)
    classification = risk.classify(ActionRequest(action_type="finance.prepare_transaction"))
    assert classification.tier == RiskTier.AMBER


def test_prepare_transaction_executes_once_authorized_and_only_ever_drafts(tmp_path):
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("finance.prepare_transaction", 4)
    provider = MockPaymentProvider()
    ConnectorRegistry(broker).register(FinanceConnector(provider))

    outcome = broker.submit(ActionRequest(
        action_type="finance.prepare_transaction",
        params={"amount": 250.50, "currency": "AED", "recipient": "acme-vendor", "memo": "October retainer"},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert len(provider.drafts) == 1
    draft = provider.drafts[0]
    assert draft.amount == 250.50
    assert draft.currency == "AED"
    assert draft.recipient == "acme-vendor"
    assert draft.status == "drafted"  # this connector has no other status -- no real money ever moves


def test_finance_connector_has_no_handler_for_actually_executing_a_transfer():
    """Interfaces-only per the owner's explicit scope decision: this
    connector can only ever produce a draft, never move real funds --
    verified structurally by checking the handler map itself, not just
    by testing the one handler that exists."""
    connector = FinanceConnector(MockPaymentProvider())
    assert set(connector.handlers().keys()) == {"finance.prepare_transaction"}


def test_manifest_reflects_credential_requirements_for_a_real_backend():
    class FakeRealProvider(PaymentProvider):
        """Stands in for a real payment provider without needing one --
        implements the interface directly so the connector's is_mock
        check is exercised honestly."""

        def is_available(self) -> bool:
            return True

        def prepare_transaction(self, *, amount, currency, recipient, memo) -> TransactionDraft:
            raise NotImplementedError("not used in this test")

    connector = FinanceConnector(FakeRealProvider())
    assert connector.manifest.auth_method == "custom"
    assert "payment_provider_api_key" in connector.manifest.required_credentials
