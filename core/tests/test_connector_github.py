"""GitHubConnector is a concrete configuration of RestApiConnector, not
a reimplementation -- these tests exist to prove the configuration
(paths, auth header, capability map) is actually correct against
GitHub's real REST API shape, using a real local HTTP server that
returns responses shaped like GitHub's, not a mock of the connector's
own methods."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aura_core.connectors import ConnectorRegistry, build_github_connector
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine, RiskTier
from aura_core.status import CapabilityStatus


class _FakeGitHubHandler(BaseHTTPRequestHandler):
    received_auth_header: str | None = None
    received_path: str | None = None
    received_body: dict | None = None

    def do_GET(self):
        _FakeGitHubHandler.received_auth_header = self.headers.get("Authorization")
        _FakeGitHubHandler.received_path = self.path
        if self.path == "/":
            self._respond(200, {"current_user_url": "https://api.github.com/user"})
        elif self.path == "/repos/acme/widgets/pulls":
            self._respond(200, [{"number": 42, "title": "Fix the widget", "state": "open"}])
        elif self.path == "/repos/acme/widgets/pulls/42":
            self._respond(200, {"number": 42, "title": "Fix the widget", "mergeable": True})
        elif self.path == "/repos/acme/widgets/issues":
            self._respond(200, [{"number": 7, "title": "Widget is broken"}])
        elif self.path == "/repos/acme/widgets/commits/abc123/status":
            self._respond(200, {"state": "success", "total_count": 3})
        else:
            self._respond(404, {"message": "Not Found"})

    def do_POST(self):
        _FakeGitHubHandler.received_auth_header = self.headers.get("Authorization")
        _FakeGitHubHandler.received_path = self.path
        length = int(self.headers.get("Content-Length", 0))
        _FakeGitHubHandler.received_body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/repos/acme/widgets/issues/7/comments":
            self._respond(201, {"id": 999, "body": _FakeGitHubHandler.received_body.get("body")})
        else:
            self._respond(404, {"message": "Not Found"})

    def _respond(self, status: int, payload) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_github():
    server = HTTPServer(("127.0.0.1", 0), _FakeGitHubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/github.db"
    policy = PolicyEngine(db_url)
    risk = RiskEngine()
    broker = ActionBroker(policy, risk, ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    return broker, policy, risk


def test_health_check_without_a_token_is_honestly_ready_to_connect_not_live():
    connector = build_github_connector(token=None)
    result = connector.health_check()
    assert result.status == CapabilityStatus.READY_TO_CONNECT


def test_health_check_with_a_token_makes_a_real_call(fake_github):
    connector = build_github_connector(token="fake-test-token", base_url=fake_github)
    result = connector.health_check()

    assert result.status == CapabilityStatus.LIVE
    assert _FakeGitHubHandler.received_auth_header == "Bearer fake-test-token"


def test_list_pull_requests_returns_real_data_through_the_broker(tmp_path, fake_github):
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("github.list_pull_requests", 4)
    connector = build_github_connector(token="tok", base_url=fake_github)
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="github.list_pull_requests", params={"owner": "acme", "repo": "widgets"},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    body = json.loads(outcome.message)
    assert body == [{"number": 42, "title": "Fix the widget", "state": "open"}]


def test_get_pull_request_fills_the_path_template_correctly(tmp_path, fake_github):
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("github.get_pull_request", 4)
    connector = build_github_connector(token="tok", base_url=fake_github)
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="github.get_pull_request", params={"owner": "acme", "repo": "widgets", "number": 42},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert json.loads(outcome.message)["mergeable"] is True


def test_get_combined_status_reads_real_build_status(tmp_path, fake_github):
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("github.get_combined_status", 4)
    connector = build_github_connector(token="tok", base_url=fake_github)
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="github.get_combined_status",
        params={"owner": "acme", "repo": "widgets", "ref": "abc123"},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert json.loads(outcome.message)["state"] == "success"


def test_comment_on_issue_posts_the_real_body_and_is_amber_tier(tmp_path, fake_github):
    broker, policy, risk = make_broker(tmp_path)

    classification = risk.classify(ActionRequest(action_type="github.comment_on_issue"))
    assert classification.tier == RiskTier.AMBER  # a public, visible write -- never GREEN

    policy.set_autonomy_level("github.comment_on_issue", 4)
    connector = build_github_connector(token="tok", base_url=fake_github)
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="github.comment_on_issue",
        params={"owner": "acme", "repo": "widgets", "number": 7, "body": {"body": "Looking into this now."}},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert _FakeGitHubHandler.received_body == {"body": "Looking into this now."}


def test_read_only_capabilities_are_green_tier(tmp_path):
    _broker, _policy, risk = make_broker(tmp_path)
    for action_type in ["github.list_pull_requests", "github.get_pull_request", "github.list_issues", "github.get_issue", "github.get_combined_status"]:
        assert risk.classify(ActionRequest(action_type=action_type)).tier == RiskTier.GREEN


def test_a_write_at_autonomy_level_zero_is_denied_by_default(tmp_path, fake_github):
    """No autonomy level configured -- fails safe to DENY, exactly like
    every other connector in this project."""
    broker, _policy, _risk = make_broker(tmp_path)
    connector = build_github_connector(token="tok", base_url=fake_github)
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="github.comment_on_issue",
        params={"owner": "acme", "repo": "widgets", "number": 7, "body": {"body": "should not be posted"}},
    ))

    assert outcome.status == OutcomeStatus.DENIED
