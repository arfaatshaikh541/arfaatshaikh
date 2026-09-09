"""Section 23's "reboot-resume scenario": persist state, restart the
complete runtime, verify work continues safely. Every other crash-
recovery test in this project (test_task_engine.py's lease-expiry
tests, test_operating_loop.py's simulated worker crash) rebuilds only
the engine under test, not the whole system -- this rebuilds an entire
Runtime from scratch via build_runtime(), the same function the real
CLI/API entrypoints use, proving state survives a genuine "the process
was killed and started again" scenario rather than just "one object's
own internal state machine recovers."

conftest.py's autouse fixture sets AURA_DATABASE_URL once per test to a
tmp_path-based file; calling build_runtime() twice in the same test
reuses that same on-disk database across both calls, exactly the way a
real restart would reuse the same install's database file.
"""
from __future__ import annotations

import time

import pytest

from aura_core.runtime import build_runtime


@pytest.mark.asyncio
async def test_mandate_and_workstream_state_survives_a_full_runtime_rebuild(tmp_path):
    runtime_a = build_runtime()

    mandate = runtime_a.mandates.create(
        "Run Gridkeep", mission="Keep operations moving.",
        objectives=["Answer inquiries within a day"],
        kpis=[{"name": "response_hours", "target": 24, "current": 0}],
        constraints=["never send without review"],
    )
    runtime_a.mandates.activate(mandate.id)

    goal = runtime_a.goals.create(
        "Write today's status note", success_metric="note exists",
        budget={}, stop_conditions=["stop if disk full"], review_interval_seconds=3600,
    )
    runtime_a.goals.activate(goal.id)
    runtime_a.goals.set_mandate(goal.id, mandate.id)
    runtime_a.goals.mark_blocked(goal.id)  # simulate real prior progress, not just draft state

    decision = runtime_a.memory.record_decision(
        goal=goal.id, statement="Draft the note manually pending approval",
        reasoning="autonomy level too low to send automatically", source="operating_loop",
    )

    # The process is gone -- nothing from runtime_a is touched again.
    del runtime_a

    runtime_b = build_runtime()

    restored_mandate = runtime_b.mandates.get(mandate.id)
    restored_goal = runtime_b.goals.get(goal.id)
    restored_decisions = runtime_b.memory.decisions_for_goal(goal.id)

    assert restored_mandate is not None
    assert restored_mandate.status == "active"
    assert restored_mandate.title == "Run Gridkeep"
    assert restored_goal is not None
    assert restored_goal.status == "blocked"
    assert restored_goal.mandate_id == mandate.id
    assert [d.id for d in restored_decisions] == [decision.id]

    report = runtime_b.mandates.report(mandate.id, runtime_b.goals, runtime_b.memory)
    assert report.counts == {"FAILED": 1}  # "blocked" buckets into FAILED in the report vocabulary


@pytest.mark.asyncio
async def test_a_task_claimed_but_never_completed_before_the_crash_is_recovered_and_finished_after_restart(tmp_path):
    """The real "someone pulled the power mid-task" case: a task is
    claimed (as a live worker would) and then simply abandoned --
    nothing calls complete() or fail() on it, simulating the process
    dying between claiming the work and finishing it. A fresh Runtime,
    built later against the same database, must reap the expired lease
    and actually finish the real, governed, Action-Broker-gated work --
    not just mark it retriable."""
    runtime_a = build_runtime()
    runtime_a.policy.set_autonomy_level("filesystem.write_file", 4)
    # build_runtime() already auto-registers its own FilesystemConnector
    # at settings.filesystem_sandbox_dir (see runtime.py's
    # _build_connectors) -- no need to register a second one here, and
    # doing so at a different path would only prove the wrong
    # connector's write succeeded when runtime_b rebuilds its own.
    sandbox_dir = runtime_a.settings.filesystem_sandbox_dir

    goal = runtime_a.goals.create(
        "Write the recovery marker", success_metric="file exists",
        budget={}, stop_conditions=["stop if disk full"],
    )
    runtime_a.goals.activate(goal.id)

    task = runtime_a.tasks.enqueue("execute_goal_step", {
        "goal_id": goal.id, "action_type": "filesystem.write_file",
        "params": {"path": "recovered-after-restart.txt", "content": "survived a real restart"},
        "summary": "write the recovery marker",
    })

    # Simulate a worker claiming it and then the whole process dying --
    # a very short lease so it's already expired by the time the next
    # "process" (runtime_b) looks at it, with nothing here ever calling
    # complete() or fail().
    claimed = runtime_a.tasks.claim_next("worker-a", lease_seconds=1)
    assert claimed.id == task.id
    del runtime_a
    time.sleep(1.1)

    runtime_b = build_runtime()
    outcomes = await runtime_b.operating_loop.run_cycle_once()

    assert any(o.task_id == task.id and o.outcome == "executed" for o in outcomes)
    assert runtime_b.tasks.get(task.id).status == "COMPLETED"
    from pathlib import Path
    assert (Path(sandbox_dir) / "recovered-after-restart.txt").read_text() == "survived a real restart"
