"""Live health information. Every value comes from a real check or a real row."""
from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import check_db
from .models import Application, JobSource, Platform, Report, WorkerHeartbeat, utcnow
from .security.vault import vault_status
from .settings_store import AISettings, AutomationSettings, load


def _age(t: dt.datetime | None) -> float | None:
    return (utcnow() - t).total_seconds() if t else None


def system_health(s: Session) -> dict[str, Any]:
    h: dict[str, Any] = {}
    ok, msg = check_db()
    h["database"] = msg
    auto = load(s, AutomationSettings)
    h["automation_state"] = auto.state
    h["mode"] = "LIVE MODE" if auto.mode == "LIVE" else "DRY RUN"
    beats = s.scalars(select(WorkerHeartbeat)).all()
    sched = [b for b in beats if b.kind == "scheduler" and _age(b.last_seen) is not None and _age(b.last_seen) < 90]
    h["scheduler"] = "RUNNING" if sched else "NOT RUNNING"
    workers = [b for b in beats if b.kind == "worker"]
    alive = [b for b in workers if _age(b.last_seen) < 60]
    h["workers"] = f"{len(alive)}/{len(workers)} ALIVE" if workers else "NO WORKERS REGISTERED"
    browsers = [b.info.get("browser") for b in alive if b.info]
    h["browser_workers"] = ", ".join(sorted({str(x) for x in browsers if x})) or "UNKNOWN (no live worker)"
    vok, vmsg = vault_status()
    h["credential_vault"] = vmsg
    ai = load(s, AISettings)
    if ai.provider == "none":
        h["ai_provider"] = "NOT CONFIGURED"
    elif ai.last_check_ok is None:
        h["ai_provider"] = f"{ai.provider}/{ai.model}: NOT TESTED"
    else:
        h["ai_provider"] = f"{ai.provider}/{ai.model}: {'CONNECTED' if ai.last_check_ok else 'FAILED'} " \
                           f"({ai.last_check_message}, {ai.last_check_at})"
    h["job_sources"] = [
        {"id": x.id, "connector": x.connector, "identifier": x.identifier, "enabled": x.enabled,
         "last_success_at": x.last_success_at, "last_error": x.last_error, "last_job_count": x.last_job_count}
        for x in s.scalars(select(JobSource).order_by(JobSource.id))
    ]
    h["platforms"] = [{"key": p.key, "name": p.name, "status": p.status} for p in
                      s.scalars(select(Platform).order_by(Platform.automatable.desc(), Platform.key))]
    h["last_successful_discovery"] = s.scalar(select(func.max(JobSource.last_success_at)))
    h["last_successful_application"] = s.scalar(select(func.max(Application.submitted_at)).where(
        Application.mode == "LIVE", Application.status.in_(["SUBMITTED", "VERIFIED"])))
    h["last_report"] = s.scalar(select(func.max(Report.generated_at)))
    from .models import Task, VerificationRequest
    from .verification.gateway import OPEN_STATES

    h["worker_rows"] = [
        {"id": b.worker_id, "health": "HEALTHY" if _age(b.last_seen) < 60 else ("STALE" if _age(b.last_seen) < 120 else "DEAD"),
         "activity": (b.info or {}).get("activity", "Idle"), "browser": (b.info or {}).get("browser"),
         "task": b.current_task_id, "last_seen": b.last_seen, "started_at": b.started_at}
        for b in sorted(workers, key=lambda b: b.worker_id)
    ]
    open_vr = s.scalars(select(VerificationRequest).where(VerificationRequest.status.in_(OPEN_STATES))
                        .order_by(VerificationRequest.id)).all()
    h["open_verifications"] = open_vr
    running_apply = s.scalar(select(func.count(Task.id)).where(Task.type == "apply", Task.status == "RUNNING")) or 0
    h["browser_sessions"] = running_apply
    h["queue_depth"] = s.scalar(select(func.count(Task.id)).where(Task.status == "PENDING")) or 0
    h["applications_queued"] = s.scalar(select(func.count(Application.id)).where(
        Application.status == "QUEUED", Application.mode == auto.mode)) or 0
    ok_core = ok and h["scheduler"] == "RUNNING" and bool(alive)
    h["system"] = "ONLINE" if ok_core else ("DEGRADED" if ok else "OFFLINE")
    return h
