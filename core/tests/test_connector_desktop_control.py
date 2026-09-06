from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

from aura_core.connectors import ConnectorRegistry
from aura_core.connectors.desktop_connector import DesktopControlConnector
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine
from aura_core.status import CapabilityStatus

_XVFB_DISPLAY = ":93"


@pytest.fixture(scope="module")
def virtual_display():
    """A real, self-contained X server this test session controls (not
    dependent on any display happening to already be running) — this is
    what makes 'real input injection' genuinely testable in a headless
    Linux container. Skips cleanly if Xvfb isn't installed."""
    if subprocess.run(["which", "Xvfb"], capture_output=True).returncode != 0:
        pytest.skip("Xvfb is not installed in this environment")

    os.environ.setdefault("HOME", "/root")
    xauth_path = os.path.expanduser("~/.Xauthority")
    if not os.path.exists(xauth_path):
        open(xauth_path, "a").close()

    proc = subprocess.Popen(
        ["Xvfb", _XVFB_DISPLAY, "-screen", "0", "1024x768x24", "-ac"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)
    old_display = os.environ.get("DISPLAY")
    os.environ["DISPLAY"] = _XVFB_DISPLAY
    try:
        yield _XVFB_DISPLAY
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        if old_display is not None:
            os.environ["DISPLAY"] = old_display
        else:
            os.environ.pop("DISPLAY", None)


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/desktop.db"
    policy = PolicyEngine(db_url)
    broker = ActionBroker(policy, RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    return broker, policy


def test_health_check_is_live_against_a_real_display(virtual_display):
    connector = DesktopControlConnector()
    result = connector.health_check()
    assert result.status == CapabilityStatus.LIVE


def test_health_check_is_unavailable_without_a_display():
    # Run in a fresh subprocess, deliberately: pynput's underlying Xlib
    # connection has process-global state, and toggling DISPLAY within
    # this test process was observed to leave later tests' mouse queries
    # returning stale/default positions rather than the real ones.
    # Isolating this negative case avoids polluting that shared state.
    #
    # sys.executable, not a bare "python3": a bare name resolves against
    # whatever's first on PATH, which silently becomes the wrong
    # interpreter (no aura_core installed) whenever this suite is invoked
    # via an absolute interpreter path without the venv's bin/Scripts
    # directory having been prepended to PATH first -- exactly how
    # WINDOWS-COMMISSIONING.ps1 invokes pytest. Caught by actually running
    # that script end to end rather than assuming the invocation style.
    env = {k: v for k, v in os.environ.items() if k != "DISPLAY"}
    result = subprocess.run(
        [sys.executable, "-c", (
            "from aura_core.connectors.desktop_connector import DesktopControlConnector;"
            "r = DesktopControlConnector().health_check();"
            "print(r.status.value)"
        )],
        env=env, capture_output=True, text=True, timeout=15,
    )
    assert result.stdout.strip() == CapabilityStatus.UNAVAILABLE.value, result.stderr


def test_move_mouse_executes_a_real_xtest_call_against_the_display(tmp_path, virtual_display):
    # What this proves: the connector makes a genuine XTestFakeMotionEvent
    # call against a real, live X server connection and the call
    # completes without error (health_check against the same display
    # reports LIVE; without a display it reports UNAVAILABLE, covered
    # separately). What this does NOT prove: that the pointer's on-screen
    # position visibly changed. Independent verification via `xdotool
    # getmouselocation` immediately after — even for a bare `xdotool
    # mousemove` with no AURA code involved at all — reported the
    # pointer unmoved in this container's Xvfb, and pynput's own
    # follow-up position query agreed with xdotool, not with the value
    # it was just told to set. That rules out a bug in this connector
    # (the same primitive, invoked by an entirely separate tool, showed
    # identical behavior) and points to a synthetic-input limitation of
    # this sandbox's Xvfb, not something to fix here. Genuine on-screen
    # verification needs a real Windows desktop — see
    # docs/project-status.md's blocker classification for this connector.
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("computer_control.move_mouse", 4)
    ConnectorRegistry(broker).register(DesktopControlConnector())

    outcome = broker.submit(ActionRequest(action_type="computer_control.move_mouse", params={"x": 111, "y": 222}))

    assert outcome.status == OutcomeStatus.EXECUTED


def test_type_text_and_key_press_execute_without_error_against_a_real_display(tmp_path, virtual_display):
    # Same caveat as the mouse test: this proves the connector's
    # XTestFakeKeyEvent calls run cleanly against a live X connection, not
    # that a receiving application visibly captured the keystrokes. A
    # receiving-application check (spawning xterm and reading back a
    # captured file) was attempted and removed: it failed for the same
    # environment reason as the mouse position check, not a connector
    # bug, and duplicating the same caveat in a heavier, flakier test
    # wasn't worth it. Real delivery to a focused application needs
    # Windows validation.
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("computer_control.type_text", 4)
    policy.set_autonomy_level("computer_control.key_press", 4)
    ConnectorRegistry(broker).register(DesktopControlConnector())

    type_outcome = broker.submit(ActionRequest(action_type="computer_control.type_text", params={"text": "hello"}))
    assert type_outcome.status == OutcomeStatus.EXECUTED

    key_outcome = broker.submit(ActionRequest(action_type="computer_control.key_press", params={"key": "enter"}))
    assert key_outcome.status == OutcomeStatus.EXECUTED
