"""Shared test helpers.

`SMTPCapture` runs a real aiosmtpd SMTP server on localhost:1025 (the same
address the app's SMTP_HOST/SMTP_PORT point at for local development) so
that registration/invitation/password-reset emails are genuinely sent over
SMTP and genuinely received, not mocked - tests then parse the captured
message body to extract the raw verification/reset/invitation token,
exactly as a human would click a link in their inbox.
"""

import email
import re

from aiosmtpd.controller import Controller
from app.core.config import get_settings
from httpx import AsyncClient


class _CaptureHandler:
    def __init__(self) -> None:
        self.messages: list[email.message.Message] = []

    async def handle_DATA(self, server, session, envelope):
        msg = email.message_from_bytes(envelope.content)
        self.messages.append(msg)
        return "250 Message accepted for delivery"


class SMTPCapture:
    def __init__(self) -> None:
        self.handler = _CaptureHandler()
        self.controller = Controller(self.handler, hostname="localhost", port=1025)

    def start(self) -> None:
        self.controller.start()

    def stop(self) -> None:
        self.controller.stop()

    def clear(self) -> None:
        self.handler.messages.clear()

    def latest_body_for(self, to_email: str) -> str:
        for msg in reversed(self.handler.messages):
            if to_email.lower() in (msg.get("To") or "").lower():
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            return part.get_payload(decode=True).decode("utf-8")
                return msg.get_payload(decode=True).decode("utf-8")
        raise AssertionError(f"No captured email found for {to_email}")


def extract_token_from_url(body: str, param: str = "token") -> str:
    match = re.search(rf"[?&]{param}=([^\s&\"']+)", body)
    if not match:
        raise AssertionError(f"Could not find '{param}=' in email body:\n{body}")
    return match.group(1)


def migrator_asyncpg_url() -> str:
    """The migrator role's connection URL, translated to the asyncpg driver
    for use with SQLAlchemy's async engine in tests that need to bypass RLS
    (seeding/truncating between tests) or deliberately probe RLS directly."""
    settings = get_settings()
    return settings.database_url_sync.replace("postgresql+psycopg", "postgresql+asyncpg")


def csrf_headers(client: AsyncClient) -> dict:
    settings = get_settings()
    token = client.cookies.get(settings.csrf_cookie_name)
    return {"x-csrf-token": token} if token else {}


async def register_verify_login(
    client: AsyncClient, smtp_capture: SMTPCapture, *, email: str, password: str, full_name: str
) -> None:
    resp = await client.post(
        "/auth/register", json={"email": email, "password": password, "full_name": full_name}
    )
    assert resp.status_code == 201, resp.text
    token = extract_token_from_url(smtp_capture.latest_body_for(email), "token")
    verify_resp = await client.post("/auth/verify-email", json={"token": token})
    assert verify_resp.status_code == 200, verify_resp.text
    login_resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
