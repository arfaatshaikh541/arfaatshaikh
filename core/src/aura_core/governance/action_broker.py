"""Action Broker: the single mandatory execution gateway.

Per docs/adr/0001-action-broker-single-choke-point.md: every consequential
action — the deterministic commands wired in today, and every future
connector, computer-control action, email, social post, call, finance
action, deployment, and security action — is submitted here. Nothing else
in this codebase is permitted to call a handler directly; `register_handler`
is the only way a capability becomes reachable, and `submit` /
`resume_after_approval` are the only ways it ever executes.

Sequence, unconditionally, on every call: kill switch -> risk
classification -> policy evaluation -> (approval, if required) ->
credential issuance -> handler execution -> audit write. The audit write
happens on every branch, including denials and kill-switch rejections —
there is no early return that skips it.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from ..status import CapabilityStatus
from .approval_engine import ApprovalEngine
from .audit_log import AuditLog
from .credential_broker import CredentialBroker
from .policy_engine import PolicyDecision, PolicyEngine
from .rate_limiter import RateLimiter
from .risk_engine import ActionRequest, RiskEngine, RiskTier


class OutcomeStatus(str, Enum):
    EXECUTED = "EXECUTED"
    DENIED = "DENIED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    KILL_SWITCH_ENGAGED = "KILL_SWITCH_ENGAGED"
    NO_HANDLER = "NO_HANDLER"
    RATE_LIMITED = "RATE_LIMITED"


@dataclass
class HandlerResult:
    status: CapabilityStatus
    message: str


ActionHandler = Callable[[ActionRequest], HandlerResult]


@dataclass
class ActionOutcome:
    status: OutcomeStatus
    message: str
    approval_id: str | None = None
    risk_tier: RiskTier | None = None


class ActionBroker:
    def __init__(
        self, policy_engine: PolicyEngine, risk_engine: RiskEngine,
        approval_engine: ApprovalEngine, credential_broker: CredentialBroker,
        audit_log: AuditLog, rate_limiter: RateLimiter | None = None,
        on_audit: Callable[[], None] | None = None,
    ) -> None:
        self._policy = policy_engine
        self._risk = risk_engine
        self._approvals = approval_engine
        self._credentials = credential_broker
        self._audit = audit_log
        self._rate_limiter = rate_limiter or RateLimiter()
        self._on_audit = on_audit
        self._handlers: dict[str, ActionHandler] = {}

    def register_handler(self, action_type: str, handler: ActionHandler) -> None:
        self._handlers[action_type] = handler

    # -- Entry points ---------------------------------------------------------
    def submit(self, request: ActionRequest) -> ActionOutcome:
        if self._policy.is_kill_switch_engaged():
            outcome = ActionOutcome(OutcomeStatus.KILL_SWITCH_ENGAGED, "kill switch is engaged; no actions execute")
            self._audit_record(request, risk_tier=None, decision="KILL_SWITCH", approval_id=None, outcome=outcome)
            return outcome

        if not self._rate_limiter.allow(request.action_type):
            outcome = ActionOutcome(OutcomeStatus.RATE_LIMITED, f"rate limit exceeded for '{request.action_type}'")
            self._audit_record(request, risk_tier=None, decision="RATE_LIMITED", approval_id=None, outcome=outcome)
            return outcome

        risk = self._risk.classify(request)
        evaluation = self._policy.evaluate(request, risk.tier)

        if evaluation.decision == PolicyDecision.DENY:
            outcome = ActionOutcome(OutcomeStatus.DENIED, evaluation.reason, risk_tier=risk.tier)
            self._audit_record(request, risk.tier, evaluation.decision.value, None, outcome)
            return outcome

        if evaluation.decision == PolicyDecision.REQUIRE_APPROVAL:
            approval = self._approvals.create(request, risk.tier, evaluation.reason)
            outcome = ActionOutcome(
                OutcomeStatus.PENDING_APPROVAL, evaluation.reason,
                approval_id=approval.id, risk_tier=risk.tier,
            )
            self._audit_record(request, risk.tier, evaluation.decision.value, approval.id, outcome)
            return outcome

        return self._execute(request, risk.tier, evaluation.decision, approval_id=None)

    def resume_after_approval(self, approval_id: str, *, approved: bool, decided_by: str) -> ActionOutcome:
        record = self._approvals.get(approval_id)
        if record is None:
            return ActionOutcome(OutcomeStatus.DENIED, f"no such approval '{approval_id}'")
        if record.status != "pending":
            return ActionOutcome(OutcomeStatus.DENIED, f"approval '{approval_id}' already {record.status}")

        self._approvals.decide(approval_id, approved=approved, decided_by=decided_by)
        request = self._approvals.to_action_request(record)
        risk_tier = RiskTier(record.risk_tier)

        if not approved:
            outcome = ActionOutcome(
                OutcomeStatus.DENIED, f"approval denied by {decided_by}",
                approval_id=approval_id, risk_tier=risk_tier,
            )
            self._audit_record(request, risk_tier, "APPROVAL_DENIED", approval_id, outcome)
            return outcome

        if self._policy.is_kill_switch_engaged():
            outcome = ActionOutcome(
                OutcomeStatus.KILL_SWITCH_ENGAGED,
                "kill switch engaged before the approved action could execute",
                approval_id=approval_id, risk_tier=risk_tier,
            )
            self._audit_record(request, risk_tier, "KILL_SWITCH", approval_id, outcome)
            return outcome

        return self._execute(request, risk_tier, PolicyDecision.ALLOW, approval_id=approval_id)

    # -- Internal ---------------------------------------------------------------
    def _execute(
        self, request: ActionRequest, risk_tier: RiskTier,
        decision: PolicyDecision, approval_id: str | None,
    ) -> ActionOutcome:
        credential = self._credentials.issue(request.action_type, scope=json.dumps(request.params))
        try:
            handler = self._handlers.get(request.action_type)
            if handler is None:
                outcome = ActionOutcome(
                    OutcomeStatus.NO_HANDLER, f"no handler registered for '{request.action_type}'",
                    approval_id=approval_id, risk_tier=risk_tier,
                )
                self._audit_record(request, risk_tier, decision.value, approval_id, outcome)
                return outcome

            result = handler(request)

            if result.status == CapabilityStatus.LIVE:
                if request.amount and request.budget_key:
                    self._policy.record_spend(request.budget_key, request.amount)
                outcome = ActionOutcome(
                    OutcomeStatus.EXECUTED, result.message,
                    approval_id=approval_id, risk_tier=risk_tier,
                )
            else:
                # Handler results that aren't LIVE (NOT_CONNECTED, DEGRADED,
                # BLOCKED_BY_POLICY, UNAVAILABLE) are reported honestly as
                # their own outcome, never laundered into EXECUTED.
                outcome = ActionOutcome(
                    OutcomeStatus.DENIED, f"[{result.status.value}] {result.message}",
                    approval_id=approval_id, risk_tier=risk_tier,
                )

            self._audit_record(request, risk_tier, decision.value, approval_id, outcome)
            return outcome
        finally:
            self._credentials.revoke(credential.token)

    def _audit_record(
        self, request: ActionRequest, risk_tier: RiskTier | None, decision: str,
        approval_id: str | None, outcome: ActionOutcome,
    ) -> None:
        self._audit.record(
            actor=request.requested_by,
            action_type=request.action_type,
            params_json=json.dumps(request.params),
            risk_tier=risk_tier.value if risk_tier else "NONE",
            decision=decision,
            approval_id=approval_id,
            result_status=outcome.status.value,
            result_message=outcome.message,
        )
        if self._on_audit is not None:
            self._on_audit()
