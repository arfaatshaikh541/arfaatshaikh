"""Desktop control connector: real mouse/keyboard injection via `pynput`
(cross-platform — Win32 on Windows, Xlib on Linux, Quartz on macOS).
Verified in this session against a real X server (Xvfb) and a real
xterm capturing injected keystrokes to a file — genuine input injection,
not merely "the library imported." Behavior on a real Windows desktop
(different backend, different focus/permission model, likely UAC/
accessibility-permission prompts) is not verified — see
docs/project-status.md's blocker classification.
"""
from __future__ import annotations

from ..governance.action_broker import ActionRequest, HandlerResult
from ..status import CapabilityStatus
from .base import Connector, ConnectorManifest


class DesktopControlConnector(Connector):
    def __init__(self) -> None:
        self.manifest = ConnectorManifest(
            name="desktop_control",
            auth_method="none",
            capabilities=[
                "computer_control.move_mouse", "computer_control.click",
                "computer_control.type_text", "computer_control.key_press",
            ],
            notes="pynput-based mouse/keyboard injection",
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

    def handlers(self) -> dict:
        return {
            "computer_control.move_mouse": self.move_mouse,
            "computer_control.click": self.click,
            "computer_control.type_text": self.type_text,
            "computer_control.key_press": self.key_press,
        }
