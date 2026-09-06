"""Capability status registry.

Every capability in AURA reports one of six states. A capability is never
marked LIVE because its code exists — only because a real operation against
it has been authenticated and verified. This registry is the single source
of truth queried by the CLI, the API, and (eventually) the owner interface,
so "what actually works right now" is always one query away, never a claim
buried in a doc.
"""
from __future__ import annotations

import enum
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


class CapabilityStatus(str, enum.Enum):
    LIVE = "LIVE"
    READY_TO_CONNECT = "READY_TO_CONNECT"
    DEGRADED = "DEGRADED"
    NOT_CONNECTED = "NOT_CONNECTED"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class CapabilityRecord:
    name: str
    status: CapabilityStatus
    detail: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class StatusRegistry:
    """Thread-safe in-memory registry. Backed by nothing durable on purpose —
    status is a live health signal, recomputed on check, not a memory record."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, CapabilityRecord] = {}

    def set(self, name: str, status: CapabilityStatus, detail: str = "") -> None:
        with self._lock:
            self._records[name] = CapabilityRecord(name=name, status=status, detail=detail)

    def get(self, name: str) -> CapabilityRecord | None:
        with self._lock:
            return self._records.get(name)

    def snapshot(self) -> dict[str, dict]:
        with self._lock:
            return {
                name: {
                    "status": rec.status.value,
                    "detail": rec.detail,
                    "checked_at": rec.checked_at.isoformat(),
                }
                for name, rec in sorted(self._records.items())
            }


# Process-wide registry. Seeded with the honest current state of this build —
# most entries are NOT_CONNECTED / READY_TO_CONNECT because most of the
# mega-prompt's scope has not been implemented yet. Update these only when a
# capability has actually been wired and verified, not when code is written.
registry = StatusRegistry()

registry.set("memory.store", CapabilityStatus.UNAVAILABLE, "not yet initialized")
registry.set("model.ollama", CapabilityStatus.UNAVAILABLE, "not yet health-checked")
registry.set("actions.deterministic", CapabilityStatus.LIVE, "in-process registry, no external dependency")
registry.set("api.server", CapabilityStatus.UNAVAILABLE, "not started")

# Capabilities named in the mega-prompt that this build deliberately does not
# implement yet. Listed explicitly so "what's missing" is never ambiguous.
for _name, _detail in [
    ("voice.wake_word", "no audio hardware in this build environment; requires local implementation + testing on your machine"),
    ("voice.stt", "not implemented"),
    ("voice.tts", "not implemented"),
    ("telephony.inbound", "not implemented; requires a telephony/SIP provider and your explicit authorization"),
    ("telephony.outbound", "not implemented; requires a telephony/SIP provider and your explicit authorization"),
    ("connector.email", "not implemented; requires OAuth credentials you provide"),
    ("connector.social", "not implemented; requires provider API credentials you provide"),
    ("connector.crm", "not implemented"),
    ("connector.finance", "not implemented; execution requires the financial-control design in docs/architecture/06-financial-control.md"),
    ("computer_control.desktop", "not implemented; requires a native agent running on your machine with explicit scoped authority"),
    ("security.pentest_tools", "not implemented; requires explicit written authorization and scope per engagement"),
    ("windows.native_shell", "not implemented in this build; this environment cannot build or run a Windows application"),
]:
    registry.set(_name, CapabilityStatus.NOT_CONNECTED, _detail)
