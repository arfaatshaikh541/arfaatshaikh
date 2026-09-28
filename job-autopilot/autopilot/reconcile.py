"""Reconciliation of applications whose submission status is uncertain.

Candidates: UNKNOWN or VERIFICATION_TIMEOUT applications whose submit control was clicked.
Evidence source implemented: your mailbox, read-only over IMAPS (the employer's confirmation
email). If found -> CONFIRMATION_EMAIL evidence -> SUBMITTED. If not found nothing changes:
the application stays UNKNOWN for a human, and it is never automatically retried.
(ATS applicant-history pages need an applicant login that Greenhouse/Lever/Ashby do not provide;
that source is NOT AVAILABLE.)
"""
from __future__ import annotations

import datetime as dt
import email
import email.policy
import email.utils
import imaplib
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .browser.detect import CONFIRM_TEXT_RE
from .evidence import add_evidence
from .models import Application, ApplicationStatus as S, User
from .security.credentials import use_credential
from .settings_store import ReconcileSettings, load
from .state import log_event, transition


@dataclass
class Mail:
    message_id: str
    sender: str
    subject: str
    date: dt.datetime | None
    body: str


def _norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def matches(app_company: str | None, app_title: str, submitted: dt.datetime, m: Mail) -> bool:
    """A confirmation email must: arrive after the submit click, name the employer (sender/subject/body),
    and contain confirmation wording. The title is used when no company name is known."""
    if m.date is None or m.date < submitted - dt.timedelta(minutes=5):
        return False
    hay = _norm(f"{m.sender} {m.subject} {m.body[:20000]}")
    who = _norm(app_company) if app_company else _norm(app_title)
    if not who or who not in hay:
        return False
    return bool(CONFIRM_TEXT_RE.search(f"{m.subject}\n{m.body}"))


def fetch_mail(rs: ReconcileSettings, password: str, since: dt.date, limit: int = 200) -> list[Mail]:
    out: list[Mail] = []
    with imaplib.IMAP4_SSL(rs.imap_host, rs.imap_port, timeout=30) as M:
        M.login(rs.imap_username, password)
        M.select(rs.imap_folder, readonly=True)
        typ, data = M.search(None, "SINCE", since.strftime("%d-%b-%Y"))
        ids = (data[0] or b"").split()[-limit:]
        for i in ids:
            typ, parts = M.fetch(i, "(BODY.PEEK[])")  # PEEK: never marks mail as read
            raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
            if not raw:
                continue
            msg = email.message_from_bytes(raw, policy=email.policy.default)
            body = ""
            part = msg.get_body(preferencelist=("plain", "html"))
            if part is not None:
                body = re.sub(r"<[^>]+>", " ", part.get_content())
            try:
                date = email.utils.parsedate_to_datetime(msg.get("Date"))
            except (TypeError, ValueError):
                date = None
            out.append(Mail(str(msg.get("Message-ID", "")), str(msg.get("From", "")), str(msg.get("Subject", "")),
                            date, body))
    return out


def candidates(s: Session, lookback_days: int) -> list[Application]:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=lookback_days)
    return s.scalars(select(Application).where(
        Application.status.in_([S.UNKNOWN.value, S.VERIFICATION_TIMEOUT.value]),
        Application.mode == "LIVE", Application.submit_clicked_at.isnot(None),
        Application.submit_clicked_at >= since)).all()


def reconcile_by_email(s: Session, mail: list[Mail] | None = None) -> dict:
    rs = load(s, ReconcileSettings)
    apps = candidates(s, rs.lookback_days)
    if not apps:
        return {"candidates": 0}
    if mail is None:
        if not (rs.imap_enabled and rs.imap_host and rs.imap_username):
            return {"candidates": len(apps), "skipped": "IMAP reconciliation NOT CONFIGURED"}
        owner = s.scalars(select(User).order_by(User.id)).first()
        since = min(a.submit_clicked_at for a in apps).date()
        with use_credential(s, owner.id, "reconcile:imap") as (_, pw):
            mail = fetch_mail(rs, pw, since)
    confirmed = 0
    for app in apps:
        hit = next((m for m in mail if matches(app.job.company, app.job.title, app.submit_clicked_at, m)), None)
        if hit is None:
            continue
        if S(app.status) == S.VERIFICATION_TIMEOUT:
            transition(s, app, S.UNKNOWN, worker_id="reconcile", reason="Confirmation email found; reconciling")
        ev = log_event(s, app, "reconciled_by_email", worker_id="reconcile",
                       detail={"message_id": hit.message_id, "from": hit.sender[:200]})
        add_evidence(s, app, ev, "CONFIRMATION_EMAIL",
                     value=f"From: {hit.sender}\nSubject: {hit.subject}\nDate: {hit.date}\nMessage-ID: {hit.message_id}")
        transition(s, app, S.SUBMITTED, worker_id="reconcile", reason="Employer confirmation email found")
        app.submitted_at = hit.date or app.submitted_at
        confirmed += 1
    return {"candidates": len(apps), "confirmed": confirmed, "emails_scanned": len(mail)}
