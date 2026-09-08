from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time

import pytest

from aura_core.connectors import ConnectorRegistry
from aura_core.connectors.desktop_connector import DesktopControlConnector
from aura_core.connectors.ui_automation import MockUiAutomationProvider, UiElement
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine, RiskTier
from aura_core.status import CapabilityStatus

_XVFB_DISPLAY = ":93"


@pytest.fixture(scope="module")
def virtual_display():
    """A real, self-contained X server this test session controls (not
    dependent on any display happening to already be running) — this is
    what makes 'real input injection' genuinely testable in a headless
    Linux container. Only meaningful on Linux/X11: Windows' pynput backend
    talks to Win32 directly and has no DISPLAY/Xvfb concept at all, so this
    fixture skips immediately there rather than ever shelling out to a
    `which`/`Xvfb` binary that doesn't exist on that platform. Also skips
    cleanly (via shutil.which, which never raises) if Xvfb simply isn't
    installed on a Linux runner."""
    if platform.system() != "Linux":
        pytest.skip("Xvfb-backed virtual display tests only apply to Linux/X11")
    if shutil.which("Xvfb") is None:
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


@pytest.mark.linux
@pytest.mark.integration
def test_health_check_is_live_against_a_real_display(virtual_display):
    connector = DesktopControlConnector()
    result = connector.health_check()
    assert result.status == CapabilityStatus.LIVE


@pytest.mark.linux
@pytest.mark.skipif(
    platform.system() != "Linux",
    reason="Absence of DISPLAY only implies UNAVAILABLE for pynput's Linux/X11 (Xlib) "
    "backend. Windows' pynput backend talks to Win32 directly and has no DISPLAY "
    "concept, so desktop control may remain LIVE there with no DISPLAY set at all -- "
    "see test_health_check_does_not_depend_on_display_on_windows below.",
)
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


@pytest.mark.windows
@pytest.mark.hardware
@pytest.mark.skipif(
    platform.system() != "Windows",
    reason="Exercises the Win32 pynput backend's actual behavior; only meaningful "
    "on real Windows, and REQUIRES_WINDOWS_RUNTIME to genuinely verify -- this "
    "sandbox has no Windows machine reachable, so this test has never actually run "
    "and is NOT_TESTED here. It is included so a real Windows CI/commissioning run "
    "exercises the claim instead of silently skipping the whole file.",
)
def test_health_check_does_not_depend_on_display_on_windows():
    env = {k: v for k, v in os.environ.items() if k != "DISPLAY"}
    result = subprocess.run(
        [sys.executable, "-c", (
            "from aura_core.connectors.desktop_connector import DesktopControlConnector;"
            "r = DesktopControlConnector().health_check();"
            "print(r.status.value)"
        )],
        env=env, capture_output=True, text=True, timeout=15,
    )
    assert result.stdout.strip() == CapabilityStatus.LIVE.value, result.stderr


@pytest.mark.linux
@pytest.mark.integration
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


@pytest.mark.linux
@pytest.mark.integration
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


def test_find_element_is_honestly_not_connected_without_a_provider(tmp_path):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("computer_control.find_element", 4)
    ConnectorRegistry(broker).register(DesktopControlConnector())

    outcome = broker.submit(ActionRequest(action_type="computer_control.find_element", params={"name": "Submit"}))

    assert outcome.status == OutcomeStatus.DENIED
    assert "not_connected" in outcome.message.lower()


def test_find_element_returns_the_real_element_from_the_mock_accessibility_tree(tmp_path):
    provider = MockUiAutomationProvider([UiElement(name="Submit", role="button", x=100, y=200, width=80, height=30)])
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("computer_control.find_element", 4)
    ConnectorRegistry(broker).register(DesktopControlConnector(ui_automation=provider))

    outcome = broker.submit(ActionRequest(action_type="computer_control.find_element", params={"name": "Submit"}))

    assert outcome.status == OutcomeStatus.EXECUTED
    found = json.loads(outcome.message)
    assert found == {"name": "Submit", "role": "button", "x": 100, "y": 200, "width": 80, "height": 30, "automation_id": None}


def test_find_element_reports_no_match_honestly(tmp_path):
    provider = MockUiAutomationProvider([])
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("computer_control.find_element", 4)
    ConnectorRegistry(broker).register(DesktopControlConnector(ui_automation=provider))

    outcome = broker.submit(ActionRequest(action_type="computer_control.find_element", params={"name": "Nonexistent"}))

    assert outcome.status == OutcomeStatus.DENIED
    assert "no matching element found" in outcome.message


@pytest.mark.linux
@pytest.mark.integration
def test_click_element_resolves_through_the_mock_tree_and_clicks_the_real_display(tmp_path, virtual_display):
    provider = MockUiAutomationProvider([UiElement(name="Submit", role="button", x=100, y=200, width=80, height=30)])
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("computer_control.click_element", 4)
    ConnectorRegistry(broker).register(DesktopControlConnector(ui_automation=provider))

    outcome = broker.submit(ActionRequest(action_type="computer_control.click_element", params={"name": "Submit"}))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert "Submit" in outcome.message


def test_find_element_is_green_tier_and_click_element_is_amber_tier():
    risk = RiskEngine()
    assert risk.classify(ActionRequest(action_type="computer_control.find_element")).tier == RiskTier.GREEN
    assert risk.classify(ActionRequest(action_type="computer_control.click_element")).tier == RiskTier.AMBER


def test_click_element_is_denied_by_default_at_autonomy_zero(tmp_path):
    provider = MockUiAutomationProvider([UiElement(name="Submit", role="button", x=100, y=200, width=80, height=30)])
    broker, _policy = make_broker(tmp_path)
    ConnectorRegistry(broker).register(DesktopControlConnector(ui_automation=provider))

    outcome = broker.submit(ActionRequest(action_type="computer_control.click_element", params={"name": "Submit"}))

    assert outcome.status == OutcomeStatus.DENIED
