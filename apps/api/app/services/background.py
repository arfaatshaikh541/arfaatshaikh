"""Work the Celery worker does. Each function takes an open session so it can be tested without Celery; the task wrappers live in apps/worker/worker/tasks.py.

* send_email_outbox  deliver the verification / password-reset mail that the API queues in email_outbox (nothing else ever sends it)
* purge_expired      delete expired credentials and old delivered mail
* run_data_validation  re-run every source-sensitive data check and keep the result in the platform audit log

All three are idempotent: running one twice in a row changes nothing the second time.
"""
from __future__ import annotations

import json
import logging
import smtplib
import ssl
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.content_contract import PlatformAuditEvent
from app.models.identity import EmailOutbox, EmailVerificationToken, PasswordResetToken, Session

log = logging.getLogger("woi.background")

REDACTED_PAYLOAD = json.dumps({"token": "[removed after delivery]"})
PURGE_AFTER = timedelta(days=30)


class TransientEmailError(Exception):
    """The mail server could not be reached or asked us to retry later; the row stays queued."""


class PermanentEmailError(Exception):
    """The mail server refused this message; the row is marked failed."""


# ----------------------------------------------------------------------------- email
def base_url(settings: Settings) -> str:
    if settings.public_base_url:
        return settings.public_base_url.rstrip("/")
    origin = str(settings.allowed_origins[0]).rstrip("/") if settings.allowed_origins else ""
    return origin + settings.cookie_path.rstrip("/")


def render_email(template_id: str, payload: dict, url_base: str) -> tuple[str, str]:
    """Return (subject, plain-text body). The token travels in the URL fragment so it is not written to server logs."""
    token = str(payload.get("token", ""))
    if template_id == "verify-email-v1":
        link = f"{url_base}/en/verify-email#token={token}"
        return ("Confirm your email address - World of Islam",
                f"Peace be upon you.\n\nTo confirm your email address open this link (valid for one use):\n{link}\n\n"
                f"If the page asks for a token, paste:\n{token}\n\nIf you did not create an account, ignore this message.\n")
    if template_id == "password-reset-v1":
        link = f"{url_base}/en/reset-password#token={token}"
        return ("Reset your password - World of Islam",
                f"A password reset was requested for your account. Open this link (valid for one use, a short time):\n{link}\n\n"
                f"If the page asks for a token, paste:\n{token}\n\nIf you did not ask for this, ignore this message; your password has not changed.\n")
    raise PermanentEmailError(f"unknown email template {template_id}")


def smtp_sender(settings: Settings) -> Callable[[str, str, str], None]:
    def send(recipient: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = settings.smtp_from or settings.smtp_username, recipient, subject
        message.set_content(body)
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds) as client:
                if settings.smtp_starttls:
                    client.starttls(context=ssl.create_default_context())
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password.get_secret_value())
                client.send_message(message)
        except smtplib.SMTPRecipientsRefused as exc:
            raise PermanentEmailError("recipient refused by the mail server") from exc
        except smtplib.SMTPResponseException as exc:
            if 500 <= exc.smtp_code < 600 and exc.smtp_code not in (530, 535):  # 530/535 are our own credentials: operator problem, retry later
                raise PermanentEmailError(f"mail server rejected the message ({exc.smtp_code})") from exc
            raise TransientEmailError(f"mail server answered {exc.smtp_code}") from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise TransientEmailError(f"mail server unavailable: {type(exc).__name__}") from exc
    return send


def _max_age(settings: Settings, kind: str) -> timedelta:
    seconds = settings.password_reset_ttl_seconds if kind == "password_reset" else settings.email_verification_ttl_seconds
    return timedelta(seconds=seconds)


