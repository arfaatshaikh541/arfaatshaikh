"""Financial connector -- interface only, per docs/architecture/06-
financial-control.md and the owner's explicit instruction to build
high-risk capabilities (finance, telephony, social posting, computer
control) as interfaces only, with no live execution. `MockPaymentProvider`
never moves real money: `prepare_transaction` only ever produces a draft
record (financial-control.md's layer 2 -- "preparation alone has no
effect on real funds"), and there is no handler here for actually
executing a transfer against a real payment rail at all. Wiring a real
payment provider (a bank API, a payment processor) is
REQUIRES_EXTERNAL_PROVIDER + REQUIRES_USER_CREDENTIAL, and implementing
financial-control.md's full layered system (budget envelopes, merchant
allowlists, velocity limits, dual authorization) is a separate, larger
design-and-build effort tracked in BLOCKERS.md -- not something a mock
connector can honestly claim to provide.

Unlike filesystem/http/desktop_control/telephony, this connector is
deliberately NOT auto-registered by build_runtime() -- there is no
scenario where an owner wants financial action types reachable by
default before the layered controls above exist, even in prepare-only
mock form. Register it explicitly if you want to exercise the Action
Broker / policy / audit pipeline around a financial action type today.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..governance.action_broker import ActionRequest, HandlerResult
from ..status import CapabilityStatus
from .base import Connector, ConnectorManifest


@dataclass
class TransactionDraft:
    id: str
    amount: float
    currency: str
    recipient: str
    memo: str
    status: str  # "drafted" -- this connector never produces any other status
    prepared_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PaymentProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def prepare_transaction(self, *, amount: float, currency: str, recipient: str, memo: str) -> TransactionDraft: ...


class MockPaymentProvider(PaymentProvider):
    """No real bank or payment processor involved -- records a draft
    transaction so the Action Broker / policy / audit pipeline around
    financial action types can be built and tested today, ahead of any
    real payment provider integration or the full layered budget/
    dual-authorization system financial-control.md describes."""

    def __init__(self) -> None:
        self.drafts: list[TransactionDraft] = []

    def is_available(self) -> bool:
        return True

    def prepare_transaction(self, *, amount: float, currency: str, recipient: str, memo: str) -> TransactionDraft:
        draft = TransactionDraft(
            id=str(uuid.uuid4()), amount=amount, currency=currency,
            recipient=recipient, memo=memo, status="drafted",
        )
        self.drafts.append(draft)
        return draft


class FinanceConnector(Connector):
    def __init__(self, provider: PaymentProvider) -> None:
        self._provider = provider
        is_mock = isinstance(provider, MockPaymentProvider)
        self.manifest = ConnectorManifest(
            name="finance",
            auth_method="none" if is_mock else "custom",
            required_credentials=[] if is_mock else ["payment_provider_api_key"],
            capabilities=["finance.prepare_transaction"],
            notes=(
                "mock provider (drafts only, no real funds ever move; "
                "no handler exists here for executing a real transfer)"
                if is_mock else "real backend"
            ),
        )

    def health_check(self) -> HandlerResult:
        if self._provider.is_available():
            status = CapabilityStatus.LIVE if isinstance(self._provider, MockPaymentProvider) else CapabilityStatus.READY_TO_CONNECT
            return HandlerResult(status, "provider reports available")
        return HandlerResult(CapabilityStatus.UNAVAILABLE, "provider reports unavailable")

    def prepare_transaction(self, request: ActionRequest) -> HandlerResult:
        draft = self._provider.prepare_transaction(
            amount=float(request.params["amount"]),
            currency=request.params.get("currency", "USD"),
            recipient=request.params["recipient"],
            memo=request.params.get("memo", ""),
        )
        return HandlerResult(
            CapabilityStatus.LIVE,
            f"draft {draft.id}: {draft.amount} {draft.currency} to {draft.recipient} ({draft.status})",
        )

    def handlers(self) -> dict:
        return {"finance.prepare_transaction": self.prepare_transaction}
