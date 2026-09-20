"""Proves /kill-switch/disengage's device-token gate (section 9's device
trust, wired into a real endpoint as a concrete proof of concept) without
disturbing any endpoint's pre-enrollment behavior: before an owner is
enrolled the endpoint stays exactly as open as it always was (every
existing test in this suite calls it without a token and still passes),
and only once an owner is enrolled does a valid token become required.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def test_before_enrollment_the_endpoint_stays_open_exactly_as_before():
    client = TestClient(create_app(load_settings()))

    response = client.post("/kill-switch/disengage")

    assert response.status_code == 200
    assert response.json()["kill_switch_engaged"] is False


def test_after_enrollment_the_endpoint_requires_a_token():
    app = create_app(load_settings())
    app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    response = client.post("/kill-switch/disengage")

    assert response.status_code == 401


def test_after_enrollment_a_valid_token_is_accepted():
    app = create_app(load_settings())
    _owner, raw_token = app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    response = client.post("/kill-switch/disengage", headers={"X-Aura-Device-Token": raw_token})

    assert response.status_code == 200
    assert response.json()["kill_switch_engaged"] is False


def test_after_enrollment_a_wrong_token_is_rejected():
    app = create_app(load_settings())
    app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    response = client.post("/kill-switch/disengage", headers={"X-Aura-Device-Token": "not-the-real-token"})

    assert response.status_code == 401


def test_a_revoked_devices_token_is_rejected():
    app = create_app(load_settings())
    _owner, raw_token = app.state.runtime.enrollment.enroll_owner("Ada")
    device = app.state.runtime.enrollment.list_devices()[0]
    app.state.runtime.enrollment.revoke_device(device.id)
    client = TestClient(app)

    response = client.post("/kill-switch/disengage", headers={"X-Aura-Device-Token": raw_token})

    assert response.status_code == 401
