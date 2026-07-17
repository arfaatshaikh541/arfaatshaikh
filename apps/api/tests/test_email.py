"""Milestone 28: `core/email.send_email` is a real `smtplib` client, not a
log-line stand-in. These tests exercise it against the real local SMTP
server started in `conftest.py` (`_smtp_capture` fixture) — same pattern as
the local HTTP (M11) and DNS (M27) test servers: don't mock the
application-layer call, stand up a real server speaking the real wire
protocol."""

from __future__ import annotations

import pytest

from core.config import settings
from core.email import send_email

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_send_email_delivers_real_message_via_smtp(sent_emails):
    send_email(to="recipient@example.com", subject="Hello", body="This is a real message body.")

    assert len(sent_emails) == 1
    message = sent_emails[0]
    assert message["To"] == "recipient@example.com"
    assert message["From"] == settings.mail_from_address
    assert message["Subject"] == "Hello"
    assert message.get_content().strip() == "This is a real message body."


async def test_send_email_raises_when_smtp_server_unreachable(monkeypatch):
    monkeypatch.setattr(settings, "mail_capture_port", 1)  # nothing listens on port 1
    with pytest.raises(OSError):
        send_email(to="recipient@example.com", subject="Hello", body="Unreachable.")
