"""InstagramConnector implements Meta's real two-step Graph API publish
flow (create a media container, then publish it) -- a genuinely different
shape from RestApiConnector's single-request-per-action_type model, so it
gets its own dedicated Connector subclass and its own fake server here,
shaped like the real two endpoints rather than a mock of the connector's
own methods.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aura_core.connectors import ConnectorRegistry, InstagramConnector
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine, RiskTier
from aura_core.status import CapabilityStatus


class _FakeInstagramHandler(BaseHTTPRequestHandler):
    received_auth_header: str | None = None
    received_bodies: list[dict] = []
    fail_publish: bool = False

    def do_GET(self):
        _FakeInstagramHandler.received_auth_header = self.headers.get("Authorization")
        if self.path == "/me":
            self._respond(200, {"id": "ig-user-1", "username": "acme"})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        _FakeInstagramHandler.received_auth_header = self.headers.get("Authorization")
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        _FakeInstagramHandler.received_bodies.append(body)

        if self.path == "/ig-user-1/media":
            self._respond(200, {"id": "creation-1"})
        elif self.path == "/ig-user-1/media_publish":
            if _FakeInstagramHandler.fail_publish:
                self._respond(400, {"error": "publish rejected"})
            else:
                self._respond(200, {"id": "media-1"})
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
def fake_instagram():
    _FakeInstagramHandler.received_bodies = []
    _FakeInstagramHandler.fail_publish = False
    server = HTTPServer(("127.0.0.1", 0), _FakeInstagramHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/instagram.db"
    policy = PolicyEngine(db_url)
    risk = RiskEngine()
    broker = ActionBroker(policy, risk, ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    return broker, policy, risk


def test_health_check_without_a_token_is_honestly_ready_to_connect_not_live():
    connector = InstagramConnector(token=None)
    assert connector.health_check().status == CapabilityStatus.READY_TO_CONNECT


def test_health_check_with_a_token_makes_a_real_call(fake_instagram):
    connector = InstagramConnector(token="fake-page-token", base_url=fake_instagram)
    result = connector.health_check()

    assert result.status == CapabilityStatus.LIVE
    assert _FakeInstagramHandler.received_auth_header == "Bearer fake-page-token"


def test_publish_post_does_the_real_two_step_flow_and_returns_the_final_media_id(tmp_path, fake_instagram):
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("instagram.publish_post", 4)
    ConnectorRegistry(broker).register(InstagramConnector(token="tok", base_url=fake_instagram))

    outcome = broker.submit(ActionRequest(
        action_type="instagram.publish_post",
        params={"ig_user_id": "ig-user-1", "image_url": "https://example.com/photo.jpg", "caption": "Launch day!"},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert json.loads(outcome.message)["id"] == "media-1"
    assert _FakeInstagramHandler.received_bodies == [
        {"image_url": "https://example.com/photo.jpg", "caption": "Launch day!"},
        {"creation_id": "creation-1"},
    ]


def test_publish_post_reports_a_publish_step_failure_honestly_with_the_creation_id(tmp_path, fake_instagram):
    _FakeInstagramHandler.fail_publish = True
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("instagram.publish_post", 4)
    ConnectorRegistry(broker).register(InstagramConnector(token="tok", base_url=fake_instagram))

    outcome = broker.submit(ActionRequest(
        action_type="instagram.publish_post",
        params={"ig_user_id": "ig-user-1", "image_url": "https://example.com/photo.jpg"},
    ))

    assert outcome.status == OutcomeStatus.DENIED
    assert "creation-1" in outcome.message
    assert "media_publish failed" in outcome.message


def test_publish_post_is_amber_tier():
    risk = RiskEngine()
    assert risk.classify(ActionRequest(action_type="instagram.publish_post")).tier == RiskTier.AMBER


def test_publish_post_is_denied_by_default_at_autonomy_zero(tmp_path, fake_instagram):
    broker, _policy, _risk = make_broker(tmp_path)
    ConnectorRegistry(broker).register(InstagramConnector(token="tok", base_url=fake_instagram))

    outcome = broker.submit(ActionRequest(
        action_type="instagram.publish_post",
        params={"ig_user_id": "ig-user-1", "image_url": "https://example.com/photo.jpg"},
    ))

    assert outcome.status == OutcomeStatus.DENIED
