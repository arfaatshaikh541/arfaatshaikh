"""Proves the device-trust gate (section 9) was actually applied to
every state-changing endpoint, not just /kill-switch/disengage --
declaring `dependencies=gated` on a route is easy to get wrong or forget
on the next new endpoint, so this asserts the real behavior across a
representative sample rather than trusting the source read.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings


def _make_enrolled_app():
    app = create_app(load_settings())
    _owner, raw_token = app.state.runtime.enrollment.enroll_owner("Ada")
    return app, raw_token


def test_every_post_endpoint_is_open_before_enrollment():
    app = create_app(load_settings())
    client = TestClient(app)

    # A representative sample across every router group -- governance,
    # tasks, goals, mandates, memory, chat, and voice.
    checks = [
        ("POST", "/tasks", {"task_type": "noop", "payload": {}}),
        ("POST", "/goals", {"statement": "test goal"}),
        ("POST", "/mandates", {"title": "t", "mission": "m"}),
        ("POST", "/goals/review", None),
        ("POST", "/loop/run-once", None),
        ("POST", "/memory/ask", {"question": "anything?"}),
    ]
    for method, path, body in checks:
        response = client.request(method, path, json=body)
        assert response.status_code != 401, f"{path} should be open before enrollment, got {response.status_code}"


def test_every_post_endpoint_requires_a_token_after_enrollment():
    app, _raw_token = _make_enrolled_app()
    client = TestClient(app)

    checks = [
        ("POST", "/tasks", {"task_type": "noop", "payload": {}}),
        ("POST", "/goals", {"statement": "test goal"}),
        ("POST", "/mandates", {"title": "t", "mission": "m"}),
        ("POST", "/goals/review", None),
        ("POST", "/loop/run-once", None),
        ("POST", "/memory/ask", {"question": "anything?"}),
        ("POST", "/guardian/freeze", {"reason": "test"}),
        ("POST", "/kill-switch/engage", None),
        ("POST", "/voice/wake-word/check", {"audio_base64": ""}),
    ]
    for method, path, body in checks:
        response = client.request(method, path, json=body)
        assert response.status_code == 401, f"{path} should require a token after enrollment, got {response.status_code}"


def test_every_post_endpoint_accepts_the_real_token_after_enrollment():
    app, raw_token = _make_enrolled_app()
    client = TestClient(app)
    headers = {"X-Aura-Device-Token": raw_token}

    checks = [
        ("POST", "/tasks", {"task_type": "noop", "payload": {}}),
        ("POST", "/goals", {"statement": "test goal"}),
        ("POST", "/mandates", {"title": "t", "mission": "m"}),
        ("POST", "/goals/review", None),
        ("POST", "/loop/run-once", None),
        ("POST", "/memory/ask", {"question": "anything?"}),
    ]
    for method, path, body in checks:
        response = client.request(method, path, json=body, headers=headers)
        assert response.status_code != 401, f"{path} should accept a valid token, got {response.status_code}"


def test_read_only_get_endpoints_are_never_gated_even_after_enrollment():
    app, _raw_token = _make_enrolled_app()
    client = TestClient(app)

    for path in ["/health", "/status", "/tasks", "/goals", "/mandates", "/approvals", "/audit", "/memory/search?q=x"]:
        response = client.get(path)
        assert response.status_code != 401, f"{path} is read-only and must never require a token"
