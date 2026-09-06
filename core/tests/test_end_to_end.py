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
from aura_core.executive import ExecutiveIntelligence, GoalEngine, MandateEngine, OperatingLoopSupervisor, TaskWorker
from aura_core.governance import ActionBroker, ApprovalEngine, AuditLog, CredentialBroker, PolicyEngine, RiskEngine
from aura_core.governance.action_broker import HandlerResult
from aura_core.governance.risk_engine import ActionRequest
from aura_core.guardian import SecurityGuardian
from aura_core.memory import MemoryStore
from aura_core.providers import ModelRouter
from aura_core.status import CapabilityStatus
from aura_core.tasks import TaskEngine


class ScriptedJsonProvider:
    """Stands in for a real model that has been asked to plan a step and
    actually returned a valid, executable plan -- the deterministic
    test-mode provider (DeterministicTestProvider) only ever echoes
    prompt text, which is realistic for "prove streaming works" but
    useless for exercising the structured-plan path for real."""
    name = "scripted-json"

    def __init__(self, response: str) -> None:
        self._response = response

    async def is_available(self) -> bool:
        return True

    async def generate_stream(self, prompt: str, history: list[dict[str, str]]):
        for chunk in self._response.split(" "):
            yield chunk + " "


def build_full_stack(tmp_path, provider=None):
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
    mandates = MandateEngine(db_url)

    router = ModelRouter(primary=provider or ScriptedJsonProvider('{"advisory": "no plan"}'), allow_test_fallback=True)
    executive = ExecutiveIntelligence(goals, tasks, memory, router, broker=broker)
    worker = TaskWorker(tasks, broker, goals, memory)
    loop = OperatingLoopSupervisor(executive, worker, tasks, mandates, goals)

    return {
        "memory": memory, "policy": policy, "audit": audit, "guardian": guardian,
        "broker": broker, "tasks": tasks, "goals": goals, "mandates": mandates,
        "executive": executive, "worker": worker, "loop": loop,
    }


@pytest.mark.asyncio
async def test_the_operating_loop_plans_claims_and_executes_a_real_action(tmp_path):
    """The gap docs/FINAL_COMPLETION_AUDIT.md flagged as the single
    biggest one, closed and proven end to end: create+activate a goal ->
    a mandate owns it as a workstream -> the operating loop's one cycle
    plans a structured, broker-constrained step (a real model naming a
    real registered action_type) -> claims and executes the resulting
    task through the real Action-Broker-gated filesystem connector ->
    the workstream is marked verifying -> a Decision records the real
    outcome -> the audit chain is still valid -> Guardian never had to
    freeze anything. No step here is hand-orchestrated the way the
    pre-operating-loop version of this test had to be -- run_cycle_once()
    does the whole plan-claim-execute-verify sequence for real."""
    provider = ScriptedJsonProvider(
        '{"action_type": "filesystem.write_file", '
        '"params": {"path": "status.txt", "content": "all clients contacted today"}, '
        '"reasoning": "write the daily status note"}'
    )
    stack = build_full_stack(tmp_path, provider=provider)
    goals, mandates, loop, broker = stack["goals"], stack["mandates"], stack["loop"], stack["broker"]

    mandate = mandates.create(
        "Run Gridkeep", mission="Keep Gridkeep operations moving day to day.",
        objectives=["Write a daily status note"], kpis=[{"name": "notes_written", "target": 1, "current": 0}],
        constraints=["never spend money without approval"],
    )
    mandates.activate(mandate.id)

    goal = goals.create(
        "Write today's status note", success_metric="note file exists",
        budget={}, stop_conditions=["stop if disk is full"], review_interval_seconds=0,
    )
    goals.activate(goal.id)
    goals.set_mandate(goal.id, mandate.id)

    stack["policy"].set_autonomy_level("filesystem.write_file", 4)
    ConnectorRegistry(broker).register(FilesystemConnector(str(tmp_path / "sandbox")))

    outcomes = await loop.run_cycle_once()

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "executed"
    assert (tmp_path / "sandbox" / "status.txt").read_text() == "all clients contacted today"
    assert goals.get(goal.id).status == "verifying"

    decisions = stack["memory"].decisions_for_goal(goal.id)
    assert len(decisions) == 2  # the plan, then the real execution outcome
    assert "executed 'filesystem.write_file'" in decisions[-1].statement

    report = mandates.report(mandate.id, goals, stack["memory"])
    assert report.counts.get("IN_PROGRESS") == 1

    verification = stack["audit"].verify_chain()
    assert verification.valid is True
    assert stack["guardian"].recent_events() == []  # nothing anomalous happened


@pytest.mark.asyncio
async def test_the_operating_loop_never_fabricates_an_action_it_cannot_execute(tmp_path):
    """When the model doesn't name a real, registered action type
    (whether it stays silent, hallucinates one, or explicitly declines),
    the loop must record an honest advisory outcome -- never invent an
    ActionRequest to submit anyway. This is the safety property the
    whole plan/parse_plan design exists for."""
    provider = ScriptedJsonProvider('{"action_type": "launch_the_nukes", "params": {}}')
    stack = build_full_stack(tmp_path, provider=provider)
    goals, loop = stack["goals"], stack["loop"]

    goal = goals.create(
        "Do something", success_metric="something happens", budget={},
        stop_conditions=["stop if unclear"], review_interval_seconds=0,
    )
    goals.activate(goal.id)

    outcomes = await loop.run_cycle_once()

    assert len(outcomes) == 1
    assert outcomes[0].outcome == "advisory"
    assert goals.get(goal.id).status == "active"  # untouched -- nothing executed, nothing broke it either


@pytest.mark.asyncio
async def test_a_denied_step_blocks_its_workstream_instead_of_silently_stalling(tmp_path):
    """A structurally valid, registered action that the Policy Engine
    denies (autonomy level 0, the default) must leave a clearly blocked
    workstream behind -- not an "active" goal that looks fine but never
    actually progresses."""
    provider = ScriptedJsonProvider(
        '{"action_type": "filesystem.write_file", "params": {"path": "x.txt", "content": "x"}}'
    )
    stack = build_full_stack(tmp_path, provider=provider)
    goals, loop, broker = stack["goals"], stack["loop"], stack["broker"]
    ConnectorRegistry(broker).register(FilesystemConnector(str(tmp_path / "sandbox")))
    # No autonomy level set for filesystem.write_file -> defaults to 0 (DENY).

    goal = goals.create(
        "Write a file", success_metric="file exists", budget={},
        stop_conditions=["stop if disk full"], review_interval_seconds=0,
    )
    goals.activate(goal.id)

    outcomes = await loop.run_cycle_once()

    assert outcomes[0].outcome == "denied"
    assert goals.get(goal.id).status == "blocked"
    assert not (tmp_path / "sandbox" / "x.txt").exists()


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
