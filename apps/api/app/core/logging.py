"""Structured JSON logging configuration.

Log records must never include passwords, tokens, secrets, or full
Authorization headers. Call sites are responsible for only passing safe
fields; this module only wires up the formatter/handlers.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

_REDACT_KEYS = {"password", "token", "secret", "authorization", "refresh_token", "access_token"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if extra:
            for key, value in extra.items():
                if key.lower() in _REDACT_KEYS:
                    continue
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
