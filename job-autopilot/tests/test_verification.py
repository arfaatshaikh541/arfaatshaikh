"""Human Verification Gateway, end to end, with real Chromium instances and a real web server.

  worker thread : its own Chromium + SessionServer, holds the page when a challenge appears
  web server    : the real FastAPI app under uvicorn (auth, CSP, WebSocket relay)
  "phone"       : a second Chromium emulating an iPhone 13 (touch) that logs in, opens /verify/<id>,
                  TAPS the challenge widget on the streamed image and taps DONE

The challenge widget is a local fixture (tests/fixtures/forms) that only a click can complete; the
automation code never touches it. This validates our mechanism, not any real CAPTCHA provider.
"""
import datetime as dt
import socket
import threading
import time

import pytest
from sqlalchemy import select

from test_browser_apply import CHROME, _Handler, _reload, _setup, server  # noqa: F401  (fixture import)

from autopilot.models import (
    ApplicationStatus as S, AuditLog, Notification, VerificationRequest, VerificationStatus as VS, utcnow,
)


def _free_port() -> int:
    with socket.socket() as so:
        so.bind(("127.0.0.1", 0))
        return so.getsockname()[1]


@pytest.fixture
def web(user):
    import uvicorn

    from autopilot.web.app import app

    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    th.join(10)


class WorkerThread(threading.Thread):
    """A worker with its own Playwright/Chromium (Playwright objects are thread-bound)."""

    def __init__(self, app_id: int):
        super().__init__(daemon=True)
        self.app_id, self.result, self.error = app_id, None, None
        self.ready = threading.Event()

    def run(self):
        import os

        os.environ["JOBAP_BROWSER_EXECUTABLE"] = CHROME if os.path.exists(CHROME) else ""
        from autopilot.browser.engine import BrowserManager
        from autopilot.verification.session_server import SessionServer
        from autopilot.workers.apply import ApplicationRunner

        bm = BrowserManager()
        try:
            self.server = SessionServer("127.0.0.1", _free_port(), "127.0.0.1")
            self.ready.set()
            self.result = ApplicationRunner(bm, "worker-e2e", self.server).run(self.app_id)
        except Exception as e:  # surfaced by the test
            self.error = e
        finally:
            self.ready.set()
            bm.close()


def _wait_vr(s, app_id, timeout=60, w=None):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s.expire_all()
        vr = s.scalar(select(VerificationRequest).where(VerificationRequest.application_id == app_id))
        if vr is not None:
            return vr
        time.sleep(0.3)
    s.expire_all()
    from autopilot.models import Application, ErrorRecord

    a = s.get(Application, app_id)
    errs = [f"{e.error_type}: {e.message[:300]}" for e in s.scalars(select(ErrorRecord))]
    raise AssertionError(f"no verification request created; app {a.status}: {a.status_reason}; errors {errs}; "
                         f"worker error {getattr(w, 'error', None)!r}")


def test_captcha_hold_phone_completes_and_workflow_resumes(s, profile, server, web):
    from playwright.sync_api import sync_playwright

    _Handler.log.clear()
    app_id = _setup(s, profile, f"{server}/captcha_hold_form.html")
    w = WorkerThread(app_id)
    w.start()
    vr = _wait_vr(s, app_id, w=w)
    assert vr.status == VS.OPEN.value and vr.stage == "pre_fill" and vr.kind == "captcha"
    assert vr.worker_endpoint and vr.browser_session_id and vr.expires_at > utcnow()
    assert _reload(s, app_id).status == "VERIFICATION_REQUIRED"
    n = s.scalar(select(Notification).where(Notification.verification_id == vr.id))
    assert n is not None and n.kind == "verification_required" and n.link_path == f"/verify/{vr.id}"
    assert not [p for p in _Handler.log if p.startswith("/submit-log")]  # nothing typed or submitted yet

    with sync_playwright() as p:
        kw = {"executable_path": CHROME} if __import__("os").path.exists(CHROME) else {}
        b = p.chromium.launch(**kw)
        phone = b.new_context(**p.devices["iPhone 13"])
        pg = phone.new_page()
        pg.goto(f"{web}/login")
        pg.fill("input[name=email]", "owner@test.invalid")
        pg.fill("input[name=password]", "correct horse battery")
        pg.tap("button.primary")
        pg.wait_for_url(f"{web}/")
        assert "Human verification required" in pg.inner_text("body")
        pg.goto(f"{web}/verify/{vr.id}")
        # (polled from Python: the page's CSP rightly forbids the eval that wait_for_function needs)
        for _ in range(100):
            if pg.evaluate("() => document.getElementById('rv-img').naturalWidth") > 0:
                break
            time.sleep(0.2)
        else:
            raise AssertionError("no frame received on the phone")
        pg.locator("#rv-img").scroll_into_view_if_needed()
        box = pg.locator("#rv-img").bounding_box()
        assert box["width"] <= 400  # rendered at phone width
        # The fixture widget's button is at (20+10+100, 300+10+25) in the worker's 1366x900 viewport.
        pg.touchscreen.tap(box["x"] + 130 * box["width"] / 1366, box["y"] + 335 * box["height"] / 900)
        time.sleep(2.5)
        pg.screenshot(path=__import__("os").environ.get("JOBAP_TEST_ARTIFACTS", "/tmp") + "/phone-after-tap.png")
        pg.tap("#rv-done")
        w.join(90)
        if w.is_alive():
            s.expire_all()
            pg.screenshot(path=__import__("os").environ.get("JOBAP_TEST_ARTIFACTS", "/tmp") + "/phone-stuck.png")
            v = s.get(VerificationRequest, vr.id)
            raise AssertionError(f"worker did not finish: vr={v.status} status_text={pg.inner_text('#rv-status')!r}")
        phone.close()
        b.close()

    assert w.error is None, w.error
    assert w.result.status == "SUBMITTED", _reload(s, app_id).status_reason
    s.expire_all()
    vr = s.get(VerificationRequest, vr.id)
    assert vr.status == VS.COMPLETED.value and vr.human_connected_at is not None
    app = _reload(s, app_id)
    seq = [e.to_status for e in app.events if e.to_status]
    assert seq == ["QUEUED", "STARTED", "VERIFICATION_REQUIRED", "STARTED", "FORM_COMPLETED", "SUBMITTING",
                   "SUBMITTED"], seq
    assert {"CHALLENGE_SCREENSHOT", "CONFIRMATION_TEXT", "APPLICATION_ID"} <= {e.kind for e in app.evidence}
    assert any(e.event == "preflight" and all(v is True for v in e.detail["checks"].values()) for e in app.events)
    assert len([p for p in _Handler.log if p.startswith("/submit-log")]) == 1
    kinds = {x.kind for x in s.scalars(select(Notification))}
    assert {"verification_required", "verification_completed"} <= kinds
    assert s.scalar(select(AuditLog).where(AuditLog.action == "verification_session_opened"))


