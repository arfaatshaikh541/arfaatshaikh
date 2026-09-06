"""GoalEngine: CRUD plus the activation gate that enforces
docs/architecture/03-goal-engine.md's hard requirement — a goal cannot
become 'active' without a success metric, a budget, and at least one
stop condition populated.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ..memory.models import Base
from .goal_models import Goal


class GoalNotReadyError(RuntimeError):
    pass


class GoalEngine:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    def create(
        self, statement: str, *, priority: int = 3, deadline: datetime | None = None,
        success_metric: str | None = None, budget: dict | None = None,
        stop_conditions: list[str] | None = None, constraints: list[str] | None = None,
        allowed_actions: list[str] | None = None, prohibited_actions: list[str] | None = None,
        review_interval_seconds: int = 86400,
    ) -> Goal:
        with self._Session() as session:
            goal = Goal(
                statement=statement, priority=priority, deadline=deadline,
                success_metric=success_metric,
                budget_json=json.dumps(budget) if budget is not None else None,
                stop_conditions_json=json.dumps(stop_conditions or []),
                constraints_json=json.dumps(constraints or []),
                allowed_actions_json=json.dumps(allowed_actions or []),
                prohibited_actions_json=json.dumps(prohibited_actions or []),
                review_interval_seconds=review_interval_seconds,
                status="draft",
            )
            session.add(goal)
            session.commit()
            session.refresh(goal)
            return goal

    def get(self, goal_id: str) -> Goal | None:
        with self._Session() as session:
            return session.get(Goal, goal_id)

    def activate(self, goal_id: str) -> Goal:
        """Raises GoalNotReadyError, rather than silently activating,
        when success_metric/budget/stop_conditions are missing — this is
        the enforcement point for docs/architecture/03-goal-engine.md's
        hard requirement."""
        with self._Session() as session:
            goal = session.get(Goal, goal_id)
            if goal is None:
                raise GoalNotReadyError(f"no such goal '{goal_id}'")

            missing = []
            if not goal.success_metric:
                missing.append("success_metric")
            if not goal.budget_json:
                missing.append("budget")
            if json.loads(goal.stop_conditions_json) == []:
                missing.append("stop_conditions")
            if missing:
                raise GoalNotReadyError(f"goal '{goal_id}' missing required fields: {', '.join(missing)}")

            goal.status = "active"
            session.commit()
            session.refresh(goal)
            return goal

    def pause(self, goal_id: str) -> None:
        self._set_status(goal_id, "paused")

    def abandon(self, goal_id: str) -> None:
        self._set_status(goal_id, "abandoned")

    def complete(self, goal_id: str) -> None:
        self._set_status(goal_id, "completed")

    def mark_waiting_approval(self, goal_id: str) -> None:
        self._set_status(goal_id, "waiting_approval")

    def mark_waiting_external(self, goal_id: str) -> None:
        self._set_status(goal_id, "waiting_external")

    def mark_blocked(self, goal_id: str) -> None:
        self._set_status(goal_id, "blocked")

    def mark_verifying(self, goal_id: str) -> None:
        self._set_status(goal_id, "verifying")

    def mark_failed(self, goal_id: str) -> None:
        self._set_status(goal_id, "failed")

    def mark_suspended(self, goal_id: str) -> None:
        self._set_status(goal_id, "suspended")

    def reactivate(self, goal_id: str) -> None:
        """Return a workstream to 'active' once whatever it was waiting
        on (approval, an external reply, a blocker) is resolved."""
        self._set_status(goal_id, "active")

    def set_mandate(self, goal_id: str, mandate_id: str) -> None:
        with self._Session() as session:
            goal = session.get(Goal, goal_id)
            if goal is None:
                raise GoalNotReadyError(f"no such goal '{goal_id}'")
            goal.mandate_id = mandate_id
            session.commit()

    def list_for_mandate(self, mandate_id: str) -> list[Goal]:
        with self._Session() as session:
            stmt = select(Goal).where(Goal.mandate_id == mandate_id).order_by(Goal.priority)
            return list(session.scalars(stmt))

    def _set_status(self, goal_id: str, status: str) -> None:
        with self._Session() as session:
            goal = session.get(Goal, goal_id)
            if goal is None:
                raise GoalNotReadyError(f"no such goal '{goal_id}'")
            goal.status = status
            session.commit()

    def update_progress(self, goal_id: str, progress: float, confidence: float | None = None) -> None:
        with self._Session() as session:
            goal = session.get(Goal, goal_id)
            if goal is None:
                raise GoalNotReadyError(f"no such goal '{goal_id}'")
            goal.progress = max(0.0, min(1.0, progress))
            if confidence is not None:
                goal.confidence = confidence
            session.commit()

    def mark_reviewed(self, goal_id: str) -> None:
        with self._Session() as session:
            goal = session.get(Goal, goal_id)
            if goal is None:
                raise GoalNotReadyError(f"no such goal '{goal_id}'")
            goal.last_reviewed_at = datetime.now(timezone.utc)
            session.commit()

    def list_active(self) -> list[Goal]:
        with self._Session() as session:
            stmt = select(Goal).where(Goal.status == "active").order_by(Goal.priority)
            return list(session.scalars(stmt))

    def due_for_review(self) -> list[Goal]:
        """Active goals whose review_interval has elapsed since
        last_reviewed_at (or since creation, if never reviewed)."""
        due = []
        for goal in self.list_active():
            last = goal.last_reviewed_at or goal.created_at
            last_aware = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= last_aware + timedelta(seconds=goal.review_interval_seconds):
                due.append(goal)
        return due
