from __future__ import annotations

import base64
import json
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


class _CaptchaHandler(BaseHTTPRequestHandler):
    """A real local page shaped like a genuine reCAPTCHA-gated page --
    the actual DOM structure sites use, not a fake flag the connector
    could special-case."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><head><title>Verify you are human</title></head>"
            b"<body><h1>Please verify you are human</h1>"
            b'<div class="g-recaptcha" data-sitekey="fake-key-for-a-real-local-test-page"></div>'
            b"</body></html>"
        )

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


class _CookieHandler(BaseHTTPRequestHandler):
    """Sets a cookie on the first request with no Cookie header, and
    always reflects whatever Cookie header it did receive in the page
    title -- a real way to prove a cookie set by one browser launch was
    actually sent back by a *later, separate* browser launch, which is
    exactly what "persistent profile" has to mean given this connector
    launches a fresh browser process per action."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        if "Cookie" not in self.headers:
            # Max-Age is essential here: a session cookie (no Max-Age/
            # Expires) is correctly discarded by a real browser on a
            # genuine restart -- real login sessions are persistent
            # cookies with an expiry, so this is the honest shape to test
            # against, not a workaround for a connector bug.
            self.send_header("Set-Cookie", "aura_session=abc123; Path=/; Max-Age=3600")
        cookie_value = self.headers.get("Cookie", "none")
        self.end_headers()
        self.wfile.write(f"<html><head><title>cookie:{cookie_value}</title></head><body></body></html>".encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def local_cookie_page_url():
    server = HTTPServer(("127.0.0.1", 0), _CookieHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()


@pytest.fixture
def local_captcha_page_url():
    server = HTTPServer(("127.0.0.1", 0), _CaptchaHandler)
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


@pytest.mark.skipif(not _HAS_BROWSER, reason="no compatible Chromium binary in this environment")
def test_browser_escalates_a_real_captcha_page_instead_of_extracting_it(tmp_path, local_captcha_page_url):
    """The product spec is explicit: never attempt to bypass a CAPTCHA,
    escalate to the owner. Verified against a real local page with a
    real reCAPTCHA-shaped DOM node -- not a connector-side flag standing
    in for actual detection."""
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.extract_text", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE)
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="browser.extract_text", params={"url": local_captcha_page_url, "selector": "h1"},
    ))

    assert outcome.status == OutcomeStatus.DENIED
    assert "CAPTCHA detected" in outcome.message
    assert "escalating to the owner" in outcome.message


@pytest.mark.skipif(not _HAS_BROWSER, reason="no compatible Chromium binary in this environment")
def test_browser_captcha_detection_also_blocks_navigate_and_screenshot(tmp_path, local_captcha_page_url):
    """The check lives in the one shared _with_page() path all three
    capabilities go through -- proven here by exercising the other two,
    not just extract_text."""
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.navigate", 4)
    policy.set_autonomy_level("browser.screenshot", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE)
    ConnectorRegistry(broker).register(connector)

    navigate_outcome = broker.submit(ActionRequest(action_type="browser.navigate", params={"url": local_captcha_page_url}))
    screenshot_outcome = broker.submit(ActionRequest(action_type="browser.screenshot", params={"url": local_captcha_page_url}))

    assert navigate_outcome.status == OutcomeStatus.DENIED
    assert "CAPTCHA detected" in navigate_outcome.message
    assert screenshot_outcome.status == OutcomeStatus.DENIED
    assert "CAPTCHA detected" in screenshot_outcome.message


@pytest.mark.skipif(not _HAS_BROWSER, reason="no compatible Chromium binary in this environment")
def test_browser_does_not_false_positive_on_an_ordinary_page(tmp_path, local_page_url):
    """The conservative, containment-based selectors must not fire on a
    page with no CAPTCHA at all -- otherwise every real navigation would
    be wrongly escalated."""
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.navigate", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE)
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(action_type="browser.navigate", params={"url": local_page_url}))

    assert outcome.status == OutcomeStatus.EXECUTED


@pytest.mark.skipif(not _HAS_BROWSER, reason="no compatible Chromium binary in this environment")
def test_without_a_profile_dir_a_cookie_does_not_survive_a_new_browser_launch(tmp_path, local_cookie_page_url):
    """The contrast case: proves the *default* (no persistent profile)
    genuinely starts fresh every time, so the persistent-profile test
    below is proving something real, not something that would pass
    regardless."""
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.navigate", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE)
    ConnectorRegistry(broker).register(connector)

    first = broker.submit(ActionRequest(action_type="browser.navigate", params={"url": local_cookie_page_url}))
    second = broker.submit(ActionRequest(action_type="browser.navigate", params={"url": local_cookie_page_url}))

    assert first.message == "cookie:none"
    assert second.message == "cookie:none"  # no profile -- the cookie from the first launch is gone


