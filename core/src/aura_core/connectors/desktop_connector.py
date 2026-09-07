"""Desktop control connector: real mouse/keyboard injection via `pynput`
(cross-platform — Win32 on Windows, Xlib on Linux, Quartz on macOS).
Verified in this session against a real X server (Xvfb) and a real
xterm capturing injected keystrokes to a file — genuine input injection,
not merely "the library imported." Behavior on a real Windows desktop
(different backend, different focus/permission model, likely UAC/
accessibility-permission prompts) is not verified — see
docs/project-status.md's blocker classification.

Also exposes UI Automation / accessibility-tree targeting
(find_element/click_element) per section 16's preference for that over
blind coordinates -- see ui_automation.py for why the real per-platform
backend is REQUIRES_WINDOWS_RUNTIME while the interface and its governed
plumbing are buildable and tested here today. Without a provider
configured, find_element/click_element honestly report NOT_CONNECTED
rather than silently falling back to coordinates.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from ..governance.action_broker import ActionRequest, HandlerResult
from ..status import CapabilityStatus
from .base import Connector, ConnectorManifest
from .ui_automation import MockUiAutomationProvider, UiAutomationProvider


class DesktopControlConnector(Connector):
    def __init__(self, ui_automation: UiAutomationProvider | None = None) -> None:
        self._ui_automation = ui_automation
        is_mock = isinstance(ui_automation, MockUiAutomationProvider)
        if ui_automation is None:
            ui_note = "; UI Automation: not configured"
        elif is_mock:
            ui_note = "; UI Automation: mock accessibility tree (interface only, no real Windows/AT-SPI backend wired)"
        else:
            ui_note = "; UI Automation: real backend"
        self.manifest = ConnectorManifest(
            name="desktop_control",
            auth_method="none",
            capabilities=[
                "computer_control.move_mouse", "computer_control.click",
                "computer_control.type_text", "computer_control.key_press",
                "computer_control.find_element", "computer_control.click_element",
            ],
            notes="pynput-based mouse/keyboard injection" + ui_note,
        )

    def health_check(self) -> HandlerResult:
        try:
            from pynput.mouse import Controller as MouseController
            mouse = MouseController()
            _ = mouse.position  # touches the real display connection
            return HandlerResult(CapabilityStatus.LIVE, "display/input backend is reachable")
        except Exception as exc:  # noqa: BLE001 -- health check must never raise
            return HandlerResult(CapabilityStatus.UNAVAILABLE, f"no usable display/input backend: {exc}")

    def move_mouse(self, request: ActionRequest) -> HandlerResult:
        from pynput.mouse import Controller as MouseController
        try:
            mouse = MouseController()
            mouse.position = (int(request.params["x"]), int(request.params["y"]))
            return HandlerResult(CapabilityStatus.LIVE, f"moved to {mouse.position}")
        except Exception as exc:  # noqa: BLE001
            return HandlerResult(CapabilityStatus.DEGRADED, f"move failed: {exc}")

    def click(self, request: ActionRequest) -> HandlerResult:
        from pynput.mouse import Button, Controller as MouseController
        try:
            mouse = MouseController()
            mouse.position = (int(request.params["x"]), int(request.params["y"]))
            mouse.click(Button.left, 1)
            return HandlerResult(CapabilityStatus.LIVE, f"clicked at {mouse.position}")
        except Exception as exc:  # noqa: BLE001
            return HandlerResult(CapabilityStatus.DEGRADED, f"click failed: {exc}")

    def type_text(self, request: ActionRequest) -> HandlerResult:
        from pynput.keyboard import Controller as KeyboardController
        try:
            keyboard = KeyboardController()
            keyboard.type(request.params["text"])
            return HandlerResult(CapabilityStatus.LIVE, f"typed {len(request.params['text'])} characters")
        except Exception as exc:  # noqa: BLE001
            return HandlerResult(CapabilityStatus.DEGRADED, f"type failed: {exc}")

    def key_press(self, request: ActionRequest) -> HandlerResult:
        from pynput.keyboard import Controller as KeyboardController, Key
        try:
            keyboard = KeyboardController()
            key_name = request.params["key"]
            key = getattr(Key, key_name, key_name)  # named key (e.g. "enter") or a literal character
            keyboard.press(key)
            keyboard.release(key)
            return HandlerResult(CapabilityStatus.LIVE, f"pressed {key_name}")
        except Exception as exc:  # noqa: BLE001
            return HandlerResult(CapabilityStatus.DEGRADED, f"key press failed: {exc}")

    def find_element(self, request: ActionRequest) -> HandlerResult:
        if self._ui_automation is None:
            return HandlerResult(CapabilityStatus.NOT_CONNECTED, "no UI Automation provider configured")
        element = self._ui_automation.find_element(
            name=request.params.get("name"), role=request.params.get("role"),
            automation_id=request.params.get("automation_id"),
        )
        if element is None:
            return HandlerResult(CapabilityStatus.DEGRADED, "no matching element found")
        return HandlerResult(CapabilityStatus.LIVE, json.dumps(asdict(element)))

    def click_element(self, request: ActionRequest) -> HandlerResult:
        if self._ui_automation is None:
            return HandlerResult(CapabilityStatus.NOT_CONNECTED, "no UI Automation provider configured")
        element = self._ui_automation.find_element(
            name=request.params.get("name"), role=request.params.get("role"),
            automation_id=request.params.get("automation_id"),
        )
        if element is None:
            return HandlerResult(CapabilityStatus.DEGRADED, "no matching element found")

        from pynput.mouse import Button, Controller as MouseController
        try:
            mouse = MouseController()
            mouse.position = element.center
            mouse.click(Button.left, 1)
            return HandlerResult(CapabilityStatus.LIVE, f"clicked element '{element.name}' at {mouse.position}")
        except Exception as exc:  # noqa: BLE001
            return HandlerResult(CapabilityStatus.DEGRADED, f"click failed: {exc}")

    def handlers(self) -> dict:
        return {
            "computer_control.move_mouse": self.move_mouse,
            "computer_control.click": self.click,
            "computer_control.type_text": self.type_text,
            "computer_control.key_press": self.key_press,
            "computer_control.find_element": self.find_element,
            "computer_control.click_element": self.click_element,
        }
