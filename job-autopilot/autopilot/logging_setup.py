"""Structured JSON logging with mandatory secret redaction."""
from __future__ import annotations

import datetime as dt
import json
import logging
import sys

from .security.redact import RedactingFilter, redact

_FIELDS = ("worker_id", "platform", "job_id", "application_id", "task_id", "event", "duration_ms", "result", "error")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "timestamp": dt.datetime.fromtimestamp(record.created, dt.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for f in _FIELDS:
            v = getattr(record, f, None)
            if v is not None:
                out[f] = v
        if record.exc_text:
            out["exception"] = record.exc_text
        return redact(json.dumps(out, default=str)) or ""


_configured = False


def setup_logging(level: str = "INFO") -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # Never let HTTP client debug logs print headers (Authorization / cookies).
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
