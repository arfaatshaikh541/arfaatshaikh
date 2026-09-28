"""Long-running processes: scheduler (single leader) and workers (N replicas)."""
from __future__ import annotations

import datetime as dt
import logging
import signal
import time
import traceback

from sqlalchemy import func, select, text

from ..audit import record_error, system_event
from ..config import get_config
from ..db import get_engine, session_scope
from ..lifecycle import STOP, ShuttingDown
from ..models import (
    Application, ApplicationStatus as S, Job, JobSource, Report, Task, TaskStatus, WorkerHeartbeat, utcnow,
)
from ..ratelimit import backoff_delay
from ..settings_store import AutomationSettings, load
from . import queue
from .tasks import Defer, Retryable, apply_gate, handle_discover, handle_evaluate, local_now

log = logging.getLogger(__name__)
LEADER_LOCK_ID = 0x4A4F4241  # "JOBA"


def heartbeat(worker_id: str, kind: str, current_task: int | None = None, info: dict | None = None) -> None:
    with session_scope() as s:
        hb = s.get(WorkerHeartbeat, worker_id, with_for_update=True)
        if hb is None:
            hb = WorkerHeartbeat(worker_id=worker_id, kind=kind, started_at=utcnow())
            s.add(hb)
        hb.last_seen = utcnow()
        hb.current_task_id = current_task
        hb.info = info or {}


class _Stop:
    @property
    def flag(self) -> bool:
        return STOP.is_set()


_Stop = _Stop()


def _install_signals() -> None:
    def h(*_):
        STOP.set()

    signal.signal(signal.SIGTERM, h)
    signal.signal(signal.SIGINT, h)


# ------------------------------------------------------------------ scheduler


def scheduler_tick(worker_id: str) -> dict:
    """One scheduling pass. Pure DB work; safe to call repeatedly."""
    out = {"discover": 0, "evaluate": 0, "apply": 0, "report": 0, "reclaimed": 0}
    with session_scope() as s:
        out["reclaimed"] = queue.reclaim_expired(s)
    with session_scope() as s:
        auto = load(s, AutomationSettings)
        now = utcnow()
        if auto.state == "RUNNING":
            interval = dt.timedelta(minutes=auto.search_interval_minutes)
            bucket = int(now.timestamp() // interval.total_seconds())
            for src in s.scalars(select(JobSource).where(JobSource.enabled.is_(True))):
                if src.last_run_at is None or now - src.last_run_at >= interval:
                    if queue.enqueue(s, "discover", {"source_id": src.id}, dedupe_key=f"discover:{src.id}:{bucket}",
                                     priority=80, max_attempts=4):
                        out["discover"] += 1
            # Jobs discovered but never evaluated (e.g. profile added later)
            for jid in s.scalars(select(Job.id).where(Job.status == "DISCOVERED").limit(200)):
                if queue.enqueue(s, "evaluate", {"job_id": jid}, dedupe_key=f"evaluate:{jid}", priority=50):
                    out["evaluate"] += 1
            # One application at a time, oldest first, current mode only, within configured limits.
            busy = s.scalar(select(func.count(Task.id)).where(
                Task.type == "apply", Task.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value])))
            if not busy:
                nxt = s.scalars(select(Application).join(Job).where(
                    Application.status == S.QUEUED.value, Application.mode == auto.mode)
                    .order_by(Application.queued_at, Application.id).limit(1)).first()
                if nxt is not None:
                    ok, _, why = apply_gate(s, auto, nxt.job.platform)
                    if ok and queue.enqueue(s, "apply", {"application_id": nxt.id},
                                            dedupe_key=f"apply:{nxt.id}:{nxt.retry_count}", priority=10,
                                            max_attempts=1):
                        out["apply"] += 1
                    out["apply_gate"] = why
        # Daily report is generated whatever the automation state.
        local = local_now(auto.timezone)
        hh, mm = map(int, auto.daily_report_time.split(":"))
        if (local.hour, local.minute) >= (hh, mm):
            exists = s.scalar(select(Report.id).where(Report.report_date == local.date(), Report.trigger == "scheduled"))
            if not exists and queue.enqueue(s, "daily_report", {"date": local.date().isoformat()},
                                            dedupe_key=f"report:{local.date().isoformat()}", priority=5):
                out["report"] += 1
    return out


def run_scheduler(poll_s: float = 20.0) -> None:
    cfg = get_config()
    wid = f"scheduler-{cfg.worker_id}"
    _install_signals()
    conn = get_engine().connect()
    while not _Stop.flag:
        got = conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": LEADER_LOCK_ID}).scalar()
        conn.commit()
        if got:
            break
        log.info("another scheduler is leader; standing by", extra={"worker_id": wid, "event": "standby"})
        STOP.wait(poll_s)
    with session_scope() as s:
        system_event(s, "scheduler", "started", wid)
    try:
        while not _Stop.flag:
            t0 = time.monotonic()
            try:
                res = scheduler_tick(wid)
                heartbeat(wid, "scheduler", info=res)
                if any(res.get(k) for k in ("discover", "apply", "report", "reclaimed")):
                    log.info("scheduler tick", extra={"worker_id": wid, "event": "tick", "result": res})
            except Exception as e:
                log.exception("scheduler tick failed", extra={"worker_id": wid})
                try:
                    with session_scope() as s:
                        record_error(s, "scheduler", e, worker_id=wid)
                except Exception:
                    pass
            STOP.wait(max(1.0, poll_s - (time.monotonic() - t0)))
    finally:
        with session_scope() as s:
            system_event(s, "scheduler", "stopped", wid)
        conn.close()


