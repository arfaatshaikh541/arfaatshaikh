"""Failure recovery with real processes: a worker is SIGKILLed right after the submit click, and a
Chromium process is SIGKILLed mid-application. Neither may ever produce a false SUBMITTED or a
duplicate submission."""
import datetime as dt
import os
import subprocess
import sys
import time

import pytest
from sqlalchemy import select

from test_browser_apply import _Handler, _reload, _setup, server  # noqa: F401

from autopilot.db import session_scope
from autopilot.models import Task, WorkerHeartbeat, utcnow
from autopilot.settings_store import AutomationSettings, load, save
from autopilot.state import IllegalTransition, transition
from autopilot.models import ApplicationStatus as S
from autopilot.workers import queue


def _live_running():
    with session_scope() as s:
        a = load(s, AutomationSettings)
        a.state, a.mode, a.allowed_hours_start, a.allowed_hours_end = "RUNNING", "LIVE", 0, 24
        save(s, a)


def test_worker_killed_after_submit_click_is_reconciled_never_resubmitted(s, profile, server):
    _Handler.log.clear()
    _live_running()
    app_id = _setup(s, profile, f"{server}/slow_confirm_form.html")
    with session_scope() as ss:
        queue.enqueue(ss, "apply", {"application_id": app_id}, dedupe_key=f"apply:{app_id}:0", max_attempts=1)
    env = {**os.environ, "JOBAP_TASK_LEASE_SECONDS": "5", "JOBAP_WORKER_ID": "crash-victim"}
    proc = subprocess.Popen([sys.executable, "-m", "autopilot.cli", "worker"], env=env,
                            stdout=open(os.environ.get("JOBAP_TEST_ARTIFACTS", "/tmp") + "/crash-worker.log", "w"), stderr=subprocess.STDOUT)
    try:
        t0 = time.time()
        while time.time() - t0 < 120:
            s.expire_all()
            if _reload(s, app_id).submit_clicked_at and [p for p in _Handler.log if p.startswith("/submit-log")]:
                break
            time.sleep(0.2)
        else:
            pytest.fail(f"worker never clicked submit: {_reload(s, app_id).status} {_reload(s, app_id).status_reason}")
        proc.kill()  # SIGKILL: no cleanup, no final DB writes - like a crashed container
        proc.wait(10)
    finally:
        if proc.poll() is None:
            proc.kill()
    app = _reload(s, app_id)
    assert app.status == "SUBMITTING"  # uncertain: the click happened, the outcome was never seen
    time.sleep(6)  # lease expires because the dead worker can no longer renew it
    from autopilot.workers.runtime import scheduler_tick

    scheduler_tick("test-scheduler")
    app = _reload(s, app_id)
    assert app.status == "UNKNOWN", app.status_reason
    assert "lost during submission" in app.status_reason
    s.expire_all()
    assert s.scalar(select(Task.status).where(Task.dedupe_key == f"apply:{app_id}:0")) == "FAILED"
    # A second pass never re-dispatches it, and it cannot be re-queued without human reconciliation.
    assert scheduler_tick("test-scheduler")["apply"] == 0
    with pytest.raises(IllegalTransition):
        transition(s, app, S.FAILED)  # allowed...
        transition(s, app, S.QUEUED)  # ...but re-queue is refused: submit was clicked
    s.rollback()
    time.sleep(1)
    assert len([p for p in _Handler.log if p.startswith("/submit-log")]) == 1  # exactly one real submission


def test_browser_process_killed_mid_application_recovers(s, profile, server, monkeypatch):
    import autopilot.workers.apply as ap
    from autopilot.browser.engine import BrowserManager
    from autopilot.workers.apply import ApplicationRunner

    _Handler.log.clear()
    app_id = _setup(s, profile, f"{server}/apply_form.html")
    real, calls = ap.extract_fields, [0]

    def extract_then_crash(page):
        calls[0] += 1
        if calls[0] == 1:  # SIGKILL the real Chromium processes of this test
            subprocess.run(["pkill", "-9", "-f", "playwright_chromiumdev_profile"], check=False)
            time.sleep(1)
        return real(page)

    monkeypatch.setattr(ap, "extract_fields", extract_then_crash)
    bm = BrowserManager()
    try:
        r1 = ApplicationRunner(bm, "crash-test").run(app_id)
        app = _reload(s, app_id)
        assert r1.status == "RETRY" and app.status == "QUEUED" and app.retry_count == 1, app.status_reason
        assert app.submit_clicked_at is None and not [p for p in _Handler.log if p.startswith("/submit-log")]
        r2 = ApplicationRunner(bm, "crash-test").run(app_id)
        assert r2.status == "SUBMITTED", _reload(s, app_id).status_reason
        assert bm.launches == 2  # the crashed browser was replaced
        assert len([p for p in _Handler.log if p.startswith("/submit-log")]) == 1
    finally:
        bm.close()


def test_watchdog_marks_dead_worker_and_reclaims(s):
    from autopilot.models import Notification
    from autopilot.workers.runtime import scheduler_tick

    s.add(WorkerHeartbeat(worker_id="worker-ghost", kind="worker", started_at=utcnow(),
                          last_seen=utcnow() - dt.timedelta(minutes=10), info={"status": "ALIVE"}))
    s.add(Task(type="discover", payload={"source_id": 1}, status="RUNNING", locked_by="worker-ghost",
               locked_until=utcnow() + dt.timedelta(hours=1), attempts=1, max_attempts=3))
    s.commit()
    out = scheduler_tick("test-scheduler")
    assert out["watchdog"]["dead_workers"] == 1
    s.expire_all()
    assert s.get(WorkerHeartbeat, "worker-ghost").info["status"] == "DEAD"
    t = s.scalar(select(Task).where(Task.locked_by == "worker-ghost"))
    assert t.status == "PENDING"  # reclaimed for another worker (discovery is safe to redo)
    assert s.scalar(select(Notification).where(Notification.kind == "worker_dead"))
    assert scheduler_tick("test-scheduler")["watchdog"]["dead_workers"] == 0  # alerts once
