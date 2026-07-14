import logging
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger("app.email")
settings = get_settings()


class EmailProvider(ABC):
    @abstractmethod
    def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None: ...


class SmtpEmailProvider(EmailProvider):
    """Sends via SMTP. Points at MailHog in local development
    (`SMTP_HOST=mailhog`); in production this must point at a real
    transactional email provider's SMTP endpoint — REQUIRES EXTERNAL
    CREDENTIAL (SMTP_USER / SMTP_PASSWORD) when that provider requires
    authentication."""

    def send(self, *, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = f"{settings.email_from_name} <{settings.email_from_address}>"
        message["To"] = to
        message.set_content(text_body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)


_provider: EmailProvider | None = None


def get_email_provider() -> EmailProvider:
    global _provider
    if _provider is None:
        _provider = SmtpEmailProvider()
    return _provider


def send_verification_email(*, to: str, verify_url: str) -> None:
    get_email_provider().send(
        to=to,
        subject="Verify your email address",
        text_body=f"Please verify your email address by visiting: {verify_url}\n\nThis link expires in 24 hours.",
        html_body=f'<p>Please verify your email address:</p><p><a href="{verify_url}">{verify_url}</a></p><p>This link expires in 24 hours.</p>',
    )


def send_password_reset_email(*, to: str, reset_url: str) -> None:
    get_email_provider().send(
        to=to,
        subject="Reset your password",
        text_body=(
            f"We received a request to reset your password. Visit: {reset_url}\n\n"
            "This link expires in 1 hour. If you did not request this, you can safely ignore this email."
        ),
        html_body=(
            f'<p>We received a request to reset your password.</p><p><a href="{reset_url}">{reset_url}</a></p>'
            "<p>This link expires in 1 hour. If you did not request this, you can safely ignore this email.</p>"
        ),
    )


def send_welcome_set_password_email(*, to: str, tenant_name: str, set_password_url: str) -> None:
    get_email_provider().send(
        to=to,
        subject=f"Welcome to {tenant_name} on the Client Operations Platform",
        text_body=(
            f"An account has been created for you as the owner of {tenant_name}.\n\n"
            f"Set your password to get started: {set_password_url}\n\nThis link expires in 1 hour."
        ),
        html_body=(
            f"<p>An account has been created for you as the owner of <strong>{tenant_name}</strong>.</p>"
            f'<p><a href="{set_password_url}">Set your password to get started</a></p><p>This link expires in 1 hour.</p>'
        ),
    )


def send_invitation_email(*, to: str, tenant_name: str, invite_url: str) -> None:
    get_email_provider().send(
        to=to,
        subject=f"You've been invited to join {tenant_name}",
        text_body=(
            f"You have been invited to join {tenant_name} on the Client Operations Platform.\n\n"
            f"Accept your invitation: {invite_url}\n\nThis link expires in 7 days."
        ),
        html_body=(
            f"<p>You have been invited to join <strong>{tenant_name}</strong> on the Client Operations Platform.</p>"
            f'<p><a href="{invite_url}">Accept your invitation</a></p><p>This link expires in 7 days.</p>'
        ),
    )


def send_lead_acknowledgement_email(*, to: str, tenant_name: str, first_name: str, reference_number: str) -> None:
    get_email_provider().send(
        to=to,
        subject=f"Thank you for contacting {tenant_name}",
        text_body=(
            f"Hi {first_name},\n\nThank you for your enquiry with {tenant_name}. "
            f"Your reference number is {reference_number}. A member of our team will be in touch shortly."
        ),
        html_body=(
            f"<p>Hi {first_name},</p><p>Thank you for your enquiry with <strong>{tenant_name}</strong>. "
            f"Your reference number is <strong>{reference_number}</strong>. "
            "A member of our team will be in touch shortly.</p>"
        ),
    )
