"""Operations dashboard, human-verification gateway, notifications and metrics."""
from __future__ import annotations

import asyncio
import datetime as dt
import hmac
import json
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy import func, select

from ..config import get_config
from ..db import session_factory
from ..metrics import render_metrics
from ..models import (
    Application, Notification, NotificationDelivery, VerificationRequest, VerificationStatus as VS, WorkerHeartbeat,
    utcnow,
)
from ..verification import tokens
from ..verification.gateway import OPEN_STATES
from .app import Ctx, _login_redirect, app, authed_get, authed_post, back, render
from .auth import get_session

MAX_CLIENT_MSG = 4096


# ------------------------------------------------------------------ verification pages


@app.get("/verifications", response_class=HTMLResponse)
def verifications(request: Request):
    if not (c := authed_get(request)):
        return _login_redirect()
    rows = c.s.scalars(select(VerificationRequest).order_by(VerificationRequest.id.desc()).limit(200)).all()
    apps = {a.id: a for a in c.s.scalars(select(Application).where(
        Application.id.in_([r.application_id for r in rows if r.application_id])))}
    return render(c, "verifications.html", rows=rows, apps=apps, open_states=OPEN_STATES, now=utcnow())


@app.get("/verify/{vid}", response_class=HTMLResponse)
def verify_page(request: Request, vid: int):
    if not (c := authed_get(request)):
        return _login_redirect()
    vr = c.s.get(VerificationRequest, vid)
    if vr is None:
        c.close()
        raise HTTPException(404)
    a = c.s.get(Application, vr.application_id) if vr.application_id else None
    c.audit("verification_page_view", f"verification:{vid}")
    resp = render(c, "verify.html", vr=vr, a=a, job=a.job if a else None,
                  live=vr.status in OPEN_STATES and vr.expires_at > utcnow())
    return resp


@app.post("/verify/{vid}/cancel")
async def verify_cancel(request: Request, vid: int):
    c, _ = await authed_post(request)
    vr = c.s.get(VerificationRequest, vid, with_for_update=True)
    if vr is not None and vr.status in OPEN_STATES:
        vr.status = VS.CANCELLED.value
        c.audit("verification_cancel", f"verification:{vid}")
    return back(c, "/verifications", "Cancelled; the worker will stop holding the browser within a few seconds")


def _same_origin(ws: WebSocket) -> bool:
    origin = ws.headers.get("origin")
    host = ws.headers.get("host")
    return bool(origin and host and urlsplit(origin).netloc == host)


@app.websocket("/verify/{vid}/ws")
async def verify_ws(ws: WebSocket, vid: int):
    """Authenticated relay between your browser and the worker holding the page.

    Checks: valid login session cookie, same-origin (CSWSH protection), request open and unexpired.
    The worker endpoint is internal; the worker accepts only a short-lived HMAC token minted here."""
    s = session_factory()()
    try:
        found = get_session(s, ws)  # type: ignore[arg-type]
        vr = s.get(VerificationRequest, vid)
        if found is None or not _same_origin(ws) or vr is None or vr.status not in OPEN_STATES \
                or vr.expires_at <= utcnow() or not vr.worker_endpoint:
            await ws.close(code=4403)
            return
        user = found[0]
        from ..audit import audit

        audit(s, user.email, "verification_session_opened", f"verification:{vid}",
              ws.client.host if ws.client else None, worker=vr.worker_id)
        s.commit()
        endpoint = vr.worker_endpoint
        token = tokens.mint(vid, user.id)
    finally:
        s.close()
    await ws.accept()
    from websockets.asyncio.client import connect

    try:
        async with connect(f"ws://{endpoint}/session/{vid}?t={token}", max_size=8 * 1024 * 1024,
                           open_timeout=10) as up:
            async def down():
                async for m in up:
                    if isinstance(m, bytes):
                        await ws.send_bytes(m)
                    else:
                        await ws.send_text(m)

            async def upstream():
                while True:
                    msg = await ws.receive()
                    if msg["type"] == "websocket.disconnect":
                        return
                    text = msg.get("text")
                    if text and len(text) <= MAX_CLIENT_MSG:
                        await up.send(text)

            tasks = [asyncio.ensure_future(down()), asyncio.ensure_future(upstream())]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in tasks:
                t.cancel()
    except (OSError, WebSocketDisconnect):
        pass
    except Exception:
        try:
            await ws.send_text(json.dumps({"type": "status", "state": "error",
                                           "message": "The worker session is not reachable (it may have ended)."}))
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass


# ------------------------------------------------------------------ notifications


@app.get("/notifications", response_class=HTMLResponse)
def notifications_page(request: Request):
    if not (c := authed_get(request)):
        return _login_redirect()
    rows = c.s.scalars(select(Notification).order_by(Notification.id.desc()).limit(200)).all()
    deliveries: dict[int, list] = {}
    for d in c.s.scalars(select(NotificationDelivery).where(NotificationDelivery.notification_id.in_([r.id for r in rows]))):
        deliveries.setdefault(d.notification_id, []).append(d)
    return render(c, "notifications.html", rows=rows, deliveries=deliveries)


@app.post("/notifications/read")
async def notifications_read(request: Request):
    c, _ = await authed_post(request)
    for n in c.s.scalars(select(Notification).where(Notification.read_at.is_(None))):
        n.read_at = utcnow()
    return back(c, "/notifications", "All marked read")


# ------------------------------------------------------------------ metrics


@app.get("/metrics")
def metrics(request: Request):
    cfg = get_config()
    authz = request.headers.get("authorization", "")
    ok = False
    if cfg.metrics_token_file and Path(cfg.metrics_token_file).exists():
        expected = Path(cfg.metrics_token_file).read_text().strip()
        ok = bool(expected) and hmac.compare_digest(authz, f"Bearer {expected}")
    c = Ctx(request)
    try:
        if not ok and c.user is None:
            raise HTTPException(401)
        return PlainTextResponse(render_metrics(c.s), media_type="text/plain; version=0.0.4")
    finally:
        c.close(False)
