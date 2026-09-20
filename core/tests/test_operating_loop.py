"""Unit-level coverage of TaskWorker/OperatingLoopSupervisor that isn't
already covered by the full plan-claim-execute-verify paths in
test_end_to_end.py: unknown task types, crash/restart recovery via
lease-expiry, and the background-thread supervisor actually running
cycles on its own."""
from __future__ import annotations

import time

from aura_core.executive import GoalEngine, MandateEngine, OperatingLoopSupervisor, TaskWorker
from aura_core.executive.executive import ExecutiveIntelligence
from aura_core.governance import ActionBroker, ApprovalEngine, AuditLog, CredentialBroker, PolicyEngine, RiskEngine
from aura_core.memory import MemoryStore
from aura_core.providers import ModelRouter, OllamaProvider
from aura_core.tasks import TaskEngine


def make_stack(tmp_path):
    db_url = f"sqlite:///{tmp_path}/loop.db"
    memory = MemoryStore(db_url)
    policy = PolicyEngine(db_url)
    broker = ActionBroker(policy, RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    tasks = TaskEngine(db_url)
    goals = GoalEngine(db_url)
    worker = TaskWorker(tasks, broker, goals, memory)
    return tasks, goals, broker, worker, policy


def test_an_unrecognized_task_type_fails_closed_instead_of_being_silently_dropped(tmp_path):
    tasks, _goals, _broker, worker, _policy = make_stack(tmp_path)
    # max_attempts=1: an unrecognized task_type will never succeed no
    # matter how many times it's retried, so this test drives it straight
    # to its terminal state rather than asserting on the transient
    # RETRYING status a default-max_attempts task would land on first.
    tasks.enqueue("send_carrier_pigeon", {}, max_attempts=1)

    outcome = worker.run_once()

    assert outcome.outcome == "unknown_task_type"
    assert tasks.get(outcome.task_id).status == "FAILED"


def test_run_once_returns_none_when_the_queue_is_empty(tmp_path):
    _tasks, _goals, _broker, worker, _policy = make_stack(tmp_path)
    assert worker.run_once() is None


def test_a_worker_crash_mid_task_is_recovered_by_the_next_cycles_lease_reap(tmp_path):
    """Simulates the exact scenario section 4 of the product spec calls
    out by name: a process dies mid-task. The task's lease expires; the
    *next* operating-loop cycle -- a fresh call, exactly as if the whole
    process had restarted -- must pick it back up via
    TaskEngine.reap_expired_leases(), not lose it."""
    tasks, goals, broker, worker, policy = make_stack(tmp_path)
    policy.set_autonomy_level("filesystem.write_file", 4)
    from aura_core.connectors import ConnectorRegistry, FilesystemConnector
    ConnectorRegistry(broker).register(FilesystemConnector(str(tmp_path / "sandbox")))

    task = tasks.enqueue("execute_goal_step", {
        "goal_id": None, "action_type": "filesystem.write_file",
        "params": {"path": "recovered.txt", "content": "ok"}, "summary": "write it",
    })
    # Simulate a crash: claim it (as if a worker picked it up) but never
    # complete/fail it, and force the lease into the past.
    claimed = tasks.claim_next("dead-worker", lease_seconds=1)
    assert claimed.id == task.id
    time.sleep(1.1)

    reaped = tasks.reap_expired_leases()
    assert reaped == 1
    assert tasks.get(task.id).status == "QUEUED"

    outcome = worker.run_once()

    assert outcome.outcome == "executed"
    assert (tmp_path / "sandbox" / "recovered.txt").read_text() == "ok"


def test_the_background_supervisor_thread_actually_runs_cycles_on_its_own(tmp_path):
    """Not just that run_cycle_once() works when called directly -- the
    background thread this project's `aura loop run` starts must itself
    advance real state without anything else driving it."""
    db_url = f"sqlite:///{tmp_path}/loop_bg.db"
    memory = MemoryStore(db_url)
    policy = PolicyEngine(db_url)
    broker = ActionBroker(policy, RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    tasks = TaskEngine(db_url)
    goals = GoalEngine(db_url)
    mandates = MandateEngine(db_url)

    unreachable = OllamaProvider(host="http://127.0.0.1:1", model="llama3.1")
    router = ModelRouter(primary=unreachable, allow_test_fallback=True)
    executive = ExecutiveIntelligence(goals, tasks, memory, router, broker=broker)
    worker = TaskWorker(tasks, broker, goals, memory)
    supervisor = OperatingLoopSupervisor(executive, worker, tasks, mandates, goals, interval_seconds=0.1)

    goal = goals.create("g", success_metric="m", budget={}, stop_conditions=["s"], review_interval_seconds=0)
    goals.activate(goal.id)

    thread = supervisor.start_in_background()
    try:
        deadline = time.time() + 5
        while supervisor.cycles_run < 2 and time.time() < deadline:
            time.sleep(0.05)
        assert supervisor.cycles_run >= 2
        # The due goal must have actually been reviewed by the background
        # thread itself, with no test code calling run_review_cycle().
        assert goals.get(goal.id).last_reviewed_at is not None
    finally:
        supervisor.stop()
        thread.join(timeout=5)
        assert not thread.is_alive()
