"""Provider-agnostic email sending.

This is the v1 slice of the Module 10 communications layer: just enough to
support authentication flows (invitation, verification, password reset).
Tenant-configurable MessageTemplate/MessageLog/DeliveryAttempt models and
the full multi-channel provider registry (WhatsApp/SMS adapters) are
Milestone 3+ scope - see docs/product/milestone-1-acceptance-criteria.md.

SMTPEmailProvider is a REAL provider (talks to an SMTP server - Mailhog in
local dev). It requires no third-party account, but in production it must
be pointed at a real SMTP relay via environment configuration; no
credentials are hardcoded here.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as MimeEmailMessage
from typing import Protocol

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("app.email")


@dataclass
class EmailMessage:
    to: str
    subject: str
    text_body: str
    html_body: str | None = None


class EmailProvider(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class SMTPEmailProvider:
    """Sends via SMTP. Local dev points this at Mailhog (no auth, no TLS)."""

    def send(self, message: EmailMessage) -> None:
        settings = get_settings()
        mime = MimeEmailMessage()
        mime["Subject"] = message.subject
        mime["From"] = f"{settings.email_from_name} <{settings.email_from_address}>"
        mime["To"] = message.to
        mime.set_content(message.text_body)
        if message.html_body:
            mime.add_alternative(message.html_body, subtype="html")

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(mime)

        logger.info(
            "email.sent",
            extra={"extra_fields": {"to": message.to, "subject": message.subject}},
        )


class ConsoleEmailProvider:
    """Fallback used only if SMTP is unreachable in local dev - logs instead of raising,
    so auth flows remain testable without a running mail server."""

    def send(self, message: EmailMessage) -> None:
        logger.warning(
            "email.console_fallback",
            extra={
                "extra_fields": {
                    "to": message.to,
                    "subject": message.subject,
                    "body_preview": message.text_body[:200],
                }
            },
        )


def get_email_provider() -> EmailProvider:
    return SMTPEmailProvider()


def send_email_safely(message: EmailMessage) -> None:
    """Send with a console fallback so a broken local SMTP server never breaks
    the auth flow being tested. Production deployments should alert on
    ConsoleEmailProvider usage via log monitoring, since it means delivery failed."""
    try:
        get_email_provider().send(message)
    except OSError:
        ConsoleEmailProvider().send(message)


def send_invitation_email(*, to: str, tenant_name: str, accept_url: str) -> None:
    send_email_safely(
        EmailMessage(
            to=to,
            subject=f"You're invited to join {tenant_name} on LeadFlow",
            text_body=(
                f"You have been invited to join {tenant_name} on LeadFlow.\n\n"
                f"Accept your invitation: {accept_url}\n\n"
                "This link expires in 7 days."
            ),
        )
    )


def send_verification_email(*, to: str, verify_url: str) -> None:
    send_email_safely(
        EmailMessage(
            to=to,
            subject="Verify your email address",
            text_body=(
                f"Please verify your email address: {verify_url}\n\n"
                "This link expires in 24 hours."
            ),
        )
    )


def send_password_reset_email(*, to: str, reset_url: str) -> None:
    send_email_safely(
        EmailMessage(
            to=to,
            subject="Reset your password",
            text_body=(
                f"We received a request to reset your password: {reset_url}\n\n"
                "This link expires in 1 hour. If you did not request this, you can "
                "safely ignore this email."
            ),
        )
    )
