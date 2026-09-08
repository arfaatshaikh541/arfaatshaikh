"""MandateEngine: CRUD plus the activation gate (mirrors GoalEngine's
own gate exactly, for the same reason) and the executive-grade status
report from section 22 of the product spec -- "what's the update on
Gridkeep" must be built from real workstream/decision state, not
answered from vague chat memory.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ..memory.schema_migration import ensure_schema
from ..memory.store import MemoryStore
from .directives import STANDARD_DEPARTMENTS, parse_run_directive
from .goal_engine import GoalEngine
from .goal_models import Goal
from .mandate_models import Mandate


class UnrecognizedDirectiveError(RuntimeError):
    pass

# Maps a workstream's (Goal's) raw status onto the report vocabulary
# section 22 explicitly requires. "abandoned" has no listed bucket of its
# own -- it's folded into FAILED for the summary count, but the workstream
# detail line always carries its real status string too, so nothing is
# actually hidden.
_REPORT_BUCKET = {
    "completed": "DONE",
    "active": "IN_PROGRESS",
    "verifying": "IN_PROGRESS",
    "waiting_approval": "WAITING_ON_OWNER",
    "waiting_external": "WAITING_ON_EXTERNAL",
    "blocked": "FAILED",
    "failed": "FAILED",
    "abandoned": "FAILED",
    "draft": "PLANNED",
    "paused": "PLANNED",
    "suspended": "PLANNED",
}


class MandateNotReadyError(RuntimeError):
    pass


@dataclass
class WorkstreamSummary:
    goal_id: str
    statement: str
    status: str
    bucket: str
    progress: float
    latest_decision: str | None


@dataclass
class MandateReport:
    mandate_id: str
    title: str
    status: str
    generated_at: datetime
    counts: dict[str, int] = field(default_factory=dict)  # bucket -> count
    workstreams: list[WorkstreamSummary] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


class MandateEngine:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        ensure_schema(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    def create(
        self, title: str, mission: str, *, priority: int = 3,
        authority: str = "advisory_only", risk_ceiling: str = "GREEN", policy_profile: str | None = None,
        objectives: list[str] | None = None, kpis: list[dict] | None = None,
        constraints: list[str] | None = None, observation_interval_seconds: int = 3600,
    ) -> Mandate:
        with self._Session() as session:
            mandate = Mandate(
                title=title, mission=mission, priority=priority,
                authority=authority, risk_ceiling=risk_ceiling, policy_profile=policy_profile,
                objectives_json=json.dumps(objectives or []),
                kpis_json=json.dumps(kpis or []),
                constraints_json=json.dumps(constraints or []),
                observation_interval_seconds=observation_interval_seconds,
                status="draft",
            )
            session.add(mandate)
            session.commit()
            session.refresh(mandate)
            return mandate

    def create_from_directive(self, text: str) -> Mandate:
        """"Run Gridkeep" -> a draft mandate scaffolded with the standard
        operating departments, without asking for a generic goal-form
        first (section 10). Deliberately still leaves kpis/constraints
        empty: those are real facts about a real business this system
        knows nothing about, and activate() will honestly keep refusing
        to activate until the owner supplies them -- this only removes
        the friction of an intake form for the initial command, it does
        not fabricate the business content that form would have
        collected."""
        company = parse_run_directive(text)
        if company is None:
            raise UnrecognizedDirectiveError(
                f"'{text}' is not a recognized directive (expected \"Run <company>\" or \"Operate <company>\")"
            )
        return self.create(
            title=f"Run {company}",
            mission=f"Operate and grow {company}",
            objectives=[f"Stand up the {department} department" for department in STANDARD_DEPARTMENTS],
        )

    def get(self, mandate_id: str) -> Mandate | None:
        with self._Session() as session:
            return session.get(Mandate, mandate_id)

    def activate(self, mandate_id: str) -> Mandate:
        """Raises MandateNotReadyError rather than silently activating
        when objectives/KPIs/constraints are missing -- an autonomous
        directive with no stated objective, no way to measure it, and no
        constraint on how it may pursue it is exactly the "impressive
        autonomy demo, ungoverned in practice" failure mode this whole
        system exists to prevent."""
        with self._Session() as session:
            mandate = session.get(Mandate, mandate_id)
            if mandate is None:
                raise MandateNotReadyError(f"no such mandate '{mandate_id}'")

            missing = []
            if json.loads(mandate.objectives_json) == []:
                missing.append("objectives")
            if json.loads(mandate.kpis_json) == []:
                missing.append("kpis")
            if json.loads(mandate.constraints_json) == []:
                missing.append("constraints")
            if missing:
                raise MandateNotReadyError(f"mandate '{mandate_id}' missing required fields: {', '.join(missing)}")

            mandate.status = "active"
            session.commit()
            session.refresh(mandate)
            return mandate

    def pause(self, mandate_id: str) -> None:
        self._set_status(mandate_id, "paused")

    def cancel(self, mandate_id: str) -> None:
        self._set_status(mandate_id, "cancelled")

    def complete(self, mandate_id: str) -> None:
        self._set_status(mandate_id, "completed")

    def _set_status(self, mandate_id: str, status: str) -> None:
        with self._Session() as session:
            mandate = session.get(Mandate, mandate_id)
            if mandate is None:
                raise MandateNotReadyError(f"no such mandate '{mandate_id}'")
            mandate.status = status
            session.commit()

    def list_active(self) -> list[Mandate]:
        with self._Session() as session:
            stmt = select(Mandate).where(Mandate.status == "active").order_by(Mandate.priority)
            return list(session.scalars(stmt))

    def due_for_observation(self) -> list[Mandate]:
        due = []
        for mandate in self.list_active():
            last = mandate.last_observed_at
            last_aware = last if (last is None or last.tzinfo) else last.replace(tzinfo=timezone.utc)
            deadline = (last_aware or mandate.created_at)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= deadline + timedelta(seconds=mandate.observation_interval_seconds):
                due.append(mandate)
        return due

    def record_observation(self, mandate_id: str, *, summary: str, next_actions: list[str]) -> None:
        with self._Session() as session:
            mandate = session.get(Mandate, mandate_id)
            if mandate is None:
                raise MandateNotReadyError(f"no such mandate '{mandate_id}'")
            mandate.last_observed_at = datetime.now(timezone.utc)
            mandate.latest_summary = summary
            mandate.next_actions_json = json.dumps(next_actions)
            session.commit()

    def report(self, mandate_id: str, goal_engine: GoalEngine, memory: MemoryStore) -> MandateReport:
        """Builds the executive-grade status answer from real state --
        every workstream's current status and most recent recorded
        Decision -- not from any cached narrative alone."""
        mandate = self.get(mandate_id)
        if mandate is None:
            raise MandateNotReadyError(f"no such mandate '{mandate_id}'")

        workstreams = []
        counts: dict[str, int] = {}
        blockers: list[str] = []
        for goal in goal_engine.list_for_mandate(mandate_id):
            bucket = _REPORT_BUCKET.get(goal.status, "PLANNED")
            counts[bucket] = counts.get(bucket, 0) + 1
            decisions = memory.decisions_for_goal(goal.id)
            latest = decisions[-1].statement if decisions else None
            workstreams.append(WorkstreamSummary(
                goal_id=goal.id, statement=goal.statement, status=goal.status,
                bucket=bucket, progress=goal.progress, latest_decision=latest,
            ))
            if bucket == "FAILED":
                blockers.append(f"{goal.statement} ({goal.status})")

        return MandateReport(
            mandate_id=mandate.id, title=mandate.title, status=mandate.status,
            generated_at=datetime.now(timezone.utc), counts=counts, workstreams=workstreams,
            next_actions=json.loads(mandate.next_actions_json), blockers=blockers,
        )
