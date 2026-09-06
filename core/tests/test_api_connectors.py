from __future__ import annotations

import os

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings

# See test_connector_browser.py: this build environment's pre-installed
# Chromium revision doesn't match what the `playwright` pip package
# resolves to by default.
_EXECUTABLE = os.environ.get(
    "AURA_PLAYWRIGHT_EXECUTABLE",
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
)
_HAS_BROWSER = os.path.exists(_EXECUTABLE)


def test_connectors_endpoint_reports_filesystem_and_telephony_live():
    client = TestClient(create_app(load_settings()))
    response = client.get("/connectors")
    assert response.status_code == 200
    body = {c["name"]: c for c in response.json()}
    assert body["filesystem"]["status"]["status"] == "LIVE"
    assert body["telephony"]["status"]["status"] == "LIVE"


def test_connectors_endpoint_does_not_crash_on_a_real_health_check_that_uses_playwrights_sync_api(monkeypatch):
    """Regression test: BrowserConnector.health_check() launches a real
    browser via Playwright's *sync* API, which raises outright if called
    from a thread that already has an asyncio event loop running --
    exactly the thread FastAPI's own async request handler runs on. The
    /connectors endpoint used to call runtime.connectors.refresh_all()
    directly inside `async def list_connectors()`, so every single call
    after the first (which happens during build_runtime(), before any
    event loop exists) crashed with "Playwright Sync API inside the
    asyncio loop" instead of reporting an honest status. Fixed by running
    the health-check sweep in FastAPI's thread pool. This test hits the
    real endpoint through TestClient's real ASGI request handling (a
    genuine running event loop), not a direct method call, since that's
    the only way this bug reproduces at all."""
    if not _HAS_BROWSER:
        import pytest
        pytest.skip(f"no browser binary at {_EXECUTABLE} in this environment")

    monkeypatch.setenv("AURA_PLAYWRIGHT_EXECUTABLE", _EXECUTABLE)
    client = TestClient(create_app(load_settings()))

    response = client.get("/connectors")
    assert response.status_code == 200
    body = {c["name"]: c for c in response.json()}
    browser_status = body["browser"]["status"]
    assert "asyncio loop" not in browser_status["detail"]
    assert browser_status["status"] == "LIVE"
