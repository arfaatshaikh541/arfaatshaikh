"""State machine, queue locking, scheduler, retries, crash recovery and reports."""
import datetime as dt
import threading

import pytest
from sqlalchemy import func, select

from autopilot.connectors.base import NormalizedJob
from autopilot.db import session_scope
from autopilot.jobs.pipeline import ingest
from autopilot.models import Application, ApplicationStatus as S, Job, JobSource, Report, Task, utcnow
from autopilot.settings_store import AutomationSettings, load, save
from autopilot.state import IllegalTransition, transition
from autopilot.workers import queue


def _job(s, ext="1", **kw):
    j, _ = ingest(s, None, NormalizedJob(platform="greenhouse", board="b", external_id=ext, url=f"https://x/{ext}",
                                         apply_url=f"https://x/{ext}", apply_method="greenhouse_hosted_form",
                                         title=kw.get("title", f"Role {ext}"), company="Co", location="Dubai"), [])
    return j


def _app(s, status=S.EVALUATED, mode="LIVE", ext="1"):
    a = Application(job_id=_job(s, ext).id, mode=mode, status=status.value)
    s.add(a)
    s.flush()
    return a


def test_cannot_jump_to_submitted_without_evidence(s):
    a = _app(s)
    transition(s, a, S.QUEUED)
    with pytest.raises(IllegalTransition):
        transition(s, a, S.SUBMITTED)
    for st in (S.STARTED, S.FORM_COMPLETED, S.SUBMITTING):
        transition(s, a, st)
    with pytest.raises(IllegalTransition, match="evidence"):
        transition(s, a, S.SUBMITTED)
    from autopilot.evidence import add_evidence
    from autopilot.state import log_event

    ev = log_event(s, a, "x")
    add_evidence(s, a, ev, "PRE_SUBMIT_SCREENSHOT", png=b"\x89PNGfake")
    with pytest.raises(IllegalTransition):  # a pre-submit screenshot is not proof
        transition(s, a, S.SUBMITTED)
    add_evidence(s, a, ev, "CONFIRMATION_TEXT", value="Thank you for applying")
    transition(s, a, S.SUBMITTED)
    assert a.submitted_at is not None


def test_dry_run_can_never_submit(s):
    a = _app(s, mode="DRY_RUN")
    for st in (S.QUEUED, S.STARTED, S.FORM_COMPLETED):
        transition(s, a, st)
    with pytest.raises(IllegalTransition):
        transition(s, a, S.SUBMITTING)


def test_unique_application_per_job_and_mode(s):
    a = _app(s)
    s.commit()
    s.add(Application(job_id=a.job_id, mode="LIVE", status="EVALUATED"))
    with pytest.raises(Exception):
        s.commit()
    s.rollback()


def test_queue_claim_is_exclusive_under_concurrency():
    with session_scope() as s:
        for i in range(20):
            queue.enqueue(s, "evaluate", {"job_id": i}, dedupe_key=f"e:{i}")
        assert queue.enqueue(s, "evaluate", {"job_id": 0}, dedupe_key="e:0") is None  # dedupe
    claimed: list[int] = []
    lock = threading.Lock()

    def worker(n):
        while True:
            with session_scope() as s:
                t = queue.claim(s, f"w{n}", 60)
                if t is None:
                    return
                with lock:
                    claimed.append(t.id)

    ths = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    assert len(claimed) == 20 and len(set(claimed)) == 20


