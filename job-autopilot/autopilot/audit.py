from __future__ import annotations

import traceback as tb
from typing import Any

from sqlalchemy.orm import Session

from .models import AuditLog, ErrorRecord, SystemEvent
from .security.redact import redact


def _clean(detail: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (detail or {}).items():
        if any(w in k.lower() for w in ("password", "secret", "token", "cookie", "api_key")):
            out[k] = "[REDACTED]"
        elif isinstance(v, str):
            out[k] = redact(v)
        else:
            out[k] = v
    return out


def audit(s: Session, actor: str, action: str, target: str | None = None, ip: str | None = None, **detail: Any) -> None:
    s.add(AuditLog(actor=actor, action=action, target=target, ip=ip, detail=_clean(detail)))


def system_event(s: Session, component: str, event: str, worker_id: str | None = None, **detail: Any) -> None:
    s.add(SystemEvent(component=component, event=event, worker_id=worker_id, detail=_clean(detail)))


def record_error(
    s: Session,
    component: str,
    exc: BaseException | str,
    *,
    worker_id: str | None = None,
    platform: str | None = None,
    job_id: int | None = None,
    application_id: int | None = None,
    task_id: int | None = None,
) -> ErrorRecord:
    if isinstance(exc, BaseException):
        etype = type(exc).__name__
        msg = str(exc)
        trace = "".join(tb.format_exception(type(exc), exc, exc.__traceback__))
    else:
        etype, msg, trace = "Error", exc, None
    e = ErrorRecord(
        component=component,
        worker_id=worker_id,
        platform=platform,
        job_id=job_id,
        application_id=application_id,
        task_id=task_id,
        error_type=etype[:128],
        message=redact(msg)[:10000] if msg else "",
        traceback=redact(trace),
    )
    s.add(e)
    return e
