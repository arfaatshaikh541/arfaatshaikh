"""The backend half of section 8's "always-listening, privacy-visible
status" requirement: a real cross-process way for the voice host to
report its VoiceSessionController state and for any local client (a
future tray icon, `aura status`, or this endpoint directly) to read it,
closing the audit's flagged gap ("no visible indicator anywhere, console
log only"). The WPF tray icon UI itself remains REQUIRES_WINDOWS_RUNTIME
-- this is only the state-exposure API, which is what's IMPLEMENTABLE_NOW.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def test_voice_state_is_unknown_before_any_voice_host_has_reported():
    client = TestClient(create_app(load_settings()))

    response = client.get("/voice/state")

    assert response.status_code == 200
    assert response.json()["state"] == "UNKNOWN"


def test_a_reported_state_is_readable_back():
    client = TestClient(create_app(load_settings()))

    post_response = client.post("/voice/state", json={"state": "ListeningForWake"})
    assert post_response.status_code == 200

    get_response = client.get("/voice/state")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["state"] == "ListeningForWake"
    assert "reported_at" in body


def test_every_real_voice_session_state_is_accepted():
    client = TestClient(create_app(load_settings()))

    for state in ["Idle", "ListeningForWake", "Awake", "Processing", "Speaking"]:
        response = client.post("/voice/state", json={"state": state})
        assert response.status_code == 200, state
        assert client.get("/voice/state").json()["state"] == state


def test_an_unrecognized_state_is_rejected():
    client = TestClient(create_app(load_settings()))

    response = client.post("/voice/state", json={"state": "TotallyMadeUp"})

    assert response.status_code == 422


def test_reporting_state_requires_a_device_token_once_enrolled():
    app = create_app(load_settings())
    app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    response = client.post("/voice/state", json={"state": "Awake"})

    assert response.status_code == 401


def test_reading_state_never_requires_a_token_even_after_enrollment():
    app = create_app(load_settings())
    app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    response = client.get("/voice/state")

    assert response.status_code == 200
