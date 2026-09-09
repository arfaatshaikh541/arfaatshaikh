"""UI Automation / accessibility-tree targeting -- the interface section
16 asks desktop control to prefer over blind screen coordinates (find the
"Submit" button by name/role, rather than clicking wherever it happened
to render last).

The real backend for this is platform-specific: Windows' own UI
Automation API (`System.Windows.Automation`) on Windows, AT-SPI on Linux,
the Accessibility API on macOS. Genuinely exercising the Windows backend
needs a real Windows desktop this sandbox does not have
(REQUIRES_WINDOWS_RUNTIME, per docs/FINAL_COMPLETION_AUDIT.md's Desktop
control row). What is buildable and testable here, following the same
"interface now, real backend later" pattern as MockPaymentProvider/
MockTelephonyProvider/MockCloudProvider, is the provider interface itself
plus the governed Action-Broker plumbing that a real per-platform backend
plugs into later -- `MockUiAutomationProvider` is a fixed, in-memory
accessibility tree used to prove that plumbing end to end, never
presented as a real UI Automation or AT-SPI implementation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class UiElement:
    """A located UI element's identity and screen geometry -- enough to
    resolve a click/type target without the caller ever specifying raw
    coordinates."""
    name: str
    role: str
    x: int
    y: int
    width: int
    height: int
    automation_id: str | None = None

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


class UiAutomationProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def find_element(
        self, *, name: str | None = None, role: str | None = None, automation_id: str | None = None,
    ) -> UiElement | None: ...


class MockUiAutomationProvider(UiAutomationProvider):
    """No real platform accessibility API involved -- a fixed, in-memory
    tree of elements the caller registers ahead of time, so the governed
    find/click-by-element pipeline can be built and tested today, ahead
    of a real Windows UI Automation or Linux AT-SPI backend."""

    def __init__(self, elements: list[UiElement] | None = None) -> None:
        self._elements = list(elements or [])

    def add_element(self, element: UiElement) -> None:
        self._elements.append(element)

    def is_available(self) -> bool:
        return True

    def find_element(
        self, *, name: str | None = None, role: str | None = None, automation_id: str | None = None,
    ) -> UiElement | None:
        for element in self._elements:
            if name is not None and element.name != name:
                continue
            if role is not None and element.role != role:
                continue
            if automation_id is not None and element.automation_id != automation_id:
                continue
            return element
        return None
