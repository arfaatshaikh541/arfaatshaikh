from __future__ import annotations

import base64
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aura_core.connectors import ConnectorRegistry
from aura_core.connectors.browser_connector import BrowserConnector
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine
from aura_core.status import CapabilityStatus

# This build environment's pre-installed Chromium revision doesn't match
# what the `playwright` pip package resolves to by default (confirmed by
# trying) -- AURA_PLAYWRIGHT_EXECUTABLE lets tests point at the real
# binary directly rather than skipping browser tests entirely.
_EXECUTABLE = os.environ.get(
    "AURA_PLAYWRIGHT_EXECUTABLE",
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
)
_HAS_BROWSER = os.path.exists(_EXECUTABLE)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><head><title>AURA Test Page</title></head>"
                          b"<body><h1>Hello from a real local page</h1></body></html>")

    def log_message(self, *args):
        pass


@pytest.fixture
def local_page_url():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/browser.db"
    policy = PolicyEngine(db_url)
    broker = ActionBroker(policy, RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    return broker, policy


@pytest.mark.skipif(not _HAS_BROWSER, reason="no compatible Chromium binary in this environment")
def test_browser_health_check_launches_a_real_browser():
    connector = BrowserConnector(executable_path=_EXECUTABLE)
    result = connector.health_check()
    assert result.status == CapabilityStatus.LIVE


@pytest.mark.skipif(not _HAS_BROWSER, reason="no compatible Chromium binary in this environment")
def test_browser_navigate_returns_the_real_page_title(tmp_path, local_page_url):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.navigate", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE)
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(action_type="browser.navigate", params={"url": local_page_url}))
    assert outcome.status == OutcomeStatus.EXECUTED
    assert outcome.message == "AURA Test Page"


@pytest.mark.skipif(not _HAS_BROWSER, reason="no compatible Chromium binary in this environment")
def test_browser_extract_text_reads_the_real_dom(tmp_path, local_page_url):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.extract_text", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE)
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="browser.extract_text", params={"url": local_page_url, "selector": "h1"},
    ))
    assert outcome.status == OutcomeStatus.EXECUTED
    assert outcome.message == "Hello from a real local page"


@pytest.mark.skipif(not _HAS_BROWSER, reason="no compatible Chromium binary in this environment")
def test_browser_screenshot_returns_real_nonempty_png_bytes(tmp_path, local_page_url):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.screenshot", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE)
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(action_type="browser.screenshot", params={"url": local_page_url}))
    assert outcome.status == OutcomeStatus.EXECUTED
    png_bytes = base64.b64decode(outcome.message)
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"  # real PNG magic bytes, not a placeholder
    assert len(png_bytes) > 1000


@pytest.mark.skipif(not _HAS_BROWSER, reason="no compatible Chromium binary in this environment")
def test_browser_denies_navigation_outside_allowlist(tmp_path, local_page_url):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.navigate", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE, allowed_hosts=["only-this-host.example"])
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(action_type="browser.navigate", params={"url": local_page_url}))
    assert outcome.status == OutcomeStatus.DENIED
    assert "not on the browser egress allowlist" in outcome.message
