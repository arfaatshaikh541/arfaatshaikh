from __future__ import annotations

from aura_core.connectors import ConnectorRegistry, FilesystemConnector, HttpConnector
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine
from aura_core.status import CapabilityStatus, registry as status_registry


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/connectors.db"
    policy = PolicyEngine(db_url)
    broker = ActionBroker(policy, RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    return broker, policy


# -- Filesystem -----------------------------------------------------------

def test_filesystem_health_check_is_live_for_an_existing_root(tmp_path):
    connector = FilesystemConnector(str(tmp_path / "sandbox"))
    result = connector.health_check()
    assert result.status == CapabilityStatus.LIVE


def test_filesystem_write_then_read_round_trip(tmp_path):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("filesystem.write_file", 4)
    policy.set_autonomy_level("filesystem.read_file", 4)
    connector = FilesystemConnector(str(tmp_path / "sandbox"))
    ConnectorRegistry(broker).register(connector)

    write_outcome = broker.submit(ActionRequest(
        action_type="filesystem.write_file", params={"path": "notes.txt", "content": "hello aura"},
    ))
    assert write_outcome.status == OutcomeStatus.EXECUTED

    read_outcome = broker.submit(ActionRequest(action_type="filesystem.read_file", params={"path": "notes.txt"}))
    assert read_outcome.status == OutcomeStatus.EXECUTED
    assert read_outcome.message == "hello aura"


def test_filesystem_blocks_path_traversal_outside_the_sandbox(tmp_path):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("filesystem.read_file", 4)
    connector = FilesystemConnector(str(tmp_path / "sandbox"))
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(action_type="filesystem.read_file", params={"path": "../../etc/passwd"}))
    assert outcome.status == OutcomeStatus.DENIED
    assert "BLOCKED_BY_POLICY" in outcome.message


def test_filesystem_list_dir_reflects_real_writes(tmp_path):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("filesystem.write_file", 4)
    policy.set_autonomy_level("filesystem.list_dir", 4)
    connector = FilesystemConnector(str(tmp_path / "sandbox"))
    ConnectorRegistry(broker).register(connector)

    broker.submit(ActionRequest(action_type="filesystem.write_file", params={"path": "a.txt", "content": "x"}))
    broker.submit(ActionRequest(action_type="filesystem.write_file", params={"path": "b.txt", "content": "y"}))

    outcome = broker.submit(ActionRequest(action_type="filesystem.list_dir", params={}))
    assert outcome.status == OutcomeStatus.EXECUTED
    assert set(outcome.message.split("\n")) == {"a.txt", "b.txt"}


def test_connector_registry_publishes_health_into_status_registry(tmp_path):
    broker, _policy = make_broker(tmp_path)
    connector = FilesystemConnector(str(tmp_path / "sandbox"))
    ConnectorRegistry(broker).register(connector)

    record = status_registry.get("connector.filesystem")
    assert record is not None
    assert record.status == CapabilityStatus.LIVE


# -- HTTP -------------------------------------------------------------------

def test_http_health_check_blocked_with_no_allowlisted_hosts():
    connector = HttpConnector(allowed_hosts=[])
    result = connector.health_check()
    assert result.status == CapabilityStatus.BLOCKED_BY_POLICY


def test_http_get_denied_for_a_non_allowlisted_host(tmp_path):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("http.get", 4)
    connector = HttpConnector(allowed_hosts=["example.com"])
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(action_type="http.get", params={"url": "https://not-allowed.test/x"}))
    assert outcome.status == OutcomeStatus.DENIED
    assert "not on the egress allowlist" in outcome.message


def test_http_get_against_a_real_local_server(tmp_path):
    # Real HTTP over a real loopback server -- not mocked -- proving the
    # connector's actual httpx call path works, the same principle used
    # throughout this codebase (point real code at a real-but-local
    # target rather than mocking the method under test).
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"hello from test server")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        broker, policy = make_broker(tmp_path)
        policy.set_autonomy_level("http.get", 4)
        connector = HttpConnector(allowed_hosts=["127.0.0.1"])
        ConnectorRegistry(broker).register(connector)

        outcome = broker.submit(ActionRequest(action_type="http.get", params={"url": f"http://127.0.0.1:{port}/"}))
        assert outcome.status == OutcomeStatus.EXECUTED
        assert "hello from test server" in outcome.message
    finally:
        server.shutdown()
