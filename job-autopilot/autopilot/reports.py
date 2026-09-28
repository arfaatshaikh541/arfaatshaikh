"""Daily reports computed exclusively from database queries.

LIVE and DRY_RUN figures are reported in separate sections; dry-run activity is
never counted as an application.
"""
from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    Application, ApplicationStatus as S, ErrorRecord, Job, JobMatch, Report, WorkerHeartbeat, utcnow,
)
from .settings_store import AutomationSettings, load
from .workers.tasks import day_bounds_utc

SUBMITTED = [S.SUBMITTED.value, S.VERIFIED.value]


def compute(s: Session, day: dt.date, tz: str) -> dict[str, Any]:
    start, end = day_bounds_utc(tz, day)
    in_day = lambda col: (col >= start) & (col < end)  # noqa: E731

    def count(q) -> int:
        return int(s.scalar(q) or 0)

    data: dict[str, Any] = {"date": day.isoformat(), "timezone": tz, "window_utc": [start.isoformat(), end.isoformat()]}
    data["jobs_discovered"] = count(select(func.count(Job.id)).where(in_day(Job.discovered_at)))
    data["duplicates"] = count(select(func.count(Job.id)).where(in_day(Job.discovered_at), Job.duplicate_of_id.isnot(None)))
    data["jobs_evaluated"] = count(select(func.count(JobMatch.id)).where(in_day(JobMatch.evaluated_at)))
    data["jobs_skipped_by_rules"] = count(select(func.count(JobMatch.id)).where(in_day(JobMatch.evaluated_at),
                                                                                JobMatch.decision == "SKIP"))

    for mode in ("LIVE", "DRY_RUN"):
        m: dict[str, Any] = {}
        base = select(func.count(Application.id)).where(Application.mode == mode)
        m["submitted"] = count(base.where(Application.status.in_(SUBMITTED), in_day(Application.submitted_at)))
        for st in (S.FAILED, S.UNKNOWN, S.VERIFICATION_REQUIRED, S.NEEDS_REVIEW, S.SKIPPED, S.DRY_RUN_COMPLETE):
            m[st.value.lower()] = count(base.where(Application.status == st.value, in_day(Application.finished_at)))
        grp = lambda col: {  # noqa: E731
            (k or "UNKNOWN"): v for k, v in s.execute(
                select(col, func.count(Application.id)).join(Job, Job.id == Application.job_id)
                .where(Application.mode == mode, Application.status.in_(SUBMITTED), in_day(Application.submitted_at))
                .group_by(col).order_by(func.count(Application.id).desc())
            ).all()
        }
        m["by_platform"] = grp(Job.platform)
        m["by_role"] = grp(Job.title)
        m["by_company"] = grp(Job.company)
        data[mode.lower()] = m

    data["errors"] = count(select(func.count(ErrorRecord.id)).where(in_day(ErrorRecord.ts)))
    data["errors_by_component"] = dict(s.execute(
        select(ErrorRecord.component, func.count(ErrorRecord.id)).where(in_day(ErrorRecord.ts))
        .group_by(ErrorRecord.component)).all())
    last = s.scalars(select(Application).where(Application.mode == "LIVE", Application.status.in_(SUBMITTED))
                     .order_by(Application.submitted_at.desc()).limit(1)).first()
    data["last_successful_application"] = (
        {"application_id": last.id, "company": last.job.company, "title": last.job.title,
         "submitted_at": last.submitted_at.isoformat()} if last else None)
    data["pending"] = {
        st.value: count(select(func.count(Application.id)).where(Application.status == st.value))
        for st in (S.QUEUED, S.NEEDS_REVIEW, S.UNKNOWN, S.VERIFICATION_REQUIRED)
    }
    sched = s.scalars(select(WorkerHeartbeat).where(WorkerHeartbeat.kind == "scheduler")
                      .order_by(WorkerHeartbeat.last_seen.desc())).first()
    data["scheduler_uptime_hours"] = (
        round((sched.last_seen - sched.started_at).total_seconds() / 3600, 2) if sched else None)
    return data


def render_text(d: dict[str, Any]) -> str:
    L = [f"JOB AUTOPILOT DAILY REPORT — {d['date']} ({d['timezone']})", ""]
    L += [f"Jobs discovered:            {d['jobs_discovered']}",
          f"Jobs evaluated:             {d['jobs_evaluated']}",
          f"Skipped by rules:           {d['jobs_skipped_by_rules']}",
          f"Duplicates detected:        {d['duplicates']}", ""]
    for mode in ("live", "dry_run"):
        m = d[mode]
        L.append("LIVE MODE" if mode == "live" else "DRY RUN (nothing submitted; not counted as applications)")
        if mode == "live":
            L.append(f"  Applications submitted:   {m['submitted']}")
        else:
            L.append(f"  Dry-run forms completed:  {m['dry_run_complete']}")
        L += [f"  Failed:                   {m['failed']}",
              f"  Unknown (investigate):    {m['unknown']}",
              f"  Verification required:    {m['verification_required']}",
              f"  Needs review:             {m['needs_review']}",
              f"  Skipped at apply time:    {m['skipped']}"]
        if mode == "live":
            for k in ("by_platform", "by_role", "by_company"):
                if m[k]:
                    L.append(f"  {k.replace('_', ' ').title()}: " + ", ".join(f"{a}: {b}" for a, b in m[k].items()))
        L.append("")
    L.append(f"Errors: {d['errors']} " + (str(d['errors_by_component']) if d['errors_by_component'] else ""))
    la = d["last_successful_application"]
    L.append("Last successful application: " + (f"#{la['application_id']} {la['title']} @ {la['company']} "
                                                 f"({la['submitted_at']})" if la else "none"))
    L.append("Pending: " + ", ".join(f"{k}={v}" for k, v in d["pending"].items()))
    L.append(f"Scheduler uptime (h): {d['scheduler_uptime_hours'] if d['scheduler_uptime_hours'] is not None else 'NOT RUNNING'}")
    return "\n".join(L)


def generate(s: Session, day: dt.date | None = None, trigger: str = "manual") -> Report:
    auto = load(s, AutomationSettings)
    day = day or dt.datetime.now(ZoneInfo(auto.timezone)).date()
    data = compute(s, day, auto.timezone)
    r = Report(report_date=day, timezone=auto.timezone, trigger=trigger, data=data, text=render_text(data),
               generated_at=utcnow())
    s.add(r)
    s.flush()
    return r
