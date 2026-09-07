"""LinkedInConnector is a concrete configuration of RestApiConnector --
these tests prove the configuration (paths, auth header, capability map,
risk tiers) is correct against a real local HTTP server shaped like
LinkedIn's REST API, not a mock of the connector's own methods.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aura_core.connectors import ConnectorRegistry, build_linkedin_connector
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine, RiskTier
from aura_core.status import CapabilityStatus


class _FakeLinkedInHandler(BaseHTTPRequestHandler):
    received_auth_header: str | None = None
    received_body: dict | None = None

    def do_GET(self):
        _FakeLinkedInHandler.received_auth_header = self.headers.get("Authorization")
        if self.path == "/me":
            self._respond(200, {"id": "member-123", "localizedFirstName": "Ada"})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        _FakeLinkedInHandler.received_auth_header = self.headers.get("Authorization")
        length = int(self.headers.get("Content-Length", 0))
        _FakeLinkedInHandler.received_body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/ugcPosts":
            self._respond(201, {"id": "urn:li:ugcPost:123"})
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
def fake_linkedin():
    server = HTTPServer(("127.0.0.1", 0), _FakeLinkedInHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/linkedin.db"
    policy = PolicyEngine(db_url)
    risk = RiskEngine()
    broker = ActionBroker(policy, risk, ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    return broker, policy, risk


def test_health_check_without_a_token_is_honestly_ready_to_connect_not_live():
    connector = build_linkedin_connector(token=None)
    assert connector.health_check().status == CapabilityStatus.READY_TO_CONNECT


def test_health_check_with_a_token_makes_a_real_call(fake_linkedin):
    connector = build_linkedin_connector(token="fake-oauth-token", base_url=fake_linkedin)
    result = connector.health_check()

    assert result.status == CapabilityStatus.LIVE
    assert _FakeLinkedInHandler.received_auth_header == "Bearer fake-oauth-token"


def test_get_profile_is_green_tier(tmp_path, fake_linkedin):
    broker, policy, risk = make_broker(tmp_path)
    assert risk.classify(ActionRequest(action_type="linkedin.get_profile")).tier == RiskTier.GREEN

    policy.set_autonomy_level("linkedin.get_profile", 4)
    ConnectorRegistry(broker).register(build_linkedin_connector(token="tok", base_url=fake_linkedin))

    outcome = broker.submit(ActionRequest(action_type="linkedin.get_profile", params={}))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert json.loads(outcome.message)["localizedFirstName"] == "Ada"


def test_share_post_sends_the_real_body_and_is_amber_tier(tmp_path, fake_linkedin):
    broker, policy, risk = make_broker(tmp_path)
    assert risk.classify(ActionRequest(action_type="linkedin.share_post")).tier == RiskTier.AMBER

    policy.set_autonomy_level("linkedin.share_post", 4)
    ConnectorRegistry(broker).register(build_linkedin_connector(token="tok", base_url=fake_linkedin))

    outcome = broker.submit(ActionRequest(
        action_type="linkedin.share_post",
        params={"body": {"author": "urn:li:person:member-123", "lifecycleState": "PUBLISHED"}},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert _FakeLinkedInHandler.received_body["author"] == "urn:li:person:member-123"


def test_a_write_at_autonomy_level_zero_is_denied_by_default(tmp_path, fake_linkedin):
    broker, _policy, _risk = make_broker(tmp_path)
    ConnectorRegistry(broker).register(build_linkedin_connector(token="tok", base_url=fake_linkedin))

    outcome = broker.submit(ActionRequest(
        action_type="linkedin.share_post", params={"body": {"author": "urn:li:person:member-123"}},
    ))

    assert outcome.status == OutcomeStatus.DENIED
