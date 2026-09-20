"""/identity/whoami is the real substitute this build has for a production
startup authentication screen (section 3's "AURA starts -> secure
initialization -> owner authentication"): no Windows Hello or other
hardware-backed factor is wired up here, so the native shell's
AuthenticationViewModel proves the owner is at a trusted device the same
way every other mutating endpoint already does -- a valid
X-Aura-Device-Token -- rather than inventing a second, weaker check just
for the boot screen.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def test_whoami_before_enrollment_reports_honestly_that_there_is_no_owner_yet():
    client = TestClient(create_app(load_settings()))

    response = client.get("/identity/whoami")

    assert response.status_code == 200
    body = response.json()
    assert body == {"enrolled": False, "owner_name": None, "device_label": None}


def test_whoami_without_a_device_token_is_rejected_once_enrolled():
    app = create_app(load_settings())
    app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    response = client.get("/identity/whoami")

    assert response.status_code == 401


def test_whoami_with_a_valid_device_token_confirms_the_real_owner_and_device():
    app = create_app(load_settings())
    owner, device_token = app.state.runtime.enrollment.enroll_owner("Ada", device_label="Ada's laptop")
    client = TestClient(app)

    response = client.get("/identity/whoami", headers={"X-Aura-Device-Token": device_token})

    assert response.status_code == 200
    body = response.json()
    assert body["enrolled"] is True
    assert body["owner_name"] == "Ada"
    assert body["device_label"] == "Ada's laptop"


def test_whoami_with_a_wrong_device_token_is_rejected():
    app = create_app(load_settings())
    app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    response = client.get("/identity/whoami", headers={"X-Aura-Device-Token": "not-a-real-token"})

    assert response.status_code == 401


def test_whoami_with_a_revoked_device_token_is_rejected():
    app = create_app(load_settings())
    owner, device_token = app.state.runtime.enrollment.enroll_owner("Ada")
    device = app.state.runtime.enrollment.list_devices()[0]
    app.state.runtime.enrollment.revoke_device(device.id)
    client = TestClient(app)

    response = client.get("/identity/whoami", headers={"X-Aura-Device-Token": device_token})

    assert response.status_code == 401
