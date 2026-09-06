"""ExecutiveIntelligence: the planning half of the operating loop.

For each goal due for review, asks the Model Router for the single next
concrete step -- constrained to the Action Broker's actually-registered
action types, never freeform prose the system would then have no way to
execute. If the model can't identify a safe, executable step, the
outcome is an honest advisory (the workstream stays active, the owner
sees the recommendation) rather than a fabricated action. Either way the
reasoning is recorded as a Decision before anything is enqueued, and the
resulting task is picked up and actually executed by
`operating_loop.TaskWorker` -- see docs/FINAL_COMPLETION_AUDIT.md for why
that worker had to be added: nothing previously claimed these tasks at
all.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from ..governance.action_broker import ActionBroker
from ..memory import MemoryStore
from ..memory.models import Decision
from ..providers import ModelRouter, NoProviderAvailable
from ..tasks import TaskEngine
from .goal_engine import GoalEngine
from .goal_models import Goal


@dataclass
class Plan:
    """The result of constraining a model's free-text response to
    something the system can actually do something with. action_type is
    None whenever the model's output couldn't be parsed as a JSON object
    naming one of the broker's registered action types -- that's the
    safe, honest default, not an error state."""
    action_type: str | None
    params: dict = field(default_factory=dict)
    summary: str = ""


@dataclass
class ReviewOutcome:
    goal_id: str
    decision: Decision | None
    task_id: str | None
    action_type: str | None = None
    error: str | None = None


def _extract_json_object(raw: str) -> dict | None:
    """Models routinely wrap JSON in prose or markdown fences. Take the
    first {...} span found, rather than requiring the entire response to
    be bare JSON, but never guess at a shape beyond that -- an unparsable
    or non-dict result is treated as "no plan", never coerced into one."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_plan(raw: str, allowed_action_types: list[str]) -> Plan:
    """Pure and independently testable: given a model's raw text and the
    broker's currently-registered action types, decide whether a real,
    executable action was named. allowed_action_types is the ground
    truth -- a plan naming any other action_type is treated exactly like
    a plan that named none at all, since submitting it would only ever
    reach the Action Broker's NO_HANDLER path."""
    parsed = _extract_json_object(raw)
    if parsed is None:
        return Plan(action_type=None, summary=raw.strip()[:500] or "no plan could be parsed from the model's response")

    action_type = parsed.get("action_type")
    if isinstance(action_type, str) and action_type in allowed_action_types:
        params = parsed.get("params")
        reasoning = parsed.get("reasoning", "")
        return Plan(
            action_type=action_type,
            params=params if isinstance(params, dict) else {},
            summary=f"{action_type}: {reasoning}".strip(": "),
        )

    advisory = parsed.get("advisory")
    if isinstance(advisory, str) and advisory.strip():
        return Plan(action_type=None, summary=advisory.strip())

    return Plan(action_type=None, summary=raw.strip()[:500] or "no actionable or advisory plan was produced")


class ExecutiveIntelligence:
    def __init__(
        self, goals: GoalEngine, tasks: TaskEngine, memory: MemoryStore,
        model_router: ModelRouter, broker: ActionBroker | None = None,
    ) -> None:
        self._goals = goals
        self._tasks = tasks
        self._memory = memory
        self._model_router = model_router
        self._broker = broker

    async def review_goal(self, goal: Goal) -> ReviewOutcome:
        allowed = self._broker.registered_action_types() if self._broker is not None else []
        prompt = (
            "You are AURA's executive planner for a single workstream. "
            "You may ONLY propose one of these registered action types "
            f"(nothing else can actually be executed): {allowed or '(none registered)'}\n"
            f"Goal: {goal.statement}\n"
            f"Success metric: {goal.success_metric}\n"
            f"Current progress: {goal.progress:.0%}\n"
            "Respond with ONLY a JSON object, nothing else, in one of these two shapes:\n"
            '{"action_type": "<one of the allowed action types>", "params": {...}, "reasoning": "<why>"}\n'
            "or, if none of the allowed action types actually advance this goal right now:\n"
            '{"advisory": "<one-sentence recommendation for the owner>", "reasoning": "<why>"}'
        )
        try:
            chunks = [chunk async for chunk in self._model_router.generate_stream(prompt, history=[])]
        except NoProviderAvailable as exc:
            return ReviewOutcome(goal_id=goal.id, decision=None, task_id=None, error=str(exc))

        plan = parse_plan("".join(chunks), allowed)

        decision = self._memory.record_decision(
            goal=goal.id, statement=plan.summary,
            reasoning="generated by the Model Router during a scheduled goal review",
            source="executive",
        )
        task = self._tasks.enqueue("execute_goal_step", {
            "goal_id": goal.id, "action_type": plan.action_type,
            "params": plan.params, "summary": plan.summary,
        })
        self._goals.mark_reviewed(goal.id)
        return ReviewOutcome(goal_id=goal.id, decision=decision, task_id=task.id, action_type=plan.action_type)

    async def run_review_cycle(self) -> list[ReviewOutcome]:
        """Planning only -- enqueues one execute_goal_step task per goal
        due for review. Actually executing those tasks is
        operating_loop.TaskWorker's job, driven by
        operating_loop.OperatingLoopSupervisor on a schedule."""
        return [await self.review_goal(goal) for goal in self._goals.due_for_review()]
