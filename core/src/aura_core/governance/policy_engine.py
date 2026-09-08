"""Policy Engine: deterministic, data-backed ALLOW/DENY/REQUIRE_APPROVAL
decisions. No model judgment is involved — see
docs/architecture/04-agent-architecture.md#policy-engine. This is the only
write path for autonomy levels, prohibited actions, budgets, and the kill
switch; nothing here lets a caller (including the Action Broker or any
future Executive Intelligence) grant itself more than it already has —
every mutating method here is meant to be called only from owner-authenticated
paths, never from inside an agent's own reasoning.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..memory.schema_migration import ensure_schema
from .models import ActionPolicy, BudgetEnvelope, PolicyState, ProhibitedAction
from .risk_engine import ActionRequest, RiskTier


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass
class PolicyEvaluation:
    decision: PolicyDecision
    reason: str
    autonomy_level: int


# Level -> what it permits without a RED override. See
# docs/policies/README.md#autonomy-levels. Levels 0-1 never auto-execute
# (Observe/Recommend); 2-3 always need approval (Prepare/Execute-after-
# approval are functionally the same gate from this pipeline's point of
# view: no execution without an owner decision); 4-5 execute autonomously
# subject to budget/limit checks below.
_LEVEL_BASE_DECISION: dict[int, PolicyDecision] = {
    0: PolicyDecision.DENY,
    1: PolicyDecision.DENY,
    2: PolicyDecision.REQUIRE_APPROVAL,
    3: PolicyDecision.REQUIRE_APPROVAL,
    4: PolicyDecision.ALLOW,
    5: PolicyDecision.ALLOW,
}


class PolicyEngine:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        ensure_schema(self._engine)
        self._Session = sessionmaker(bind=self._engine)
        self._ensure_policy_state_row()

    def _ensure_policy_state_row(self) -> None:
        with self._Session() as session:
            if session.get(PolicyState, 1) is None:
                session.add(PolicyState(id=1, kill_switch_engaged=False))
                session.commit()

    # -- Kill switch ----------------------------------------------------
    def is_kill_switch_engaged(self) -> bool:
        with self._Session() as session:
            state = session.get(PolicyState, 1)
            return bool(state and state.kill_switch_engaged)

    def engage_kill_switch(self) -> None:
        with self._Session() as session:
            state = session.get(PolicyState, 1)
            state.kill_switch_engaged = True
            state.updated_at = datetime.now(timezone.utc)
            session.commit()

    def disengage_kill_switch(self) -> None:
        with self._Session() as session:
            state = session.get(PolicyState, 1)
            state.kill_switch_engaged = False
            state.updated_at = datetime.now(timezone.utc)
            session.commit()

    # -- Autonomy levels --------------------------------------------------
    def has_policy(self, action_type: str) -> bool:
        with self._Session() as session:
            return session.get(ActionPolicy, action_type) is not None

    def set_autonomy_level(self, action_type: str, level: int, notes: str = "") -> None:
        if not 0 <= level <= 5:
            raise ValueError("autonomy level must be between 0 and 5")
        with self._Session() as session:
            policy = session.get(ActionPolicy, action_type)
            if policy is None:
                session.add(ActionPolicy(action_type=action_type, autonomy_level=level, notes=notes))
            else:
                policy.autonomy_level = level
                policy.notes = notes
            session.commit()

    def get_autonomy_level(self, action_type: str) -> int:
        with self._Session() as session:
            policy = session.get(ActionPolicy, action_type)
            return policy.autonomy_level if policy else 0  # fail closed

    # -- Prohibited actions -----------------------------------------------
    def prohibit(self, action_type: str, reason: str) -> None:
        with self._Session() as session:
            existing = session.get(ProhibitedAction, action_type)
            if existing is None:
                session.add(ProhibitedAction(action_type=action_type, reason=reason))
            else:
                existing.reason = reason
            session.commit()

    def unprohibit(self, action_type: str) -> None:
        with self._Session() as session:
            existing = session.get(ProhibitedAction, action_type)
            if existing is not None:
                session.delete(existing)
                session.commit()

    def is_prohibited(self, action_type: str) -> str | None:
        with self._Session() as session:
            record = session.get(ProhibitedAction, action_type)
            return record.reason if record else None

    # -- Budgets ------------------------------------------------------------
    def set_budget(self, budget_key: str, limit_amount: float) -> None:
        with self._Session() as session:
            budget = session.get(BudgetEnvelope, budget_key)
            if budget is None:
                session.add(BudgetEnvelope(budget_key=budget_key, limit_amount=limit_amount, spent_amount=0.0))
            else:
                budget.limit_amount = limit_amount
            session.commit()

    def remaining_budget(self, budget_key: str) -> float | None:
        with self._Session() as session:
            budget = session.get(BudgetEnvelope, budget_key)
            return None if budget is None else budget.limit_amount - budget.spent_amount

    def record_spend(self, budget_key: str, amount: float) -> None:
        with self._Session() as session:
            budget = session.get(BudgetEnvelope, budget_key)
            if budget is not None:
                budget.spent_amount += amount
                session.commit()

    # -- Evaluation -----------------------------------------------------------
    def evaluate(self, request: ActionRequest, risk_tier: RiskTier) -> PolicyEvaluation:
        prohibited_reason = self.is_prohibited(request.action_type)
        if prohibited_reason:
            return PolicyEvaluation(PolicyDecision.DENY, f"prohibited: {prohibited_reason}", autonomy_level=0)

        level = self.get_autonomy_level(request.action_type)

        if risk_tier == RiskTier.RED:
            # Hard architectural rule, not a level-dependent decision:
            # RED always requires explicit owner approval until a
            # separately designed, narrowly scoped exception exists.
            # None does yet. See docs/policies/README.md.
            return PolicyEvaluation(
                PolicyDecision.REQUIRE_APPROVAL,
                "RED-tier actions always require owner approval",
                level,
            )

        decision = _LEVEL_BASE_DECISION[level]
        reason = f"autonomy level {level} for '{request.action_type}' at {risk_tier.value} tier"

        if decision == PolicyDecision.ALLOW and request.amount and request.budget_key:
            remaining = self.remaining_budget(request.budget_key)
            if remaining is None:
                decision = PolicyDecision.REQUIRE_APPROVAL
                reason = f"no budget envelope configured for '{request.budget_key}'"
            elif request.amount > remaining:
                decision = PolicyDecision.REQUIRE_APPROVAL
                reason = f"amount {request.amount} exceeds remaining budget {remaining} for '{request.budget_key}'"

        return PolicyEvaluation(decision, reason, level)
