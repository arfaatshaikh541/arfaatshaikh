"""MetaConnector is a concrete configuration of RestApiConnector -- these
tests prove the configuration (paths, auth header, capability map, risk
tiers) is correct against a real local HTTP server shaped like Meta's
Graph API, not a mock of the connector's own methods.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aura_core.connectors import ConnectorRegistry, build_meta_connector
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine, RiskTier
from aura_core.status import CapabilityStatus


class _FakeMetaHandler(BaseHTTPRequestHandler):
    received_auth_header: str | None = None
    received_body: dict | None = None

    def do_GET(self):
        _FakeMetaHandler.received_auth_header = self.headers.get("Authorization")
        if self.path == "/me":
            self._respond(200, {"id": "page-123", "name": "Acme Widgets"})
        elif self.path == "/page-123/posts":
            self._respond(200, {"data": [{"id": "post-1", "message": "Hello world"}]})
        elif self.path == "/post-1/comments":
            self._respond(200, {"data": [{"id": "comment-1", "message": "Nice!"}]})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        _FakeMetaHandler.received_auth_header = self.headers.get("Authorization")
        length = int(self.headers.get("Content-Length", 0))
        _FakeMetaHandler.received_body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/page-123/feed":
            self._respond(200, {"id": "post-2"})
        elif self.path == "/comment-1/comments":
            self._respond(200, {"id": "comment-2"})
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
def fake_meta():
    server = HTTPServer(("127.0.0.1", 0), _FakeMetaHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/meta.db"
    policy = PolicyEngine(db_url)
    risk = RiskEngine()
    broker = ActionBroker(policy, risk, ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    return broker, policy, risk


def test_health_check_without_a_token_is_honestly_ready_to_connect_not_live():
    connector = build_meta_connector(token=None)
    assert connector.health_check().status == CapabilityStatus.READY_TO_CONNECT


def test_health_check_with_a_token_makes_a_real_call(fake_meta):
    connector = build_meta_connector(token="fake-page-token", base_url=fake_meta)
    result = connector.health_check()

    assert result.status == CapabilityStatus.LIVE
    assert _FakeMetaHandler.received_auth_header == "Bearer fake-page-token"


def test_get_page_posts_returns_real_data_through_the_broker(tmp_path, fake_meta):
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("meta.get_page_posts", 4)
    ConnectorRegistry(broker).register(build_meta_connector(token="tok", base_url=fake_meta))

    outcome = broker.submit(ActionRequest(action_type="meta.get_page_posts", params={"page_id": "page-123"}))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert json.loads(outcome.message)["data"][0]["message"] == "Hello world"


def test_publish_post_sends_the_real_body_and_is_amber_tier(tmp_path, fake_meta):
    broker, policy, risk = make_broker(tmp_path)
    assert risk.classify(ActionRequest(action_type="meta.publish_post")).tier == RiskTier.AMBER

    policy.set_autonomy_level("meta.publish_post", 4)
    ConnectorRegistry(broker).register(build_meta_connector(token="tok", base_url=fake_meta))

    outcome = broker.submit(ActionRequest(
        action_type="meta.publish_post", params={"page_id": "page-123", "body": {"message": "Announcing!"}},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert _FakeMetaHandler.received_body == {"message": "Announcing!"}


def test_read_only_capabilities_are_green_tier(tmp_path):
    _broker, _policy, risk = make_broker(tmp_path)
    for action_type in ["meta.get_page_posts", "meta.get_post_comments"]:
        assert risk.classify(ActionRequest(action_type=action_type)).tier == RiskTier.GREEN


def test_a_write_at_autonomy_level_zero_is_denied_by_default(tmp_path, fake_meta):
    broker, _policy, _risk = make_broker(tmp_path)
    ConnectorRegistry(broker).register(build_meta_connector(token="tok", base_url=fake_meta))

    outcome = broker.submit(ActionRequest(
        action_type="meta.publish_post", params={"page_id": "page-123", "body": {"message": "should not post"}},
    ))

    assert outcome.status == OutcomeStatus.DENIED
