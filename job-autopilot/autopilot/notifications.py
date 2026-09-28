"""Notification abstraction.

Channels:
* dashboard : always on (the ``notifications`` table, shown in the web UI)
* email     : SMTP; enabled in settings + password stored in the vault as ``notify:smtp``
* telegram  : Bot API sendMessage; enabled in settings + bot token stored as ``notify:telegram``

Push and WhatsApp are NOT IMPLEMENTED (they need a registered service/business account).
Deliveries are persisted and retried with a fixed interval up to a maximum attempt count.
"""
from __future__ import annotations

import datetime as dt
import logging
import smtplib
import ssl
from email.message import EmailMessage

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_config
from .models import Notification, NotificationDelivery, User, utcnow
from .security.credentials import use_credential
from .security.redact import redact
from .settings_store import AutomationSettings, NotificationSettings, load

log = logging.getLogger(__name__)

CHANNELS = ("email", "telegram")


class ChannelNotConfigured(Exception):
    pass


def enabled_channels(s: Session) -> list[str]:
    ns = load(s, NotificationSettings)
    out = []
    if ns.email_enabled and ns.smtp_host and ns.email_to and ns.email_from:
        out.append("email")
    if ns.telegram_enabled and ns.telegram_chat_id:
        out.append("telegram")
    return out


def notify(s: Session, kind: str, title: str, body: str, *, severity: str = "info", link_path: str | None = None,
           application_id: int | None = None, verification_id: int | None = None) -> Notification:
    """Record a dashboard notification and queue deliveries on every configured channel (same transaction)."""
    n = Notification(kind=kind, severity=severity, title=title[:255], body=redact(body) or "", link_path=link_path,
                     application_id=application_id, verification_id=verification_id)
    s.add(n)
    s.flush()
    for ch in enabled_channels(s):
        s.add(NotificationDelivery(notification_id=n.id, channel=ch, next_attempt_at=utcnow()))
    s.flush()
    return n


def absolute_link(path: str | None) -> str | None:
    if not path:
        return None
    base = get_config().public_base_url.rstrip("/")
    return f"{base}{path}" if base else None


def _owner(s: Session) -> User | None:
    return s.scalars(select(User).order_by(User.id)).first()


def _text(n: Notification) -> str:
    link = absolute_link(n.link_path)
    tail = f"\n\n{link}" if link else (f"\n\nOpen the dashboard: {n.link_path}" if n.link_path else "")
    return f"{n.title}\n\n{n.body}{tail}"


def _send_email(s: Session, n: Notification) -> None:
    ns = load(s, NotificationSettings)
    owner = _owner(s)
    if owner is None:
        raise ChannelNotConfigured("no admin user")
    msg = EmailMessage()
    msg["Subject"] = f"[Job Autopilot] {n.title}"
    msg["From"] = ns.email_from
    msg["To"] = ns.email_to
    msg.set_content(_text(n))
    ctx = ssl.create_default_context()
    if ns.smtp_security == "ssl":
        server = smtplib.SMTP_SSL(ns.smtp_host, ns.smtp_port, timeout=20, context=ctx)
    else:
        server = smtplib.SMTP(ns.smtp_host, ns.smtp_port, timeout=20)
    try:
        if ns.smtp_security == "starttls":
            server.starttls(context=ctx)
        if ns.smtp_username:
            with use_credential(s, owner.id, "notify:smtp") as (_, pw):
                server.login(ns.smtp_username, pw)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass


def _send_telegram(s: Session, n: Notification) -> None:
    ns = load(s, NotificationSettings)
    owner = _owner(s)
    if owner is None:
        raise ChannelNotConfigured("no admin user")
    with use_credential(s, owner.id, "notify:telegram") as (_, token):
        r = httpx.post(f"{ns.telegram_api_base.rstrip('/')}/bot{token}/sendMessage",
                       json={"chat_id": ns.telegram_chat_id, "text": _text(n)[:4000],
                             "disable_web_page_preview": True}, timeout=20)
    if r.status_code != 200 or not r.json().get("ok"):
        raise RuntimeError(f"Telegram API HTTP {r.status_code}: {r.text[:200]}")


_SENDERS = {"email": _send_email, "telegram": _send_telegram}


def deliver_pending(s: Session, limit: int = 20, only_notification: int | None = None) -> dict:
    """Attempt due deliveries. Row-locked so concurrent workers never double-send."""
    auto = load(s, AutomationSettings)
    q = (select(NotificationDelivery).where(NotificationDelivery.status == "PENDING",
                                            NotificationDelivery.next_attempt_at <= utcnow())
         .order_by(NotificationDelivery.id).limit(limit).with_for_update(skip_locked=True))
    if only_notification is not None:
        q = q.where(NotificationDelivery.notification_id == only_notification)
    sent = failed = 0
    for d in s.scalars(q).all():
        n = s.get(Notification, d.notification_id)
        d.attempts += 1
        try:
            _SENDERS[d.channel](s, n)
            d.status, d.sent_at, d.last_error = "SENT", utcnow(), None
            sent += 1
        except Exception as e:
            failed += 1
            d.last_error = redact(f"{type(e).__name__}: {e}")[:1000]
            if d.attempts >= auto.max_notification_attempts:
                d.status = "GAVE_UP"
            else:
                d.next_attempt_at = utcnow() + dt.timedelta(minutes=auto.notification_retry_minutes)
            log.warning("notification delivery failed", extra={"event": "notify_failed", "error": d.last_error})
        s.flush()
    return {"sent": sent, "failed": failed}


def has_due(s: Session) -> bool:
    return s.scalar(select(NotificationDelivery.id).where(
        NotificationDelivery.status == "PENDING", NotificationDelivery.next_attempt_at <= utcnow()).limit(1)) is not None
