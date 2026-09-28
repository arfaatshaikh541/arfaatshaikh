"""Secret redaction for logs, errors and anything persisted as free text."""
from __future__ import annotations

import logging
import re
import threading
from collections import Counter

REDACTED = "[REDACTED]"

_lock = threading.Lock()
_secrets: Counter[str] = Counter()

# key=value / "key": "value" pairs whose key names a secret.
_KV_RE = re.compile(
    r"""(?ix)
    (["']?(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|authorization|
          cookie|set-cookie|session(?:id)?|otp|bearer)["']?\s*[:=]\s*)
    ("[^"]*"|'[^']*'|[^\s,;&}]+)
    """
)
_BEARER_RE = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
_ANTHROPIC_KEY_RE = re.compile(r"sk-(?:ant|proj)?-?[A-Za-z0-9_-]{16,}")


def register_secret(value: str) -> None:
    if value and len(value) >= 4:
        with _lock:
            _secrets[value] += 1


def unregister_secret(value: str) -> None:
    with _lock:
        if _secrets.get(value, 0) > 1:
            _secrets[value] -= 1
        else:
            _secrets.pop(value, None)


def redact(text: str | None) -> str | None:
    if not text:
        return text
    with _lock:
        known = sorted(_secrets, key=len, reverse=True)
    for s in known:
        text = text.replace(s, REDACTED)
    text = _BEARER_RE.sub(lambda m: m.group(1) + " " + REDACTED, text)
    text = _KV_RE.sub(lambda m: m.group(1) + REDACTED, text)
    text = _ANTHROPIC_KEY_RE.sub(REDACTED, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        record.msg = redact(msg)
        record.args = ()
        for attr in ("error", "detail"):
            if isinstance(getattr(record, attr, None), str):
                setattr(record, attr, redact(getattr(record, attr)))
        if record.exc_info:
            import traceback

            record.exc_text = redact("".join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
        return True
