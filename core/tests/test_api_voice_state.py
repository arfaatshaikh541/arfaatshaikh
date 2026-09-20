"""The backend half of section 8's "always-listening, privacy-visible
status" requirement: a real cross-process way for the voice host to
report its VoiceSessionController state and for any local client (a
future tray icon, `aura status`, or this endpoint directly) to read it,
closing the audit's flagged gap ("no visible indicator anywhere, console
log only"). The WPF tray icon UI itself remains REQUIRES_WINDOWS_RUNTIME
-- this is only the state-exposure API, which is what's IMPLEMENTABLE_NOW.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import aura_core.api.app as app_module
from aura_core.api import create_app
from aura_core.config import load_settings
from aura_core.status import CapabilityStatus


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


def test_the_state_stream_route_exists_and_is_ungated():
    """Full route-level smoke test: TestClient's in-process transport
    runs an ASGI call to completion before returning anything (see
    voice_state_events' docstring in api/app.py), so it cannot exercise
    an endpoint that streams forever the way a real HTTP client can --
    the actual push behaviour is covered by driving voice_state_events
    directly below. What IS verifiable here, and worth verifying, is
    that the route is registered, GET-only, and never gated -- reading
    the current voice state must never require a device token, same as
    the plain /voice/state GET."""
    app = create_app(load_settings())
    app.state.runtime.enrollment.enroll_owner("Ada")

    stream_route = next(r for r in app.routes if getattr(r, "path", None) == "/voice/state/stream")
    assert "GET" in stream_route.methods
    assert stream_route.dependant.dependencies == []


async def _next_event(agen) -> str:
    line = await asyncio.wait_for(agen.__anext__(), timeout=2.0)
    payload = json.loads(line.decode()[len("data: "):].strip())
    return payload["data"]


async def test_voice_state_events_pushes_the_current_state_immediately():
    app_module.registry.set(  # type: ignore[attr-defined]
        "voice.session_state", CapabilityStatus.LIVE, "Speaking",
    )
    agen = app_module.voice_state_events(poll_interval=0.01)
    try:
        assert await _next_event(agen) == "Speaking"
    finally:
        await agen.aclose()


async def test_voice_state_events_pushes_a_real_change_and_nothing_when_unchanged():
    app_module.registry.set(
        "voice.session_state", CapabilityStatus.LIVE, "Idle",
    )
    agen = app_module.voice_state_events(poll_interval=0.01)
    try:
        assert await _next_event(agen) == "Idle"

        app_module.registry.set("voice.session_state", CapabilityStatus.LIVE, "Awake")
        assert await _next_event(agen) == "Awake"

        # No further change was made -- the next event must not arrive
        # within a few poll cycles' worth of time (proving this pushes
        # real transitions only, not a fixed-rate heartbeat the shell
        # would have to de-duplicate itself).
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(agen.__anext__(), timeout=0.2)
    finally:
        await agen.aclose()


async def test_voice_state_events_reports_unknown_before_any_host_has_reported():
    from aura_core.status import StatusRegistry

    empty_registry = StatusRegistry()
    original = app_module.registry
    app_module.registry = empty_registry
    try:
        agen = app_module.voice_state_events(poll_interval=0.01)
        try:
            assert await _next_event(agen) == "UNKNOWN"
        finally:
            await agen.aclose()
    finally:
        app_module.registry = original
