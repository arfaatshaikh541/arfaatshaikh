"""TaskWorker + OperatingLoopSupervisor: the piece
docs/FINAL_COMPLETION_AUDIT.md identifies as the single biggest gap in
the whole system -- ExecutiveIntelligence.run_review_cycle() enqueues
execute_goal_step tasks, but nothing in production code ever called
TaskEngine.claim_next() to actually run them. This closes that loop:

    reap expired leases -> promote ready blocked tasks -> plan (review
    due goals) -> observe due mandates -> drain the task queue through
    the real Action Broker -> sleep -> repeat

Everything here is built on TaskEngine's own persisted state as the
single source of truth, never in-memory loop state -- a crash mid-cycle
recovers exactly the way any other crashed task does (lease-expiry
reap, already covered by test_task_engine.py), because the *next* time
this loop runs (a fresh process, after a restart) it starts with the
same reap-then-drain sequence regardless of how it was interrupted.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass

from ..governance.action_broker import ActionBroker, OutcomeStatus
from ..governance.risk_engine import ActionRequest
from ..memory import MemoryStore
from ..memory.world_model import WorldModelStore
from ..tasks import TaskEngine
from ..tasks.engine import TaskHandle
from .executive import ExecutiveIntelligence
from .goal_engine import GoalEngine
from .mandate_engine import MandateEngine
from .observation import observe

logger = logging.getLogger(__name__)


@dataclass
class WorkerOutcome:
    task_id: str
    task_type: str
    outcome: str
    detail: str


class TaskWorker:
    """Claims and executes exactly one task type this pass wires up for
    real: execute_goal_step, produced by ExecutiveIntelligence.review_goal.
    An unrecognized task_type fails closed -- recorded as a failed task
    with a clear error -- rather than being silently dropped or assumed
    harmless; that's the same "never fabricate success" discipline the
    rest of this codebase already applies everywhere else."""

    def __init__(
        self, tasks: TaskEngine, broker: ActionBroker, goals: GoalEngine, memory: MemoryStore,
        world_model: WorldModelStore | None = None,
    ) -> None:
        self._tasks = tasks
        self._broker = broker
        self._goals = goals
        self._memory = memory
        self._world_model = world_model

    def run_once(self, worker_id: str = "operating-loop") -> WorkerOutcome | None:
        handle = self._tasks.claim_next(worker_id)
        if handle is None:
            return None
        if handle.task_type == "execute_goal_step":
            return self._run_execute_goal_step(handle)

        error = f"no worker logic registered for task_type '{handle.task_type}'"
        self._tasks.fail(handle.id, error)
        return WorkerOutcome(task_id=handle.id, task_type=handle.task_type, outcome="unknown_task_type", detail=error)

    def _run_execute_goal_step(self, handle: TaskHandle) -> WorkerOutcome:
        goal_id = handle.payload.get("goal_id")
        action_type = handle.payload.get("action_type")
        params = handle.payload.get("params") or {}
        summary = handle.payload.get("summary", "")

        if action_type is None:
            # The planner found no safe, registered action for this step.
            # That's a genuine, honest outcome -- not a failure -- so the
            # task completes and the workstream stays active for the
            # owner to act on the advisory by hand.
            self._tasks.complete(handle.id, {"outcome": "advisory", "summary": summary})
            return WorkerOutcome(handle.id, handle.task_type, "advisory", summary)

        try:
            outcome = self._broker.submit(ActionRequest(action_type=action_type, params=params))
        except Exception as exc:  # noqa: BLE001 -- a broken handler must never crash the loop itself
            self._tasks.fail(handle.id, str(exc))
            if goal_id:
                self._goals.mark_blocked(goal_id)
            return WorkerOutcome(handle.id, handle.task_type, "error", str(exc))

        if goal_id:
            self._memory.record_decision(
                goal=goal_id, statement=f"executed '{action_type}': {outcome.message}",
                reasoning=summary, source="operating_loop",
            )

        if outcome.status == OutcomeStatus.EXECUTED:
            self._tasks.complete(handle.id, {"outcome": "executed", "message": outcome.message})
            if goal_id:
                self._goals.mark_verifying(goal_id)
            if self._world_model is not None:
                observe(self._world_model, action_type, params, outcome.message, source=f"task:{handle.id}")
            return WorkerOutcome(handle.id, handle.task_type, "executed", outcome.message)

        if outcome.status == OutcomeStatus.PENDING_APPROVAL:
            self._tasks.complete(handle.id, {"outcome": "pending_approval", "message": outcome.message})
            if goal_id:
                self._goals.mark_waiting_approval(goal_id)
            return WorkerOutcome(handle.id, handle.task_type, "pending_approval", outcome.message)

        # DENIED / KILL_SWITCH_ENGAGED / RATE_LIMITED / NO_HANDLER: the
        # step genuinely could not proceed right now. Fail the task (so
        # its own retry/backoff applies) and mark the workstream blocked
        # rather than silently leaving it "active" with nothing moving.
        self._tasks.fail(handle.id, f"[{outcome.status.value}] {outcome.message}")
        if goal_id:
            self._goals.mark_blocked(goal_id)
        return WorkerOutcome(handle.id, handle.task_type, outcome.status.value.lower(), outcome.message)


class OperatingLoopSupervisor:
    """The actual restart-durable autonomous cycle. Deliberately opt-in
    -- never started by build_runtime() itself, exactly like Supervisor/
    `aura voice run` -- so every existing test that builds a Runtime
    doesn't unexpectedly acquire a background thread."""

    def __init__(
        self, executive: ExecutiveIntelligence, worker: TaskWorker,
        tasks: TaskEngine, mandates: MandateEngine, goals: GoalEngine,
        interval_seconds: float = 30.0, max_tasks_per_cycle: int = 50,
    ) -> None:
        self._executive = executive
        self._worker = worker
        self._tasks = tasks
        self._mandates = mandates
        self._goals = goals
        self.interval_seconds = interval_seconds
        self._max_tasks_per_cycle = max_tasks_per_cycle
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.cycles_run = 0

    async def run_cycle_once(self) -> list[WorkerOutcome]:
        """One full OBSERVE -> ... -> SCHEDULE pass. Safe to call
        directly (a test, or an API/CLI "run one cycle now") without
        starting the background thread."""
        self._tasks.reap_expired_leases()
        self._tasks.promote_ready_blocked_tasks()

        await self._executive.run_review_cycle()

        for mandate in self._mandates.due_for_observation():
            self._observe_mandate(mandate.id)

        outcomes: list[WorkerOutcome] = []
        for _ in range(self._max_tasks_per_cycle):
            outcome = self._worker.run_once()
            if outcome is None:
                break
            outcomes.append(outcome)

        self.cycles_run += 1
        return outcomes

    def _observe_mandate(self, mandate_id: str) -> None:
        workstreams = self._goals.list_for_mandate(mandate_id)
        active = sum(1 for g in workstreams if g.status == "active")
        blocked = [g.statement for g in workstreams if g.status in ("blocked", "failed")]
        waiting = [g.statement for g in workstreams if g.status in ("waiting_approval", "waiting_external")]
        summary = (
            f"{len(workstreams)} workstream(s): {active} active, "
            f"{len(blocked)} blocked/failed, {len(waiting)} waiting."
        )
        next_actions = [g.statement for g in workstreams if g.status in ("draft", "active")]
        self._mandates.record_observation(mandate_id, summary=summary, next_actions=next_actions)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                asyncio.run(self.run_cycle_once())
            except Exception:  # noqa: BLE001 -- one bad cycle must not kill the supervisor thread
                logger.exception("operating loop cycle failed")
            self._stop_event.wait(self.interval_seconds)

    def start_in_background(self) -> threading.Thread:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_seconds + 5)
