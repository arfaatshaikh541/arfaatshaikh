"""PostgreSQL task queue (FOR UPDATE SKIP LOCKED, leases, dedupe keys)."""
from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models import Application, ApplicationStatus as S, Task, TaskStatus, utcnow
from ..state import transition


def enqueue(s: Session, type_: str, payload: dict[str, Any], *, dedupe_key: str | None = None,
            run_after: dt.datetime | None = None, priority: int = 100, max_attempts: int = 5) -> int | None:
    """Insert a task; returns its id, or None if a task with this dedupe key already exists."""
    stmt = insert(Task).values(
        type=type_, payload=payload, dedupe_key=dedupe_key, run_after=run_after or utcnow(), priority=priority,
        max_attempts=max_attempts, status=TaskStatus.PENDING.value, attempts=0, created_at=utcnow(), result={},
    ).on_conflict_do_nothing(index_elements=["dedupe_key"]).returning(Task.id)
    return s.execute(stmt).scalar()


def claim(s: Session, worker_id: str, lease_s: int, types: list[str] | None = None) -> Task | None:
    now = utcnow()
    q = (select(Task.id).where(Task.status == TaskStatus.PENDING.value, Task.run_after <= now)
         .order_by(Task.priority, Task.id).limit(1).with_for_update(skip_locked=True))
    if types:
        q = q.where(Task.type.in_(types))
    tid = s.scalar(q)
    if tid is None:
        return None
    t = s.get(Task, tid)
    t.status = TaskStatus.RUNNING.value
    t.locked_by = worker_id
    t.locked_until = now + dt.timedelta(seconds=lease_s)
    t.attempts += 1
    s.flush()
    return t


def complete(s: Session, t: Task, result: dict[str, Any] | None = None) -> None:
    t.status = TaskStatus.DONE.value
    t.finished_at = utcnow()
    t.result = result or {}
    t.locked_until = None


def fail(s: Session, t: Task, error: str, retry_in_s: float | None) -> None:
    t.last_error = error[:4000]
    t.locked_until = None
    if retry_in_s is not None and t.attempts < t.max_attempts:
        t.status = TaskStatus.PENDING.value
        t.run_after = utcnow() + dt.timedelta(seconds=retry_in_s)
    else:
        t.status = TaskStatus.FAILED.value
        t.finished_at = utcnow()


def defer(s: Session, t: Task, seconds: float, why: str) -> None:
    """Put a task back without consuming an attempt (e.g. outside allowed hours)."""
    t.status = TaskStatus.PENDING.value
    t.attempts = max(0, t.attempts - 1)
    t.run_after = utcnow() + dt.timedelta(seconds=seconds)
    t.locked_until = None
    t.last_error = f"deferred: {why}"


def reclaim_expired(s: Session) -> int:
    """Recover tasks whose worker died. Apply tasks past SUBMITTING become UNKNOWN, never retried."""
    n = 0
    for t in s.scalars(select(Task).where(Task.status == TaskStatus.RUNNING.value, Task.locked_until < utcnow())
                       .with_for_update(skip_locked=True)):
        n += 1
        if t.type == "apply":
            app = s.get(Application, t.payload.get("application_id"), with_for_update=True)
            if app is not None:
                st = S(app.status)
                if st == S.SUBMITTING:
                    transition(s, app, S.UNKNOWN, worker_id="scheduler",
                               reason=f"Worker {t.locked_by} lost during submission; status uncertain")
                    fail(s, t, "worker lost during submission", None)
                    continue
                if st in {S.STARTED, S.FORM_COMPLETED}:
                    transition(s, app, S.QUEUED, worker_id="scheduler",
                               reason=f"Worker {t.locked_by} lost before submit; re-queued")
            fail(s, t, f"lease expired (worker {t.locked_by})", None)
            continue
        fail(s, t, f"lease expired (worker {t.locked_by})", 30)
    return n


def cancel_pending(s: Session, types: list[str]) -> int:
    r = s.execute(update(Task).where(Task.status == TaskStatus.PENDING.value, Task.type.in_(types))
                  .values(status=TaskStatus.CANCELLED.value, finished_at=utcnow()))
    return r.rowcount or 0


def active_count(s: Session, type_: str) -> int:
    from sqlalchemy import func

    return s.scalar(select(func.count(Task.id)).where(
        Task.type == type_, or_(Task.status == TaskStatus.RUNNING.value,
                                and_(Task.status == TaskStatus.PENDING.value)))) or 0