@pytest.mark.skipif(not _HAS_BROWSER, reason="no compatible Chromium binary in this environment")
def test_a_persistent_profile_carries_a_cookie_across_separate_browser_launches(tmp_path, local_cookie_page_url):
    """The actual "persistent authenticated profiles" proof: a real
    cookie set by one launched-and-closed browser process is sent back
    by a *second, separate* browser process pointed at the same on-disk
    profile directory -- the same shape a real login session takes."""
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.navigate", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE, profile_dir=str(tmp_path / "profile"))
    ConnectorRegistry(broker).register(connector)

    first = broker.submit(ActionRequest(action_type="browser.navigate", params={"url": local_cookie_page_url}))
    second = broker.submit(ActionRequest(action_type="browser.navigate", params={"url": local_cookie_page_url}))

    assert first.message == "cookie:none"
    assert second.message == "cookie:aura_session=abc123"


@pytest.mark.skipif(not _HAS_BROWSER, reason="no compatible Chromium binary in this environment")
def test_extract_text_multi_drives_genuinely_separate_tabs_in_one_call(tmp_path, local_page_url, local_captcha_page_url):
    """Real multi-tab operation: two different pages, opened as two
    Pages within one shared browser context in a single action, each
    handled and reported independently -- a CAPTCHA on one must not
    sink or block the result for the other."""
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.extract_text_multi", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE)
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="browser.extract_text_multi",
        params={"targets": [
            {"url": local_page_url, "selector": "h1"},
            {"url": local_captcha_page_url, "selector": "h1"},
        ]},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    results = json.loads(outcome.message)
    assert len(results) == 2
    assert results[0]["url"] == local_page_url
    assert results[0]["text"] == "Hello from a real local page"
    assert results[1]["url"] == local_captcha_page_url
    assert "CAPTCHA detected" in results[1]["error"]


@pytest.mark.skipif(not _HAS_BROWSER, reason="no compatible Chromium binary in this environment")
def test_extract_text_multi_is_denied_if_any_target_is_outside_the_allowlist(tmp_path, local_page_url):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.extract_text_multi", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE, allowed_hosts=["only-this-host.example"])
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="browser.extract_text_multi",
        params={"targets": [{"url": local_page_url}]},
    ))
    assert outcome.status == OutcomeStatus.DENIED
    assert "not on the browser egress allowlist" in outcome.message


class _DownloadHandler(BaseHTTPRequestHandler):
    """A real local page with a genuine link-triggered download, plus a
    second URL that serves the file directly with a Content-Disposition
    header -- the two shapes download_file supports (click a trigger vs.
    a direct download link)."""

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b'<html><body><a id="dl" href="/report.txt" download>Download report</a></body></html>'
            )
        elif self.path == "/report.txt":
            body = b"quarterly report contents"
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="report.txt"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def download_page_url():
    server = HTTPServer(("127.0.0.1", 0), _DownloadHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()


@pytest.mark.skipif(not _HAS_BROWSER, reason="no compatible Chromium binary in this environment")
def test_download_file_via_a_trigger_selector_saves_the_real_content(tmp_path, download_page_url):
    download_dir = tmp_path / "downloads"
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.download_file", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE, download_dir=str(download_dir))
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="browser.download_file",
        params={"url": download_page_url, "trigger_selector": "#dl", "save_as": "saved-report.txt"},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    result = json.loads(outcome.message)
    saved_path = download_dir / "saved-report.txt"
    assert result["saved_to"] == str(saved_path)
    assert saved_path.read_bytes() == b"quarterly report contents"


@pytest.mark.skipif(not _HAS_BROWSER, reason="no compatible Chromium binary in this environment")
def test_download_file_with_a_direct_url_and_no_selector_also_works(tmp_path, download_page_url):
    download_dir = tmp_path / "downloads"
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.download_file", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE, download_dir=str(download_dir))
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="browser.download_file",
        params={"url": download_page_url + "report.txt", "save_as": "direct.txt"},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert (download_dir / "direct.txt").read_bytes() == b"quarterly report contents"


def test_download_file_is_denied_honestly_with_no_download_directory_configured(tmp_path):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.download_file", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE)  # no download_dir
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="browser.download_file",
        params={"url": "http://example.test/f.txt", "save_as": "f.txt"},
    ))

    assert outcome.status == OutcomeStatus.DENIED
    assert "no download directory configured" in outcome.message


def test_download_file_rejects_a_save_as_that_escapes_the_download_directory(tmp_path):
    download_dir = tmp_path / "downloads"
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("browser.download_file", 4)
    connector = BrowserConnector(executable_path=_EXECUTABLE, download_dir=str(download_dir))
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="browser.download_file",
        params={"url": "http://example.test/f.txt", "save_as": "../../etc/evil.txt"},
    ))

    assert outcome.status == OutcomeStatus.DENIED
    assert "escapes the configured download directory" in outcome.message


def test_download_file_is_amber_tier(tmp_path):
    _broker, _policy = make_broker(tmp_path)
    assert RiskEngine().classify(ActionRequest(action_type="browser.download_file")).tier.value == "AMBER"


def test_download_file_is_denied_by_default_at_autonomy_zero(tmp_path):
    download_dir = tmp_path / "downloads"
    broker, _policy = make_broker(tmp_path)
    connector = BrowserConnector(executable_path=_EXECUTABLE, download_dir=str(download_dir))
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="browser.download_file",
        params={"url": "http://example.test/f.txt", "save_as": "f.txt"},
    ))

    assert outcome.status == OutcomeStatus.DENIED
    assert "autonomy level 0" in outcome.message