# ------------------------------------------------------------------ worker


class Worker:
    def __init__(self, types: list[str] | None = None):
        cfg = get_config()
        self.cfg = cfg
        self.worker_id = f"worker-{cfg.worker_id}"
        self.types = types
        self._browsers = None
        self._runner = None

    def runner(self):
        if self._runner is None:
            from ..browser.engine import BrowserManager
            from .apply import ApplicationRunner

            self._browsers = BrowserManager()
            self._runner = ApplicationRunner(self._browsers, self.worker_id)
        return self._runner

    def browser_health(self) -> dict:
        if self._browsers is None:
            return {"browser": "NOT STARTED (starts on first application)"}
        return {"browser": "OK" if self._browsers._browser and self._browsers._browser.is_connected() else "DOWN",
                "browser_launches": self._browsers.launches}

    def handle(self, t: Task) -> dict:
        if t.type == "discover":
            return handle_discover(t.payload, self.worker_id)
        if t.type == "evaluate":
            return handle_evaluate(t.payload, self.worker_id)
        if t.type == "daily_report":
            from ..reports import generate

            with session_scope() as s:
                r = generate(s, dt.date.fromisoformat(t.payload["date"]), trigger=t.payload.get("trigger", "scheduled"))
                return {"report_id": r.id}
        if t.type == "login_test":
            from ..browser.login import run_login_test

            self.runner()  # ensures the browser manager exists
            with session_scope() as s:
                r = run_login_test(s, t.payload["user_id"], t.payload["platform_key"], self._browsers)
                return {"status": r.status, "reason": r.reason}
        if t.type == "ai_health":
            from ..ai.providers import ProviderHandle

            with session_scope() as s:
                ok, msg = ProviderHandle(s, t.payload["user_id"]).health_check()
                return {"ok": ok, "message": msg}
        if t.type == "apply":
            app_id = t.payload["application_id"]
            with session_scope() as s:
                auto = load(s, AutomationSettings)
                app = s.get(Application, app_id)
                if app is None or app.status != S.QUEUED.value:
                    return {"skipped": f"application status {app.status if app else 'missing'}"}
                if app.mode != auto.mode:
                    return {"skipped": f"application mode {app.mode} != current mode {auto.mode}"}
                ok, wait, why = apply_gate(s, auto, app.job.platform)
                # the gate's gap check counts this app's own previous attempt; that's intended
            if not ok:
                raise Defer(wait, why)
            res = self.runner().run(app_id)
            return {"status": res.status, "reason": res.reason}
        raise ValueError(f"Unknown task type {t.type}")

    def run_once(self) -> bool:
        with session_scope() as s:
            t = queue.claim(s, self.worker_id, self.cfg.task_lease_seconds, self.types)
            if t is None:
                return False
            tid, ttype, payload, attempts = t.id, t.type, dict(t.payload), t.attempts
        heartbeat(self.worker_id, "worker", tid, self.browser_health())
        t0 = time.monotonic()
        try:
            snap = Task(id=tid, type=ttype, payload=payload, attempts=attempts)
            result = self.handle(snap)
            with session_scope() as s:
                queue.complete(s, s.get(Task, tid), result)
            log.info("task done", extra={"worker_id": self.worker_id, "task_id": tid, "event": ttype,
                                         "duration_ms": int((time.monotonic() - t0) * 1000), "result": result})
        except Defer as d:
            with session_scope() as s:
                queue.defer(s, s.get(Task, tid), d.seconds, d.why)
        except ShuttingDown:
            # Only reachable from interruptible waits (discovery/backoff), never mid-submission.
            with session_scope() as s:
                queue.defer(s, s.get(Task, tid), 5, "worker shutting down")
        except Exception as e:
            retry = backoff_delay(attempts, 60) if isinstance(e, Retryable) else None
            with session_scope() as s:
                queue.fail(s, s.get(Task, tid), f"{type(e).__name__}: {e}\n{traceback.format_exc()[-2000:]}", retry)
                if not isinstance(e, Retryable):
                    record_error(s, f"task:{ttype}", e, worker_id=self.worker_id, task_id=tid)
            log.warning("task failed", extra={"worker_id": self.worker_id, "task_id": tid, "event": ttype,
                                              "error": f"{type(e).__name__}: {e}"})
        finally:
            heartbeat(self.worker_id, "worker", None, self.browser_health())
        return True

    def run_forever(self, idle_s: float = 5.0) -> None:
        _install_signals()
        with session_scope() as s:
            system_event(s, "worker", "started", self.worker_id)
        try:
            while not _Stop.flag:
                try:
                    worked = self.run_once()
                except Exception:
                    log.exception("worker loop error", extra={"worker_id": self.worker_id})
                    worked = False
                    STOP.wait(10)
                if not worked:
                    heartbeat(self.worker_id, "worker", None, self.browser_health())
                    STOP.wait(idle_s)
        finally:
            if self._browsers is not None:
                self._browsers.close()
            with session_scope() as s:
                system_event(s, "worker", "stopped", self.worker_id)
