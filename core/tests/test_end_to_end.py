"""End-to-end tests tying multiple real subsystems together in one flow,
as opposed to each module's own unit tests. Every piece here is the real
class used in production wiring (runtime.py) -- nothing is swapped for a
test double except the model provider (which the whole codebase already
treats as swappable via AURA_ENV=test) and, in one test, a stand-in
connector handler standing in for a not-yet-built specialist agent.
"""
from __future__ import annotations

import pytest

from aura_core.connectors import ConnectorRegistry, FilesystemConnector
from aura_core.executive import ExecutiveIntelligence, GoalEngine
from aura_core.governance import ActionBroker, ApprovalEngine, AuditLog, CredentialBroker, PolicyEngine, RiskEngine
from aura_core.governance.action_broker import HandlerResult
from aura_core.governance.risk_engine import ActionRequest
from aura_core.guardian import SecurityGuardian
from aura_core.memory import MemoryStore
from aura_core.providers import ModelRouter, OllamaProvider
from aura_core.status import CapabilityStatus
from aura_core.tasks import TaskEngine


def build_full_stack(tmp_path):
    db_url = f"sqlite:///{tmp_path}/e2e.db"
    memory = MemoryStore(db_url)
    policy = PolicyEngine(db_url)
    risk = RiskEngine()
    approvals = ApprovalEngine(db_url)
    credentials = CredentialBroker()
    audit = AuditLog(db_url)
    guardian = SecurityGuardian(audit, policy, db_url)
    broker = ActionBroker(policy, risk, approvals, credentials, audit, on_audit=guardian.evaluate)
    tasks = TaskEngine(db_url)
    goals = GoalEngine(db_url)

    unreachable = OllamaProvider(host="http://127.0.0.1:1", model="llama3.1")
    router = ModelRouter(primary=unreachable, allow_test_fallback=True)
    executive = ExecutiveIntelligence(goals, tasks, memory, router)

    return {
        "memory": memory, "policy": policy, "audit": audit, "guardian": guardian,
        "broker": broker, "tasks": tasks, "goals": goals, "executive": executive,
    }


@pytest.mark.asyncio
async def test_goal_to_task_to_executed_action_end_to_end(tmp_path):
    """Full loop: create+activate a goal -> Executive reviews it (real
    model-router call, test provider) -> a Decision is recorded and a
    Task enqueued -> a worker claims the task and performs a real,
    Action-Broker-gated filesystem write standing in for a future
    specialist agent's actual work -> the task completes -> the audit
    chain is still valid -> Guardian never had to freeze anything."""
    stack = build_full_stack(tmp_path)
    goals, executive, tasks, broker = stack["goals"], stack["executive"], stack["tasks"], stack["broker"]

    goal = goals.create(
        "Write today's status note", success_metric="note file exists",
        budget={}, stop_conditions=["stop if disk is full"], review_interval_seconds=0,
    )
    goals.activate(goal.id)

    outcomes = await executive.run_review_cycle()
    assert len(outcomes) == 1
    assert outcomes[0].error is None

    # Wire a handler that performs the reviewed task for real, through
    # the real Action Broker -- standing in for a specialist agent that
    # doesn't exist yet (docs/agents/README.md), the same way this
    # session has stood in real connectors for not-yet-integrated
    # vendors elsewhere.
    stack["policy"].set_autonomy_level("filesystem.write_file", 4)
    connector = FilesystemConnector(str(tmp_path / "sandbox"))
    ConnectorRegistry(broker).register(connector)

    claimed = tasks.claim_next("worker-1")
    assert claimed is not None
    assert claimed.task_type == "execute_goal_step"

    write_outcome = broker.submit(ActionRequest(
        action_type="filesystem.write_file",
        params={"path": "status.txt", "content": claimed.payload["plan"]},
    ))
    assert write_outcome.status.value == "EXECUTED"
    tasks.complete(claimed.id, {"result": "written"})

    assert tasks.get(claimed.id).status == "COMPLETED"
    assert (tmp_path / "sandbox" / "status.txt").exists()

    decisions = stack["memory"].decisions_for_goal(goal.id)
    assert len(decisions) == 1

    verification = stack["audit"].verify_chain()
    assert verification.valid is True
    assert stack["guardian"].recent_events() == []  # nothing anomalous happened


def test_a_misbehaving_caller_gets_frozen_before_causing_real_damage(tmp_path):
    """A different end-to-end path: something starts hammering a
    RED-tier action. Every individual request is correctly gated
    (PENDING_APPROVAL, never silently executed), and Security Guardian
    freezes the whole system once the burst is unambiguous -- proving
    the Action Broker and Security Guardian genuinely compose, not just
    pass their own isolated unit tests."""
    stack = build_full_stack(tmp_path)
    broker, policy, guardian = stack["broker"], stack["policy"], stack["guardian"]
    policy.set_autonomy_level("finance.change_bank_details", 5)  # even at the top level...

    executed_count = 0

    def handler(_request):
        nonlocal executed_count
        executed_count += 1
        return HandlerResult(CapabilityStatus.LIVE, "changed")

    broker.register_handler("finance.change_bank_details", handler)

    outcomes = [
        broker.submit(ActionRequest(action_type="finance.change_bank_details"))
        for _ in range(3)
    ]

    assert all(o.status.value == "PENDING_APPROVAL" for o in outcomes)  # ...RED always needs approval
    assert executed_count == 0  # never reached the handler
    assert policy.is_kill_switch_engaged() is True  # Guardian's red_tier_velocity rule fired
    assert any(e.rule_name == "red_tier_velocity" for e in guardian.recent_events())

    # And now the system is frozen -- even a legitimate, previously-fine
    # action is blocked until the owner reviews and disengages.
    blocked = broker.submit(ActionRequest(action_type="status.read"))
    assert blocked.status.value == "KILL_SWITCH_ENGAGED"