def test_concurrent_application_claim_only_one_wins(s):
    from autopilot.workers.apply import _claim

    a = _app(s)
    transition(s, a, S.QUEUED)
    s.commit()
    wins = []

    def attempt(n):
        with session_scope() as ss:
            if _claim(ss, a.id, f"w{n}", "sid") is not None:
                wins.append(n)

    ths = [threading.Thread(target=attempt, args=(i,)) for i in range(5)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    assert len(wins) == 1


def test_crash_during_submitting_becomes_unknown_not_retried(s):
    a = _app(s)
    for st in (S.QUEUED, S.STARTED, S.FORM_COMPLETED, S.SUBMITTING):
        transition(s, a, st)
    b = _app(s, ext="2")
    for st in (S.QUEUED, S.STARTED):
        transition(s, b, st)
    past = utcnow() - dt.timedelta(minutes=5)
    for app in (a, b):
        s.add(Task(type="apply", payload={"application_id": app.id}, status="RUNNING", locked_by="dead",
                   locked_until=past, attempts=1, max_attempts=1))
    s.commit()
    with session_scope() as ss:
        assert queue.reclaim_expired(ss) == 2
    s.expire_all()
    assert s.get(Application, a.id).status == "UNKNOWN"
    assert s.get(Application, b.id).status == "QUEUED"  # safe: never reached submit


def test_scheduler_respects_state_and_limits(s):
    from autopilot.workers.runtime import scheduler_tick

    src = JobSource(connector="greenhouse", identifier="acme")
    s.add(src)
    live = _app(s, ext="9")
    transition(s, live, S.QUEUED)
    s.commit()
    assert scheduler_tick("t")["discover"] == 0  # STOPPED by default
    with session_scope() as ss:
        auto = load(ss, AutomationSettings)
        auto.state, auto.allowed_hours_start, auto.allowed_hours_end = "RUNNING", 0, 24
        save(ss, auto)
    r = scheduler_tick("t")
    assert r["discover"] == 1 and r["apply"] == 0  # LIVE app is never dispatched while in DRY_RUN mode
    a = _app(s, mode="DRY_RUN")
    transition(s, a, S.QUEUED)
    s.commit()
    r = scheduler_tick("t")
    assert r["discover"] == 0 and r["apply"] == 1
    r = scheduler_tick("t")
    assert r["discover"] == 0 and r["apply"] == 0  # deduped / one apply at a time
    with session_scope() as ss:
        auto = load(ss, AutomationSettings)
        auto.max_applications_per_day = 0
        save(ss, auto)
        ss.execute(Task.__table__.delete().where(Task.type == "apply"))
    r = scheduler_tick("t")
    assert r["apply"] == 0 and r["apply_gate"] == "daily application limit reached"


def test_allowed_hours_gate(s):
    from autopilot.workers.tasks import apply_gate

    auto = AutomationSettings(state="RUNNING", timezone="UTC")
    h = dt.datetime.now(dt.timezone.utc).hour
    auto.allowed_hours_start, auto.allowed_hours_end = (h + 1) % 24, max((h + 1) % 24 + 1, 1)
    ok, wait, why = apply_gate(s, auto, "greenhouse")
    assert not ok and why == "outside allowed hours" and wait > 0


def test_worker_retries_transient_and_records_permanent(monkeypatch):
    from autopilot.connectors.base import PermanentError, TransientError
    from autopilot.connectors import discovery
    from autopilot.workers.runtime import Worker

    calls = {"n": 0}

    class Flaky(discovery.DiscoveryConnector):
        def fetch(self, identifier, options):
            calls["n"] += 1
            raise TransientError("HTTP 503") if identifier == "flaky" else PermanentError("HTTP 404")

    monkeypatch.setitem(discovery.DISCOVERY_CONNECTORS, "greenhouse", Flaky)
    with session_scope() as ss:
        a = JobSource(connector="greenhouse", identifier="flaky")
        b = JobSource(connector="greenhouse", identifier="gone")
        ss.add_all([a, b])
        ss.flush()
        queue.enqueue(ss, "discover", {"source_id": a.id}, dedupe_key="d:a", max_attempts=3)
        queue.enqueue(ss, "discover", {"source_id": b.id}, dedupe_key="d:b")
    w = Worker()
    assert w.run_once() and w.run_once()
    with session_scope() as ss:
        ta = ss.scalar(select(Task).where(Task.dedupe_key == "d:a"))
        tb = ss.scalar(select(Task).where(Task.dedupe_key == "d:b"))
        assert ta.status == "PENDING" and ta.run_after > utcnow() - dt.timedelta(seconds=1)  # backoff scheduled
        assert tb.status == "DONE" and "404" in ss.scalar(select(JobSource.last_error).where(JobSource.identifier == "gone"))


def test_evaluate_creates_queued_application_only_when_rules_pass(s, profile):
    from autopilot.profile.service import set_fact, store_cv
    from autopilot.workers.tasks import handle_evaluate

    profile.preferences = {**profile.preferences, "target_roles": ["Analyst"], "target_locations": ["Dubai"],
                           "min_match_score": 0}
    store_cv(s, profile, "cv.txt", b"x cv")
    set_fact(s, profile, "work_authorization", "authorized:united arab emirates", "yes")
    j1 = _job(s, "1", title="Security Analyst")
    j2 = _job(s, "2", title="Chef")
    s.commit()
    assert handle_evaluate({"job_id": j1.id}, "t")["decision"] == "APPLY"
    assert handle_evaluate({"job_id": j2.id}, "t")["decision"] == "SKIP"
    s.expire_all()
    apps = s.scalars(select(Application)).all()
    assert len(apps) == 1 and apps[0].status == "QUEUED" and apps[0].mode == "DRY_RUN"  # default mode
    assert apps[0].cv_version_id is not None


def test_report_counts_come_from_db_and_separate_modes(s):
    from autopilot.evidence import add_evidence
    from autopilot.reports import generate
    from autopilot.state import log_event

    with session_scope() as ss:
        save(ss, AutomationSettings(timezone="UTC"))
    r0 = generate(s)
    assert r0.data["live"]["submitted"] == 0 and r0.data["jobs_discovered"] == 0  # empty DB -> zeros
    live = _app(s, ext="1")
    dry = _app(s, mode="DRY_RUN", ext="2")
    for st in (S.QUEUED, S.STARTED, S.FORM_COMPLETED, S.SUBMITTING):
        transition(s, live, st)
    add_evidence(s, live, log_event(s, live, "c"), "CONFIRMATION_TEXT", value="Thank you for applying")
    transition(s, live, S.SUBMITTED)
    for st in (S.QUEUED, S.STARTED, S.FORM_COMPLETED, S.DRY_RUN_COMPLETE):
        transition(s, dry, st)
    s.commit()
    r = generate(s)
    assert r.data["jobs_discovered"] == 2
    assert r.data["live"]["submitted"] == 1 and r.data["live"]["by_platform"] == {"greenhouse": 1}
    assert r.data["dry_run"]["submitted"] == 0 and r.data["dry_run"]["dry_run_complete"] == 1
    assert "Applications submitted:   1" in r.text
    assert s.scalar(select(func.count(Report.id))) == 2


def test_long_rate_limit_defers_instead_of_blocking(monkeypatch):
    from autopilot.ratelimit import RateLimited, penalize, reserve_slot
    from autopilot.workers.runtime import Worker

    reserve_slot("host:slow.example", 1)
    penalize("host:slow.example", retry_after_s=600)
    with pytest.raises(RateLimited):
        reserve_slot("host:slow.example", 1, max_wait_s=30)
    from autopilot.connectors import discovery
    from autopilot.connectors.base import DiscoveryConnector

    class Slow(DiscoveryConnector):
        def fetch(self, identifier, options):
            return self.http.get_json("https://slow.example/jobs")

    monkeypatch.setitem(discovery.DISCOVERY_CONNECTORS, "greenhouse", Slow)
    with session_scope() as ss:
        src = JobSource(connector="greenhouse", identifier="slow")
        ss.add(src)
        ss.flush()
        queue.enqueue(ss, "discover", {"source_id": src.id}, dedupe_key="d:slow")
    import time

    t0 = time.monotonic()
    assert Worker().run_once()
    assert time.monotonic() - t0 < 10  # did not sit in a 10-minute sleep
    with session_scope() as ss:
        t = ss.scalar(select(Task).where(Task.dedupe_key == "d:slow"))
        assert t.status == "PENDING" and t.attempts == 0 and "deferred" in t.last_error
        assert t.run_after > utcnow() + dt.timedelta(minutes=5)


def test_shutdown_interrupts_waits():
    import time

    from autopilot.lifecycle import STOP, ShuttingDown, sleep

    STOP.set()
    try:
        t0 = time.monotonic()
        with pytest.raises(ShuttingDown):
            sleep(600)
        assert time.monotonic() - t0 < 1
    finally:
        STOP.clear()
