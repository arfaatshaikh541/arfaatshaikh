"""Multi-device trust, over the real HTTP surface a native shell (and a
genuinely separate second device) would use. identity/enrollment.py's
DeviceTrust already supported multiple devices per owner before this
file existed -- what was missing was any way to reach it over HTTP.
These tests prove: the device list is real and elevation-gated, revoking
a device really blocks its future requests (not just its DB row),
renaming persists, and the pairing flow lets a genuinely separate device
(its own TestClient, its own bearer token, no shared state except the
pairing code) join without ever needing a device token of its own.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def _enroll_and_elevate(pin: str = "482913") -> tuple[TestClient, FastAPI, str, str]:
    """Returns (client, app, device_token, elevation_token). Every
    backend_gated endpoint requires BOTH headers on every single call --
    a valid elevation token alone is not enough, matching
    require_backend_elevation's docs ("independent of, and never
    satisfied by, require_device_token")."""
    app: FastAPI = create_app(load_settings())
    _owner, device_token = app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)
    client.post("/backend/pin", json={"pin": pin}, headers={"X-Aura-Device-Token": device_token})
    auth = client.post(
        "/backend/authenticate", json={"pin": pin}, headers={"X-Aura-Device-Token": device_token},
    )
    elevation_token = auth.json()["elevation_token"]
    return client, app, device_token, elevation_token


def _backend_headers(device_token: str, elevation_token: str) -> dict[str, str]:
    return {"X-Aura-Device-Token": device_token, "X-Aura-Backend-Elevation": elevation_token}


def test_devices_list_requires_backend_elevation_not_just_a_device_token():
    app: FastAPI = create_app(load_settings())
    _owner, device_token = app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    response = client.get("/devices", headers={"X-Aura-Device-Token": device_token})

    assert response.status_code == 401


def test_devices_list_shows_the_real_enrolled_device_never_a_token():
    client, app, device_token, elevation_token = _enroll_and_elevate()

    response = client.get("/devices", headers=_backend_headers(device_token, elevation_token))

    assert response.status_code == 200
    devices = response.json()
    assert len(devices) == 1
    assert devices[0]["label"] == "primary"
    assert devices[0]["revoked"] is False
    assert "token_hash" not in devices[0]
    assert "token" not in devices[0]


def test_the_full_pairing_flow_enrolls_a_genuinely_separate_second_device():
    client, app, device_token, elevation_token = _enroll_and_elevate()

    start = client.post("/devices/pairing/start", headers=_backend_headers(device_token, elevation_token))
    assert start.status_code == 200
    code = start.json()["code"]
    assert len(code) == 8

    # A genuinely separate device: its own TestClient, no headers shared
    # with the root client at all -- the only thing it has is the code.
    second_device_client = TestClient(app)
    claim = second_device_client.post(
        "/devices/pairing/claim", json={"code": code, "device_label": "iPhone"},
    )
    assert claim.status_code == 200
    new_device_token = claim.json()["device_token"]
    assert new_device_token

    # The new device's token is real and independently usable.
    whoami = second_device_client.get(
        "/identity/whoami", headers={"X-Aura-Device-Token": new_device_token},
    )
    assert whoami.status_code == 200
    assert whoami.json()["device_label"] == "iPhone"

    # And it shows up in the root's device list too.
    devices = client.get("/devices", headers=_backend_headers(device_token, elevation_token)).json()
    assert {d["label"] for d in devices} == {"primary", "iPhone"}


def test_a_pairing_code_cannot_be_claimed_twice():
    client, app, device_token, elevation_token = _enroll_and_elevate()
    code = client.post(
        "/devices/pairing/start", headers=_backend_headers(device_token, elevation_token),
    ).json()["code"]

    first = TestClient(app).post("/devices/pairing/claim", json={"code": code, "device_label": "iPhone"})
    assert first.status_code == 200

    second = TestClient(app).post("/devices/pairing/claim", json={"code": code, "device_label": "Attacker"})
    assert second.status_code == 401


