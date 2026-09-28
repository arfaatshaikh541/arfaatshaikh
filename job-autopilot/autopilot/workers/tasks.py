"""Task handlers: discover, evaluate, apply, daily_report."""
from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import record_error, system_event
from ..connectors.base import PermanentError, PoliteClient, TransientError
from ..connectors.discovery import DISCOVERY_CONNECTORS
from ..db import session_scope
from ..jobs.matching import criteria_json, decide, evaluate, score
from ..jobs.pipeline import ingest
from ..models import (
    Application, ApplicationStatus as S, CandidateProfile, Job, JobMatch, JobSource, Platform, utcnow,
)
from ..profile.service import active_cv, knowledge, preferences, rules
from ..ratelimit import RateLimited
from ..settings_store import AutomationSettings, load
from ..state import log_event, transition
from .queue import enqueue

log = logging.getLogger(__name__)


class Defer(Exception):
    def __init__(self, seconds: float, why: str):
        super().__init__(why)
        self.seconds = seconds
        self.why = why


class Retryable(Exception):
    pass


def the_profile(s: Session) -> CandidateProfile | None:
    """Single-candidate deployment: exactly one candidate profile."""
    profiles = s.scalars(select(CandidateProfile).order_by(CandidateProfile.id)).all()
    if len(profiles) > 1:
        raise RuntimeError("More than one candidate profile; this deployment supports one candidate")
    return profiles[0] if profiles else None


# ------------------------------------------------------------------ discover


def handle_discover(payload: dict, worker_id: str) -> dict:
    sid = payload["source_id"]
    with session_scope() as s:
        src = s.get(JobSource, sid)
        if src is None or not src.enabled:
            return {"skipped": "source disabled or deleted"}
        connector_cls = DISCOVERY_CONNECTORS.get(src.connector)
        if connector_cls is None:
            raise PermanentError(f"Connector {src.connector} NOT SUPPORTED")
        auto = load(s, AutomationSettings)
        prof = the_profile(s)
        terms = (preferences(prof).required_skills + preferences(prof).optional_skills) if prof else []
        identifier, options = src.identifier, dict(src.options or {})
        src.last_run_at = utcnow()
    http = PoliteClient(min_interval_s=auto.request_min_interval_seconds)
    try:
        jobs = connector_cls(http).fetch(identifier, options)
    except RateLimited as e:
        raise Defer(e.wait_s + 1, str(e)) from e
    except (TransientError, PermanentError) as e:
        with session_scope() as s:
            src = s.get(JobSource, sid)
            src.last_error = str(e)[:2000]
            record_error(s, "discovery", e, worker_id=worker_id, platform=src.connector)
        if isinstance(e, TransientError):
            raise Retryable(str(e)) from e
        return {"error": str(e)}
    finally:
        http.close()
    new = dups = 0
    with session_scope() as s:
        for nj in jobs:
            job, created = ingest(s, sid, nj, terms)
            if created:
                new += 1
                if job.duplicate_of_id:
                    dups += 1
                enqueue(s, "evaluate", {"job_id": job.id}, dedupe_key=f"evaluate:{job.id}", priority=50)
        src = s.get(JobSource, sid)
        src.last_success_at = utcnow()
        src.last_error = None
        src.last_job_count = len(jobs)
        system_event(s, "discovery", "source_fetched", worker_id, source_id=sid, connector=src.connector,
                     listed=len(jobs), new=new, duplicates=dups)
    return {"listed": len(jobs), "new": new, "duplicates": dups}


# ------------------------------------------------------------------ evaluate


