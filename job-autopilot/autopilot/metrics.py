"""Prometheus text-format metrics computed from the database (no in-memory counters to lose)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    Application, NotificationDelivery, SystemEvent, Task, VerificationRequest, WorkerHeartbeat, utcnow,
)


def _line(name: str, value: float, labels: dict | None = None) -> str:
    lab = ""
    if labels:
        lab = "{" + ",".join(f'{k}="{str(v).replace(chr(34), "")}"' for k, v in sorted(labels.items())) + "}"
    return f"{name}{lab} {value}"


def render_metrics(s: Session) -> str:
    now = utcnow()
    out: list[str] = []
    out.append("# TYPE jobap_tasks gauge")
    for typ, st, n in s.execute(select(Task.type, Task.status, func.count(Task.id)).group_by(Task.type, Task.status)):
        out.append(_line("jobap_tasks", n, {"type": typ, "status": st}))
    out.append("# TYPE jobap_queue_depth gauge")
    out.append(_line("jobap_queue_depth", s.scalar(select(func.count(Task.id)).where(Task.status == "PENDING")) or 0))
    out.append("# TYPE jobap_applications gauge")
    for mode, st, n in s.execute(select(Application.mode, Application.status, func.count(Application.id))
                                 .group_by(Application.mode, Application.status)):
        out.append(_line("jobap_applications", n, {"mode": mode, "status": st}))
    out.append("# TYPE jobap_worker_heartbeat_age_seconds gauge")
    for hb in s.scalars(select(WorkerHeartbeat)):
        out.append(_line("jobap_worker_heartbeat_age_seconds", round((now - hb.last_seen).total_seconds(), 1),
                         {"worker": hb.worker_id, "kind": hb.kind}))
    out.append("# TYPE jobap_verification_requests gauge")
    for st, n in s.execute(select(VerificationRequest.status, func.count(VerificationRequest.id))
                           .group_by(VerificationRequest.status)):
        out.append(_line("jobap_verification_requests", n, {"status": st}))
    out.append("# TYPE jobap_notification_deliveries gauge")
    for ch, st, n in s.execute(select(NotificationDelivery.channel, NotificationDelivery.status,
                                      func.count(NotificationDelivery.id))
                               .group_by(NotificationDelivery.channel, NotificationDelivery.status)):
        out.append(_line("jobap_notification_deliveries", n, {"channel": ch, "status": st}))
    out.append("# TYPE jobap_system_events_24h gauge")
    since = now - dt.timedelta(hours=24)
    for comp, ev, n in s.execute(select(SystemEvent.component, SystemEvent.event, func.count(SystemEvent.id))
                                 .where(SystemEvent.ts > since).group_by(SystemEvent.component, SystemEvent.event)):
        out.append(_line("jobap_system_events_24h", n, {"component": comp, "event": ev}))
    return "\n".join(out) + "\n"
