"""WhatsAppConnector is a concrete configuration of RestApiConnector --
these tests prove the configuration (paths, auth header, capability map,
risk tiers) is correct against a real local HTTP server shaped like
Meta's WhatsApp Cloud API, not a mock of the connector's own methods.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aura_core.connectors import ConnectorRegistry, build_whatsapp_connector
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine, RiskTier
from aura_core.status import CapabilityStatus


class _FakeWhatsAppHandler(BaseHTTPRequestHandler):
    received_auth_header: str | None = None
    received_body: dict | None = None

    def do_GET(self):
        _FakeWhatsAppHandler.received_auth_header = self.headers.get("Authorization")
        if self.path in ("/", "/phone-123"):
            self._respond(200, {"id": "phone-123", "verified_name": "Acme Support"})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        _FakeWhatsAppHandler.received_auth_header = self.headers.get("Authorization")
        length = int(self.headers.get("Content-Length", 0))
        _FakeWhatsAppHandler.received_body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/phone-123/messages":
            self._respond(200, {"messages": [{"id": "wamid.123"}]})
        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, status: int, payload) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_whatsapp():
    server = HTTPServer(("127.0.0.1", 0), _FakeWhatsAppHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/whatsapp.db"
    policy = PolicyEngine(db_url)
    risk = RiskEngine()
    broker = ActionBroker(policy, risk, ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    return broker, policy, risk


def test_health_check_without_a_token_is_honestly_ready_to_connect_not_live():
    connector = build_whatsapp_connector(token=None)
    assert connector.health_check().status == CapabilityStatus.READY_TO_CONNECT


def test_health_check_with_a_token_makes_a_real_call(fake_whatsapp):
    connector = build_whatsapp_connector(token="fake-waba-token", base_url=fake_whatsapp)
    result = connector.health_check()

    assert result.status == CapabilityStatus.LIVE
    assert _FakeWhatsAppHandler.received_auth_header == "Bearer fake-waba-token"


def test_send_message_posts_the_real_body_and_is_amber_tier(tmp_path, fake_whatsapp):
    broker, policy, risk = make_broker(tmp_path)
    assert risk.classify(ActionRequest(action_type="whatsapp.send_message")).tier == RiskTier.AMBER

    policy.set_autonomy_level("whatsapp.send_message", 4)
    ConnectorRegistry(broker).register(build_whatsapp_connector(token="tok", base_url=fake_whatsapp))

    outcome = broker.submit(ActionRequest(
        action_type="whatsapp.send_message",
        params={
            "phone_number_id": "phone-123",
            "body": {"messaging_product": "whatsapp", "to": "15551234567", "type": "text", "text": {"body": "Hi!"}},
        },
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert json.loads(outcome.message)["messages"][0]["id"] == "wamid.123"
    assert _FakeWhatsAppHandler.received_body["text"]["body"] == "Hi!"


def test_get_phone_number_status_is_green_tier(tmp_path, fake_whatsapp):
    broker, policy, risk = make_broker(tmp_path)
    assert risk.classify(ActionRequest(action_type="whatsapp.get_phone_number_status")).tier == RiskTier.GREEN

    policy.set_autonomy_level("whatsapp.get_phone_number_status", 4)
    ConnectorRegistry(broker).register(build_whatsapp_connector(token="tok", base_url=fake_whatsapp))

    outcome = broker.submit(ActionRequest(
        action_type="whatsapp.get_phone_number_status", params={"phone_number_id": "phone-123"},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert json.loads(outcome.message)["verified_name"] == "Acme Support"


def test_a_write_at_autonomy_level_zero_is_denied_by_default(tmp_path, fake_whatsapp):
    broker, _policy, _risk = make_broker(tmp_path)
    ConnectorRegistry(broker).register(build_whatsapp_connector(token="tok", base_url=fake_whatsapp))

    outcome = broker.submit(ActionRequest(
        action_type="whatsapp.send_message",
        params={"phone_number_id": "phone-123", "body": {"to": "15551234567", "text": {"body": "should not send"}}},
    ))

    assert outcome.status == OutcomeStatus.DENIED