def handle_evaluate(payload: dict, worker_id: str) -> dict:
    with session_scope() as s:
        job = s.get(Job, payload["job_id"], with_for_update=True)
        prof = the_profile(s)
        if job is None:
            return {"skipped": "job gone"}
        if prof is None:
            raise Defer(3600, "No candidate profile configured")
        prefs, rl, kb = preferences(prof), rules(prof), knowledge(s, prof)
        crit = evaluate(job, prefs, kb)
        sc = score(crit)
        platform = s.get(Platform, job.platform)
        auto = load(s, AutomationSettings)
        d = decide(job, crit, sc, prefs, rl, bool(platform and platform.automatable))
        # Never apply twice to the same underlying job unless explicitly configured.
        if d.decision != "SKIP" and job.duplicate_of_id and not auto.apply_to_duplicates:
            d.decision, d.reasons = "SKIP", [f"Duplicate of job #{job.duplicate_of_id}"]
        m = s.scalar(select(JobMatch).where(JobMatch.job_id == job.id))
        if m is None:
            m = JobMatch(job_id=job.id)
            s.add(m)
        m.score, m.criteria, m.decision, m.decision_reasons = sc, criteria_json(crit), d.decision, d.reasons
        m.rules_snapshot = {"preferences": prefs.model_dump(), "rules": rl.model_dump()}
        m.evaluated_at = utcnow()
        if job.status != "DUPLICATE":
            job.status = "EVALUATED"
        if d.decision == "SKIP":
            return {"decision": "SKIP", "score": sc}
        existing = s.scalar(select(Application).where(Application.job_id == job.id, Application.mode == auto.mode))
        if existing is not None:
            return {"decision": d.decision, "existing_application": existing.id}
        cv = active_cv(s, prof)
        app = Application(job_id=job.id, mode=auto.mode, status=S.EVALUATED.value, cv_version_id=cv.id if cv else None)
        s.add(app)
        s.flush()
        # EVALUATED is the initial state of an application row; record its creation.
        log_event(s, app, "created", worker_id=worker_id, detail={"score": sc, "decision": d.decision,
                                                                   "reasons": d.reasons, "mode": auto.mode})
        if cv is None:
            transition(s, app, S.NEEDS_REVIEW, worker_id=worker_id, reason="No active CV uploaded")
        elif d.decision == "APPLY":
            transition(s, app, S.QUEUED, worker_id=worker_id, reason="; ".join(d.reasons))
        else:
            transition(s, app, S.NEEDS_REVIEW, worker_id=worker_id, reason="; ".join(d.reasons))
        return {"decision": d.decision, "score": sc, "application_id": app.id}


# ------------------------------------------------------------------ apply gating


def local_now(tz: str) -> dt.datetime:
    return dt.datetime.now(ZoneInfo(tz))


def day_bounds_utc(tz: str, day: dt.date) -> tuple[dt.datetime, dt.datetime]:
    z = ZoneInfo(tz)
    start = dt.datetime.combine(day, dt.time(0), z)
    return start.astimezone(dt.timezone.utc), (start + dt.timedelta(days=1)).astimezone(dt.timezone.utc)


def apply_gate(s: Session, auto: AutomationSettings, platform: str) -> tuple[bool, float, str]:
    """Returns (allowed, retry_in_seconds, reason) according to the configured limits."""
    if auto.state != "RUNNING":
        return False, 300, f"automation {auto.state}"
    now = local_now(auto.timezone)
    if not (auto.allowed_hours_start <= now.hour < auto.allowed_hours_end):
        nxt = now.replace(hour=auto.allowed_hours_start, minute=0, second=0, microsecond=0)
        if nxt <= now:
            nxt += dt.timedelta(days=1)
        return False, (nxt - now).total_seconds(), "outside allowed hours"
    start, end = day_bounds_utc(auto.timezone, now.date())
    base = select(func.count(Application.id)).where(Application.started_at >= start, Application.started_at < end,
                                                    Application.mode == auto.mode)
    today = s.scalar(base) or 0
    if today >= auto.max_applications_per_day:
        return False, (end - utcnow()).total_seconds() + 60, "daily application limit reached"
    per_platform = s.scalar(base.join(Job, Job.id == Application.job_id).where(Job.platform == platform)) or 0
    if per_platform >= auto.max_applications_per_platform_per_day:
        return False, (end - utcnow()).total_seconds() + 60, f"daily limit for {platform} reached"
    last = s.scalar(select(func.max(Application.started_at)))
    gap = dt.timedelta(minutes=auto.min_minutes_between_applications)
    if last and utcnow() - last < gap:
        return False, (last + gap - utcnow()).total_seconds() + 1, "minimum gap between applications"
    return True, 0, "ok"
