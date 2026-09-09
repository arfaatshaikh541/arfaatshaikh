"""TaskEngine: durable task queue with leases, retries, dependencies, and
schedules — the primitives docs/architecture/08-long-running-autonomy.md
requires, implemented natively over SQLite rather than a workflow engine
like Temporal (see docs/adr/0005-native-task-engine-not-temporal.md).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ..memory.schema_migration import ensure_schema
from .models import TaskRecord


class TaskNotFound(RuntimeError):
    pass


@dataclass
class TaskHandle:
    id: str
    task_type: str
    payload: dict
    attempts: int
    max_attempts: int


class TaskEngine:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        ensure_schema(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    # -- Enqueue / lifecycle -------------------------------------------------
    def enqueue(
        self, task_type: str, payload: dict, *, run_at: datetime | None = None,
        depends_on: list[str] | None = None, max_attempts: int = 3,
    ) -> TaskRecord:
        depends_on = depends_on or []
        with self._Session() as session:
            status = "BLOCKED" if depends_on else "QUEUED"
            task = TaskRecord(
                task_type=task_type,
                payload_json=json.dumps(payload),
                status=status,
                run_at=run_at or datetime.now(timezone.utc),
                depends_on_json=json.dumps(depends_on),
                max_attempts=max_attempts,
            )
            session.add(task)
            session.commit()
            session.refresh(task)
            return task

    def get(self, task_id: str) -> TaskRecord | None:
        with self._Session() as session:
            return session.get(TaskRecord, task_id)

    def list_by_status(self, status: str) -> list[TaskRecord]:
        with self._Session() as session:
            stmt = select(TaskRecord).where(TaskRecord.status == status).order_by(TaskRecord.created_at)
            return list(session.scalars(stmt))

    def _dependencies_satisfied(self, session, task: TaskRecord) -> bool:
        dep_ids = json.loads(task.depends_on_json)
        if not dep_ids:
            return True
        for dep_id in dep_ids:
            dep = session.get(TaskRecord, dep_id)
            if dep is None or dep.status != "COMPLETED":
                return False
        return True

    def promote_ready_blocked_tasks(self) -> int:
        """BLOCKED -> QUEUED once every dependency has COMPLETED. Call this
        periodically (or after any task completes) rather than relying on
        claim_next() alone, so dependents don't need to be polled forever."""
        promoted = 0
        with self._Session() as session:
            for task in session.scalars(select(TaskRecord).where(TaskRecord.status == "BLOCKED")):
                if self._dependencies_satisfied(session, task):
                    task.status = "QUEUED"
                    task.updated_at = datetime.now(timezone.utc)
                    promoted += 1
            session.commit()
        return promoted

    def claim_next(self, worker_id: str, lease_seconds: int = 60) -> TaskHandle | None:
        """Atomically claims the oldest ready QUEUED/RETRYING task whose
        run_at has passed. Returns None if nothing is ready."""
        now = datetime.now(timezone.utc)
        with self._Session() as session:
            stmt = (
                select(TaskRecord)
                .where(TaskRecord.status.in_(["QUEUED", "RETRYING"]))
                .where(TaskRecord.run_at <= now)
                .order_by(TaskRecord.run_at)
            )
            for task in session.scalars(stmt):
                if not self._dependencies_satisfied(session, task):
                    task.status = "BLOCKED"
                    continue
                task.status = "RUNNING"
                task.lease_owner = worker_id
                task.lease_expires_at = now + timedelta(seconds=lease_seconds)
                task.attempts += 1
                task.updated_at = now
                session.commit()
                return TaskHandle(
                    id=task.id, task_type=task.task_type,
                    payload=json.loads(task.payload_json),
                    attempts=task.attempts, max_attempts=task.max_attempts,
                )
            session.commit()  # persist any BLOCKED demotions found above
            return None

    def complete(self, task_id: str, result: dict | None = None) -> None:
        with self._Session() as session:
            task = self._require(session, task_id)
            task.status = "COMPLETED"
            task.result_json = json.dumps(result or {})
            task.lease_owner = None
            task.lease_expires_at = None
            task.updated_at = datetime.now(timezone.utc)
            session.commit()

    def fail(self, task_id: str, error: str, *, backoff_seconds: int = 30) -> str:
        """Returns the resulting status ('RETRYING' or 'FAILED')."""
        with self._Session() as session:
            task = self._require(session, task_id)
            task.error = error
            task.lease_owner = None
            task.lease_expires_at = None
            task.updated_at = datetime.now(timezone.utc)
            if task.attempts < task.max_attempts:
                task.status = "RETRYING"
                task.run_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds * task.attempts)
            else:
                task.status = "FAILED"
            session.commit()
            return task.status

    def cancel(self, task_id: str) -> None:
        with self._Session() as session:
            task = self._require(session, task_id)
            task.status = "CANCELLED"
            task.lease_owner = None
            task.lease_expires_at = None
            task.updated_at = datetime.now(timezone.utc)
            session.commit()

    def mark_needs_approval(self, task_id: str, approval_id: str) -> None:
        with self._Session() as session:
            task = self._require(session, task_id)
            task.status = "NEEDS_APPROVAL"
            task.approval_id = approval_id
            task.lease_owner = None
            task.lease_expires_at = None
            task.updated_at = datetime.now(timezone.utc)
            session.commit()

    def resume_from_approval(self, task_id: str) -> None:
        with self._Session() as session:
            task = self._require(session, task_id)
            task.status = "QUEUED"
            task.updated_at = datetime.now(timezone.utc)
            session.commit()

    def reap_expired_leases(self) -> int:
        """A worker died mid-task without completing/failing it. Its
        lease expires and the task becomes claimable again — this is what
        makes crash recovery real rather than aspirational."""
        now = datetime.now(timezone.utc)
        reaped = 0
        with self._Session() as session:
            stmt = select(TaskRecord).where(
                TaskRecord.status == "RUNNING", TaskRecord.lease_expires_at < now,
            )
            for task in session.scalars(stmt):
                task.status = "QUEUED" if task.attempts < task.max_attempts else "FAILED"
                if task.status == "FAILED":
                    task.error = "lease expired and max_attempts exhausted"
                task.lease_owner = None
                task.lease_expires_at = None
                task.updated_at = now
                reaped += 1
            session.commit()
        return reaped

    def _require(self, session, task_id: str) -> TaskRecord:
        task = session.get(TaskRecord, task_id)
        if task is None:
            raise TaskNotFound(task_id)
        return task