async def send_email_outbox(session: AsyncSession, settings: Settings, *, send: Callable[[str, str, str], None] | None = None,
                            now: datetime | None = None, limit: int = 50) -> dict:
    now = now or datetime.now(UTC)
    due = (EmailOutbox.sent_at.is_(None), EmailOutbox.failed_at.is_(None), EmailOutbox.available_at <= now)
    if not settings.smtp_host and send is None:
        pending = await session.scalar(select(func.count()).select_from(EmailOutbox).where(*due)) or 0
        if pending:
            log.warning("email_outbox: %s message(s) are waiting but WOI_SMTP_HOST is not set; nothing was sent", pending)
        return {"status": "smtp_not_configured", "pending": int(pending), "sent": 0, "failed": 0, "expired": 0}
    send = send or smtp_sender(settings)
    url_base = base_url(settings)
    sent = failed = expired = 0
    for _ in range(limit):
        row = await session.scalar(select(EmailOutbox).where(*due).order_by(EmailOutbox.available_at).limit(1).with_for_update(skip_locked=True))
        if row is None:
            break
        if now - row.available_at > _max_age(settings, row.kind):  # the token inside is dead by now; do not send a useless link
            row.failed_at, row.failure_reason, row.payload_json = now, "expired before delivery", REDACTED_PAYLOAD
            expired += 1
            await session.commit()
            continue
        try:
            subject, body = render_email(row.template_id, json.loads(row.payload_json), url_base)
            send(row.recipient, subject, body)
        except PermanentEmailError as exc:
            row.failed_at, row.failure_reason, row.payload_json = now, str(exc)[:300], REDACTED_PAYLOAD
            failed += 1
            log.error("email_outbox: %s to a recipient failed permanently: %s", row.kind, exc)
            await session.commit()
            continue
        except TransientEmailError:
            await session.rollback()
            log.warning("email_outbox: mail server unavailable after %s sent; will retry", sent)
            raise
        row.sent_at, row.payload_json = now, REDACTED_PAYLOAD  # at-least-once: a crash between send and commit may send once more; tokens are single use
        sent += 1
        await session.commit()
    log.info("email_outbox: sent=%s failed=%s expired=%s", sent, failed, expired)
    return {"status": "ok", "sent": sent, "failed": failed, "expired": expired}


# ----------------------------------------------------------------------------- purge
async def purge_expired(session: AsyncSession, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    cutoff = now - PURGE_AFTER
    counts = {
        "sessions": (await session.execute(delete(Session).where((Session.expires_at < cutoff) | (Session.revoked_at < cutoff)))).rowcount,
        "email_verification_tokens": (await session.execute(delete(EmailVerificationToken).where(
            (EmailVerificationToken.expires_at < cutoff) | (EmailVerificationToken.consumed_at < cutoff)))).rowcount,
        "password_reset_tokens": (await session.execute(delete(PasswordResetToken).where(
            (PasswordResetToken.expires_at < cutoff) | (PasswordResetToken.consumed_at < cutoff)))).rowcount,
        "email_outbox": (await session.execute(delete(EmailOutbox).where(
            (EmailOutbox.sent_at < cutoff) | (EmailOutbox.failed_at < cutoff)))).rowcount,
    }
    await session.commit()
    log.info("purge_expired: %s", counts)
    return {"status": "ok", "deleted": counts}


# ----------------------------------------------------------------------------- validation
async def run_data_validation(session: AsyncSession) -> dict:
    from app.services.data_validation import validate_database
    from app.services.manifest import load_manifest

    results = await validate_database(session, load_manifest())
    problems = {name: len(items) for name, items in results.items() if items}
    session.add(PlatformAuditEvent(actor_user_id=None, action="system.data_validation", target_type="database", target_id=None,
                                   metadata_json={"checks": len(results), "failed": problems, "first_problems": {n: results[n][:3] for n in problems}}))
    await session.commit()
    if problems:
        log.error("data validation FAILED: %s", problems)
    else:
        log.info("data validation passed: %s checks", len(results))
    return {"status": "failed" if problems else "ok", "checks": len(results), "failed": problems}
