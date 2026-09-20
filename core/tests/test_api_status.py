from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def test_health_endpoint():
    client = TestClient(create_app(load_settings()))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_endpoint_reports_real_capability_states():
    client = TestClient(create_app(load_settings()))
    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()

    # memory.store and api.server must be LIVE once the app has actually
    # started and connected — never fabricated regardless of these two.
    assert body["memory.store"]["status"] == "LIVE"

    # Capabilities this build doesn't implement must say so honestly.
    assert body["voice.wake_word"]["status"] == "NOT_CONNECTED"
    assert body["windows.native_shell"]["status"] == "NOT_CONNECTED"


def test_commitments_endpoint_starts_empty():
    client = TestClient(create_app(load_settings()))
    response = client.get("/commitments")
    assert response.status_code == 200
    assert response.json() == []
