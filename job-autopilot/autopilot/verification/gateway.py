"""Human Verification Gateway (worker side).

When a CAPTCHA / OTP / MFA / identity check is detected the worker:
  1. persists a VerificationRequest (application, worker, browser session, stage, expiry)
  2. moves the application to VERIFICATION_REQUIRED (same transaction) and notifies you
  3. stops automating the page and holds the browser context alive
  4. streams the page to your authenticated phone session and applies *your* input
  5. resumes only after it has itself verified, twice in a row, that the challenge is gone
  6. otherwise times out -> VERIFICATION_TIMEOUT (no reloads, no re-submits, no success claimed)
Nothing here solves, hides or bypasses a challenge.
"""
from __future__ import annotations

import datetime as dt
import logging
import queue
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

from playwright.sync_api import Page
from sqlalchemy import func, select

from .. import lifecycle
from ..audit import system_event
from ..db import session_scope
from ..models import VerificationRequest, VerificationStatus as VS, utcnow
from ..notifications import deliver_pending, notify
from .session_server import SessionServer

log = logging.getLogger(__name__)
OPEN_STATES = (VS.OPEN.value, VS.HUMAN_CONNECTED.value, VS.CHECKING.value)


@dataclass
class HoldResult:
    outcome: str  # COMPLETED | TIMEOUT | SESSION_LOST | CANCELLED
    detail: str


def open_sessions(s) -> int:
    return s.scalar(select(func.count(VerificationRequest.id)).where(VerificationRequest.status.in_(OPEN_STATES))) or 0


def safe_url(u: str) -> str:
    p = urlsplit(u)
    return f"{p.scheme}://{p.netloc}{p.path}"


def create_request(s, *, application_id: int | None, platform_key: str | None, user_id: int | None, worker_id: str,
                   browser_session_id: str, endpoint: str, kind: str, detail: str, stage: str, page_url: str,
                   expires_at: dt.datetime, title: str, body: str) -> VerificationRequest:
    vr = VerificationRequest(application_id=application_id, platform_key=platform_key, user_id=user_id,
                             worker_id=worker_id, browser_session_id=browser_session_id, worker_endpoint=endpoint,
                             kind=kind, detail=detail[:2000], stage=stage, page_url=safe_url(page_url),
                             expires_at=expires_at, status=VS.OPEN.value)
    s.add(vr)
    s.flush()
    notify(s, "verification_required", title, body, severity="critical", link_path=f"/verify/{vr.id}",
           application_id=application_id, verification_id=vr.id)
    system_event(s, "verification", "requested", worker_id, verification_id=vr.id, kind=kind, stage=stage)
    return vr


def _apply(page: Page, evt: dict) -> None:
    t = evt["type"]
    if t == "click":
        page.mouse.click(evt["x"], evt["y"])
    elif t == "dblclick":
        page.mouse.dblclick(evt["x"], evt["y"])
    elif t == "type":
        page.keyboard.type(evt["text"], delay=25)  # text is never logged
    elif t == "key":
        page.keyboard.press(" " if evt["key"] == "Space" else evt["key"])
    elif t == "scroll":
        page.mouse.wheel(0, evt["dy"])


def hold(server: SessionServer, vid: int, page_provider: Callable[[], Page], deadline: dt.datetime,
         is_cleared: Callable[[Page], bool], keepalive: Callable[[], None] | None = None,
         poll_s: float = 0.25) -> HoldResult:
    page = page_provider()
    vp = page.viewport_size or {"width": 1366, "height": 900}
    ch = server.open(vid, (vp["width"], vp["height"]))
    ch.set_status(state="waiting", message="Complete the verification on the page, then tap DONE.")
    last_shot = last_check = last_db = 0.0
    confirmations = 0
    connected_recorded = False
    try:
        while True:
            lifecycle.touch()
            now = time.monotonic()
            if lifecycle.STOP.is_set():
                return HoldResult("SESSION_LOST", "Worker shutting down while waiting for verification")
            if utcnow() >= deadline:
                return HoldResult("TIMEOUT", "Verification not completed before the configured timeout")
            page = page_provider()
            if page.is_closed():
                return HoldResult("SESSION_LOST", "Browser page closed while waiting for verification")
            human_done = False
            for _ in range(50):
                try:
                    evt = ch.inbound.get_nowait()
                except queue.Empty:
                    break
                if evt["type"] == "done":
                    human_done = True
                    continue
                try:
                    _apply(page, evt)
                except Exception as e:  # a bad tap must not kill the session
                    log.info("remote input not applied", extra={"event": "remote_input_error", "error": type(e).__name__})
                last_shot = 0.0  # refresh the frame right after input
            if now - last_db > 2.0:
                last_db = now
                with session_scope() as s:
                    vr = s.get(VerificationRequest, vid, with_for_update=True)
                    if vr.status == VS.CANCELLED.value:
                        return HoldResult("CANCELLED", "Cancelled from the dashboard")
                    deadline = min(deadline, vr.expires_at)  # expiry may be shortened from the DB
                    if ch.ever_connected and not connected_recorded:
                        connected_recorded = True
                        vr.status, vr.human_connected_at = VS.HUMAN_CONNECTED.value, utcnow()
                        system_event(s, "verification", "human_connected", vr.worker_id, verification_id=vid)
                    if human_done:
                        vr.status = VS.CHECKING.value
                if keepalive:
                    keepalive()
            if now - last_shot > 0.4:
                last_shot = now
                try:
                    ch.publish(page.screenshot(type="jpeg", quality=55, timeout=5000))
                except Exception:
                    pass
            if human_done or now - last_check > 1.5:
                last_check = now
                if is_cleared(page):
                    confirmations += 1
                    ch.set_status(state="checking", message="Challenge appears cleared, confirming…")
                else:
                    if human_done:
                        ch.set_status(state="waiting", message="The challenge is still present on the page.")
                    confirmations = 0
                if confirmations >= 2:
                    return HoldResult("COMPLETED", "Challenge no longer present (verified twice)")
            time.sleep(poll_s)
    finally:
        server.close(vid, "Automation has taken back control of this session.")


def finish(s, vid: int, result: HoldResult) -> VerificationRequest:
    vr = s.get(VerificationRequest, vid, with_for_update=True)
    vr.status = {"COMPLETED": VS.COMPLETED, "TIMEOUT": VS.TIMEOUT, "SESSION_LOST": VS.SESSION_LOST,
                 "CANCELLED": VS.CANCELLED}[result.outcome].value
    vr.completed_at = utcnow()
    vr.outcome = result.detail
    system_event(s, "verification", result.outcome.lower(), vr.worker_id, verification_id=vid)
    return vr


def deliver_now(notification_ids: list[int]) -> None:
    """Best-effort immediate delivery; failures stay PENDING for the scheduler's retry loop."""
    for nid in notification_ids:
        try:
            with session_scope() as s:
                deliver_pending(s, only_notification=nid)
        except Exception:
            log.warning("immediate notification delivery failed", extra={"event": "notify_deferred"})
