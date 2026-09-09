"""Telephony abstraction. `MockTelephonyProvider` is real, working code —
an in-memory call log a real backend (Twilio, a SIP trunk) would sit
behind — genuinely testable without any phone provider or account.
Wiring a real backend is REQUIRES_EXTERNAL_PROVIDER (needs a telephony
account and its credentials), tracked in docs/project-status.md, not
implemented here.

health_check() reports the mock as READY_TO_CONNECT, never LIVE -- no
real phone call has ever gone through this code, so claiming LIVE would
be exactly the "simulated success" this system must never fabricate.
Every CallRecord also carries `provider` ("mock" here) so any consumer
of a call's outcome -- audit log, World Model, an owner reading
`/audit` -- can tell a simulated call apart from a real one even though
the Action Broker still reports the request itself as EXECUTED (the
governed pipeline genuinely ran the registered handler; that handler
just isn't backed by real telephony infrastructure yet).
"""
from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..governance.action_broker import ActionRequest, HandlerResult
from ..status import CapabilityStatus
from .base import Connector, ConnectorManifest


@dataclass
class CallRecord:
    id: str
    to: str
    from_: str
    status: str  # "queued" | "completed" | "failed"
    message: str
    provider: str = "mock"  # "mock" until a real backend (twilio/sip/...) is wired
    placed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id, "to": self.to, "from": self.from_,
            "status": self.status, "message": self.message, "provider": self.provider,
            "placed_at": self.placed_at.isoformat(),
        }


class TelephonyProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def place_call(self, *, to: str, from_: str, message: str) -> CallRecord: ...


class MockTelephonyProvider(TelephonyProvider):
    """No real phone network involved — records what AURA *would* have
    said and to whom, so the Action Broker / policy / audit pipeline
    around telephony can be built and tested today, ahead of any real
    account existing."""

    def __init__(self) -> None:
        self.calls: list[CallRecord] = []

    def is_available(self) -> bool:
        return True

    def place_call(self, *, to: str, from_: str, message: str) -> CallRecord:
        record = CallRecord(id=str(uuid.uuid4()), to=to, from_=from_, status="completed", message=message)
        self.calls.append(record)
        return record


class TelephonyConnector(Connector):
    def __init__(self, provider: TelephonyProvider, from_number: str = "+10000000000") -> None:
        self._provider = provider
        self._from_number = from_number
        is_mock = isinstance(provider, MockTelephonyProvider)
        self.manifest = ConnectorManifest(
            name="telephony",
            auth_method="none" if is_mock else "custom",
            required_credentials=[] if is_mock else ["account_sid", "auth_token"],
            capabilities=["telephony.call"],
            notes="mock provider (no real calls placed)" if is_mock else "real backend",
        )

    def health_check(self) -> HandlerResult:
        if not self._provider.is_available():
            return HandlerResult(CapabilityStatus.UNAVAILABLE, "provider reports unavailable")
        if isinstance(self._provider, MockTelephonyProvider):
            return HandlerResult(CapabilityStatus.READY_TO_CONNECT, "mock provider only -- no real telephony backend configured")
        return HandlerResult(CapabilityStatus.READY_TO_CONNECT, "provider reports available")

    def call(self, request: ActionRequest) -> HandlerResult:
        record = self._provider.place_call(
            to=request.params["to"], from_=self._from_number, message=request.params.get("message", ""),
        )
        return HandlerResult(CapabilityStatus.LIVE, json.dumps(record.to_dict()))

    def handlers(self) -> dict:
        return {"telephony.call": self.call}
