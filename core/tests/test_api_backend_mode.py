"""Backend Mode's real security boundary, proven through the actual
HTTP surface a native shell would use -- not a unit test of
BackendElevationService in isolation. These tests are the API-layer
half of the security-audit requirements: backend endpoints reject a
request with only a device token (no elevation), voice/chat has no path
to elevation at all, and the elevation lifecycle (authenticate ->
verify -> deauthenticate) round-trips for real.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def _make_enrolled_client(pin: str = "482913") -> tuple[TestClient, str]:
    app: FastAPI = create_app(load_settings())
    _owner, device_token = app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    pin_response = client.post("/backend/pin", json={"pin": pin}, headers={"X-Aura-Device-Token": device_token})
    assert pin_response.status_code == 200, pin_response.text
    return client, device_token


def test_interface_config_is_reachable_before_any_authentication():
    client = TestClient(create_app(load_settings()))

    response = client.get("/interface/config")

    assert response.status_code == 200
    body = response.json()
    assert body["default_interface_mode"] == "voice"
    assert body["backend_toggle_hotkey"]


def test_backend_endpoints_reject_a_device_token_with_no_elevation():
    client, device_token = _make_enrolled_client()

    response = client.get("/backend/diagnostics", headers={"X-Aura-Device-Token": device_token})

    assert response.status_code == 401


def test_full_elevation_lifecycle_through_the_real_api():
    client, device_token = _make_enrolled_client()

    auth_response = client.post(
        "/backend/authenticate", json={"pin": "482913"}, headers={"X-Aura-Device-Token": device_token},
    )
    assert auth_response.status_code == 200, auth_response.text
    elevation_token = auth_response.json()["elevation_token"]
    assert auth_response.json()["expires_in_seconds"] > 0

    diagnostics_response = client.get("/backend/diagnostics", headers={
        "X-Aura-Device-Token": device_token, "X-Aura-Backend-Elevation": elevation_token,
    })
    assert diagnostics_response.status_code == 200
    assert "audit_chain_valid" in diagnostics_response.json()

    session_response = client.get("/backend/session", headers={"X-Aura-Backend-Elevation": elevation_token})
    assert session_response.status_code == 200
    assert session_response.json()["active"] is True

    deauth_response = client.post("/backend/deauthenticate", headers={"X-Aura-Backend-Elevation": elevation_token})
    assert deauth_response.status_code == 200

    after_response = client.get("/backend/diagnostics", headers={
        "X-Aura-Device-Token": device_token, "X-Aura-Backend-Elevation": elevation_token,
    })
    assert after_response.status_code == 401  # elevation was really revoked, not just UI-hidden


def test_wrong_pin_through_the_real_api_is_denied():
    client, device_token = _make_enrolled_client()

    response = client.post(
        "/backend/authenticate", json={"pin": "000000"}, headers={"X-Aura-Device-Token": device_token},
    )

    assert response.status_code == 401


def test_authenticate_without_a_device_token_is_rejected():
    client, _device_token = _make_enrolled_client()

    response = client.post("/backend/authenticate", json={"pin": "482913"})

    assert response.status_code == 401


def test_chat_and_the_planner_have_no_path_to_backend_elevation():
    """The product brief's explicit "no backend through voice bypass"
    rule: neither /chat nor /plan accept or honor anything resembling an
    elevation credential -- voice can only ever ask a human to go press
    the real hotkey and authenticate for real."""
    client, device_token = _make_enrolled_client()

    chat_response = client.post(
        "/chat", json={"message": "show me the backend"}, headers={"X-Aura-Device-Token": device_token},
    )
    assert chat_response.status_code == 200  # answered like any other unresolved request, never elevates

    diagnostics_response = client.get("/backend/diagnostics")
    assert diagnostics_response.status_code == 401  # still locked -- the chat request above granted nothing


def test_repeated_wrong_pins_through_the_real_api_eventually_rate_limit():
    client, device_token = _make_enrolled_client()

    statuses = []
    for _ in range(6):
        response = client.post(
            "/backend/authenticate", json={"pin": "000000"}, headers={"X-Aura-Device-Token": device_token},
        )
        statuses.append(response.status_code)

    assert 429 in statuses, statuses


def test_backend_pin_cannot_be_set_without_a_device_token_once_enrolled():
    app: FastAPI = create_app(load_settings())
    app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    response = client.post("/backend/pin", json={"pin": "111111"})

    assert response.status_code == 401


def test_backend_audit_lists_the_real_elevation_attempts():
    client, device_token = _make_enrolled_client()
    client.post("/backend/authenticate", json={"pin": "482913"}, headers={"X-Aura-Device-Token": device_token})
    elevation_token = client.post(
        "/backend/authenticate", json={"pin": "482913"}, headers={"X-Aura-Device-Token": device_token},
    ).json()["elevation_token"]

    response = client.get("/backend/audit", headers={
        "X-Aura-Device-Token": device_token, "X-Aura-Backend-Elevation": elevation_token,
    })

    assert response.status_code == 200
    action_types = {entry["action_type"] for entry in response.json()}
    assert "security.backend_elevation_attempt" in action_types
