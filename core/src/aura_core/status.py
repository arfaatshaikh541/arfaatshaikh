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

# Capabilities that are code-complete and tested with real local
# implementations, but whose true status can only be known once
# build_runtime() actually runs a health check (voice models need to be
# downloaded to .models/; connectors are registered at startup). Seeded
# here as NOT_CONNECTED/UNAVAILABLE so a query before startup is honest,
# never seeded as LIVE from configuration alone -- see runtime.py and
# voice/config.py for what overwrites these on a real run.
for _name, _detail in [
    ("voice.wake_word", "implemented (openWakeWord/ONNX); not yet health-checked in this process"),
    ("voice.stt", "implemented (sherpa-onnx Whisper-tiny.en); not yet health-checked in this process"),
    ("voice.tts", "implemented (sherpa-onnx Piper/VITS); not yet health-checked in this process"),
    ("telephony.inbound", "not implemented; inbound calls require a real telephony/SIP provider and your explicit authorization"),
    ("telephony.outbound", "mock provider implemented (connector.telephony); a real provider is REQUIRES_EXTERNAL_PROVIDER"),
    ("connector.email", "implemented (SMTP send); requires you to configure AURA_SMTP_HOST + credentials"),
    ("connector.social", "not implemented; each vendor needs its own REST mapping plus your API credentials"),
    ("connector.crm", "generic REST connector implemented; each vendor needs its own mapping plus your API credentials"),
    ("connector.finance", "mock provider implemented (drafts only, never moves real funds); not auto-registered by build_runtime() -- see connectors/finance_connector.py. Real execution requires the financial-control design in docs/architecture/06-financial-control.md and your explicit authorization"),
    ("computer_control.desktop", "implemented (pynput); not yet health-checked in this process"),
    ("security.pentest_tools", "not implemented; requires explicit written authorization and scope per engagement"),
    ("windows.native_shell", "source implemented (WPF); this build environment cannot compile or run a Windows application to verify it"),
]:
    registry.set(_name, CapabilityStatus.NOT_CONNECTED, _detail)
