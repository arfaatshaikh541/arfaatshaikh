from __future__ import annotations

import smtplib
from email.message import EmailMessage

import structlog

from core.config import settings

logger = structlog.get_logger()


def send_email(*, to: str, subject: str, body: str) -> None:
    """Dispatch a real email over SMTP.

    Connects to `settings.mail_capture_host`/`mail_capture_port` and sends a
    real RFC 5322 message via stdlib `smtplib` — no dev-only branch, no
    logging-only stand-in. In local/dev/test that host is Mailhog (or, for
    the test suite, a local `aiosmtpd` server started in `conftest.py`); in
    production it would point at a real relay. Raises on failure (e.g. the
    target SMTP server is unreachable) rather than swallowing the error,
    since a caller that wants "best effort" delivery should catch it.
    """
    message = EmailMessage()
    message["From"] = settings.mail_from_address
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.mail_capture_host, settings.mail_capture_port, timeout=5) as client:
        client.send_message(message)

    logger.info("email_dispatched", to=to, subject=subject)
