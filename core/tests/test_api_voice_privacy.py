"""The backend half of section 17's real microphone privacy gating:
FULL_MIC_OFF and WAKE_WORD_ONLY are distinct, both real states the voice
host process (AuraVoice.Windows.Host, via WindowsVoicePipeline.PrivacyGate)
polls and acts on by actually opening/closing the microphone hardware --
this endpoint only records the requested mode, exactly like
/voice/state records the reported session state. The WPF UI's mute
toggle is not itself the privacy control; it is a client of this API,
proven end-to-end (minus the actual hardware, which needs Windows) in
AuraShell.Core.Tests.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def test_privacy_mode_defaults_to_normal_before_anything_reports():
    client = TestClient(create_app(load_settings()))

    response = client.get("/voice/privacy")

    assert response.status_code == 200
    assert response.json()["mode"] == "Normal"


def test_a_set_privacy_mode_is_readable_back():
    client = TestClient(create_app(load_settings()))

    post_response = client.post("/voice/privacy", json={"mode": "FullMicOff"})
    assert post_response.status_code == 200
    assert post_response.json()["mode"] == "FullMicOff"

    get_response = client.get("/voice/privacy")
    assert get_response.json()["mode"] == "FullMicOff"


def test_every_real_privacy_mode_is_accepted():
    client = TestClient(create_app(load_settings()))

    for mode in ["Normal", "WakeWordOnly", "FullMicOff"]:
        response = client.post("/voice/privacy", json={"mode": mode})
        assert response.status_code == 200, mode
        assert client.get("/voice/privacy").json()["mode"] == mode


def test_an_unrecognized_privacy_mode_is_rejected():
    client = TestClient(create_app(load_settings()))
    client.post("/voice/privacy", json={"mode": "WakeWordOnly"})
    before = client.get("/voice/privacy").json()["mode"]

    response = client.post("/voice/privacy", json={"mode": "SortOfMuted"})

    assert response.status_code == 422
    # And it must not have silently taken effect.
    assert client.get("/voice/privacy").json()["mode"] == before


def test_setting_privacy_mode_requires_a_device_token_once_enrolled():
    app = create_app(load_settings())
    app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    response = client.post("/voice/privacy", json={"mode": "FullMicOff"})

    assert response.status_code == 401


def test_reading_privacy_mode_never_requires_a_token_even_after_enrollment():
    app = create_app(load_settings())
    app.state.runtime.enrollment.enroll_owner("Ada")
    client = TestClient(app)

    response = client.get("/voice/privacy")

    assert response.status_code == 200
