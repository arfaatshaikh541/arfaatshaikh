from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aura_core.connectors import ConnectorRegistry
from aura_core.connectors.rest_connector import RestApiConnector, RestCapability
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine
from aura_core.status import CapabilityStatus


class _FakeCrmHandler(BaseHTTPRequestHandler):
    received_auth_header: str | None = None
    received_body: dict | None = None

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        _FakeCrmHandler.received_auth_header = self.headers.get("Authorization")
        length = int(self.headers.get("Content-Length", 0))
        _FakeCrmHandler.received_body = json.loads(self.rfile.read(length) or b"{}")
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"id": "contact-123"}).encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_crm():
    server = HTTPServer(("127.0.0.1", 0), _FakeCrmHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/rest.db"
    policy = PolicyEngine(db_url)
    broker = ActionBroker(policy, RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    return broker, policy


def test_health_check_reports_ready_to_connect_without_an_api_key(fake_crm):
    connector = RestApiConnector(
        "crm", fake_crm, {"crm.write": RestCapability("POST", "/contacts")}, health_path="/health",
    )
    assert connector.health_check().status == CapabilityStatus.READY_TO_CONNECT


def test_health_check_is_live_once_configured(fake_crm):
    connector = RestApiConnector(
        "crm", fake_crm, {"crm.write": RestCapability("POST", "/contacts")},
        api_key="secret-key", health_path="/health",
    )
    assert connector.health_check().status == CapabilityStatus.LIVE


def test_post_action_reaches_the_real_fake_crm_with_auth_header_and_body(tmp_path, fake_crm):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("crm.write", 4)
    connector = RestApiConnector(
        "crm", fake_crm, {"crm.write": RestCapability("POST", "/contacts")},
        api_key="secret-key", health_path="/health",
    )
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="crm.write", params={"body": {"name": "Ahmed", "email": "ahmed@example.test"}},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert "contact-123" in outcome.message
    assert _FakeCrmHandler.received_auth_header == "Bearer secret-key"
    assert _FakeCrmHandler.received_body == {"name": "Ahmed", "email": "ahmed@example.test"}


def test_path_template_fills_from_params(tmp_path, fake_crm):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("crm.update_contact", 4)
    connector = RestApiConnector(
        "crm", fake_crm,
        {"crm.update_contact": RestCapability("POST", "/contacts/{contact_id}")},
        api_key="secret-key",
    )
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="crm.update_contact", params={"contact_id": "42", "body": {"status": "customer"}},
    ))
    assert outcome.status == OutcomeStatus.EXECUTED


def test_missing_path_param_reported_honestly(tmp_path, fake_crm):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("crm.update_contact", 4)
    connector = RestApiConnector(
        "crm", fake_crm,
        {"crm.update_contact": RestCapability("POST", "/contacts/{contact_id}")},
        api_key="secret-key",
    )
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(action_type="crm.update_contact", params={"body": {}}))
    assert outcome.status == OutcomeStatus.DENIED
    assert "missing required param" in outcome.message