def test_verification_timeout_pauses_safely(s, profile, server):
    _Handler.log.clear()
    app_id = _setup(s, profile, f"{server}/captcha_hold_form.html")
    w = WorkerThread(app_id)
    w.start()
    vr = _wait_vr(s, app_id, w=w)
    vr.expires_at = utcnow()  # nobody completes it
    s.commit()
    w.join(60)
    assert w.result.status == "VERIFICATION_TIMEOUT"
    s.expire_all()
    assert s.get(VerificationRequest, vr.id).status == VS.TIMEOUT.value
    app = _reload(s, app_id)
    assert app.status == "VERIFICATION_TIMEOUT" and app.submitted_at is None and app.submit_clicked_at is None
    assert not [p for p in _Handler.log if p.startswith("/submit-log")]
    assert s.scalar(select(Notification).where(Notification.kind == "verification_timeout"))
    from autopilot.state import transition

    transition(s, app, S.QUEUED)  # safe to retry: submit was never clicked


def test_session_server_rejects_unauthenticated_and_forged_tokens():
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import connect

    from autopilot.verification import tokens
    from autopilot.verification.session_server import SessionServer, validate_event

    srv = SessionServer("127.0.0.1", _free_port(), "127.0.0.1")
    srv.open(77, (1366, 900))

    def code(url):
        with connect(url) as c:
            try:
                c.recv(timeout=5)
                c.recv(timeout=5)
            except ConnectionClosed as e:
                return e.rcvd.code
        return None

    base = f"ws://{srv.endpoint}/session/77"
    assert code(base) == 4401
    assert code(base + "?t=77.1.9999999999.deadbeef") == 4401
    assert code(base + "?t=" + tokens.mint(78, 1)) == 4401  # token for another session
    expired = tokens.mint(77, 1, ttl_s=-5)
    assert code(base + "?t=" + expired) == 4401
    assert code(f"ws://{srv.endpoint}/session/99?t=" + tokens.mint(99, 1)) == 4410  # not held
    with connect(base + "?t=" + tokens.mint(77, 1)) as c:
        assert '"hello"' in c.recv(timeout=5)
    # input validation: out-of-viewport clicks, unknown keys, oversize text are dropped
    assert validate_event('{"type":"click","x":5000,"y":1}', (1366, 900)) is None
    assert validate_event('{"type":"key","key":"F12"}', (1366, 900)) is None
    assert validate_event('{"type":"type","text":"' + "x" * 300 + '"}', (1366, 900)) is None
    assert validate_event('{"type":"eval","js":"alert(1)"}', (1366, 900)) is None
    assert validate_event('{"type":"click","x":10,"y":10}', (1366, 900)) == {"type": "click", "x": 10.0, "y": 10.0}


def test_web_relay_requires_login_and_same_origin(s, user):
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from autopilot.web.app import app

    vr = VerificationRequest(worker_id="w", browser_session_id="x", worker_endpoint="127.0.0.1:1", kind="captcha",
                             stage="pre_fill", status="OPEN", expires_at=utcnow() + dt.timedelta(minutes=5))
    s.add(vr)
    s.commit()
    with TestClient(app) as c:
        with pytest.raises(WebSocketDisconnect) as ex:
            with c.websocket_connect(f"/verify/{vr.id}/ws", headers={"origin": "http://testserver"}) as ws:
                ws.receive_text()
        assert ex.value.code == 4403  # not logged in
        c.post("/login", data={"email": "owner@test.invalid", "password": "correct horse battery"})
        with pytest.raises(WebSocketDisconnect) as ex:
            with c.websocket_connect(f"/verify/{vr.id}/ws", headers={"origin": "https://evil.example"}) as ws:
                ws.receive_text()
        assert ex.value.code == 4403  # cross-site WebSocket hijacking blocked
        r = c.get(f"/verify/{vr.id}")
        assert r.status_code == 200 and "script-src 'self'" in r.headers["content-security-policy"]
        assert "script-src 'none'" in c.get("/").headers["content-security-policy"]