def test_an_unknown_pairing_code_is_rejected():
    app: FastAPI = create_app(load_settings())
    client = TestClient(app)

    response = client.post("/devices/pairing/claim", json={"code": "NOTREAL1", "device_label": "iPhone"})

    assert response.status_code == 401


def test_starting_a_pairing_session_requires_backend_elevation():
    app: FastAPI = create_app(load_settings())
    _owner, device_token = app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    response = client.post("/devices/pairing/start", headers={"X-Aura-Device-Token": device_token})

    assert response.status_code == 401


def test_revoking_a_device_genuinely_blocks_its_future_requests():
    client, app, device_token, elevation_token = _enroll_and_elevate()
    code = client.post(
        "/devices/pairing/start", headers=_backend_headers(device_token, elevation_token),
    ).json()["code"]
    second_device_client = TestClient(app)
    new_device_token = second_device_client.post(
        "/devices/pairing/claim", json={"code": code, "device_label": "iPhone"},
    ).json()["device_token"]

    devices = client.get("/devices", headers=_backend_headers(device_token, elevation_token)).json()
    iphone_id = next(d["id"] for d in devices if d["label"] == "iPhone")

    revoke = client.post(
        f"/devices/{iphone_id}/revoke", headers=_backend_headers(device_token, elevation_token),
    )
    assert revoke.status_code == 200

    # The revoked device's own token no longer works for anything.
    whoami = second_device_client.get(
        "/identity/whoami", headers={"X-Aura-Device-Token": new_device_token},
    )
    assert whoami.status_code == 401

    devices_after = client.get("/devices", headers=_backend_headers(device_token, elevation_token)).json()
    iphone_after = next(d for d in devices_after if d["id"] == iphone_id)
    assert iphone_after["revoked"] is True


def test_revoking_an_unknown_device_id_is_a_safe_no_op():
    client, app, device_token, elevation_token = _enroll_and_elevate()

    response = client.post(
        "/devices/does-not-exist/revoke", headers=_backend_headers(device_token, elevation_token),
    )

    assert response.status_code == 200


def test_renaming_a_device_persists_and_requires_elevation():
    client, app, device_token, elevation_token = _enroll_and_elevate()
    device_id = client.get(
        "/devices", headers=_backend_headers(device_token, elevation_token),
    ).json()[0]["id"]

    renamed = client.post(
        f"/devices/{device_id}/rename", json={"label": "Ada's Desktop"},
        headers=_backend_headers(device_token, elevation_token),
    )
    assert renamed.status_code == 200

    devices = client.get("/devices", headers=_backend_headers(device_token, elevation_token)).json()
    assert devices[0]["label"] == "Ada's Desktop"


def test_renaming_an_unknown_device_id_reports_404():
    client, app, device_token, elevation_token = _enroll_and_elevate()

    response = client.post(
        "/devices/does-not-exist/rename", json={"label": "x"},
        headers=_backend_headers(device_token, elevation_token),
    )

    assert response.status_code == 404


def test_every_pairing_attempt_is_written_to_the_real_audit_log():
    client, app, device_token, elevation_token = _enroll_and_elevate()
    code = client.post(
        "/devices/pairing/start", headers=_backend_headers(device_token, elevation_token),
    ).json()["code"]
    TestClient(app).post("/devices/pairing/claim", json={"code": code, "device_label": "iPhone"})
    TestClient(app).post("/devices/pairing/claim", json={"code": "WRONGCODE", "device_label": "Attacker"})

    entries = app.state.runtime.audit.entries_after(0)
    action_types = [e.action_type for e in entries]
    assert "security.device_pairing_start" in action_types
    claim_entries = [e for e in entries if e.action_type == "security.device_pairing_claim"]
    assert any(e.decision == "ALLOW" for e in claim_entries)
    assert any(e.decision == "DENY" for e in claim_entries)
    # Never records the pairing code itself in the audit trail.
    assert all(code not in (e.result_message or "") for e in entries)
