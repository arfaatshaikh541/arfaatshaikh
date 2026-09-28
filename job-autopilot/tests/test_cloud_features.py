import datetime as dt
import http.server
import json
import socket
import threading

import pytest
from sqlalchemy import select, text

from autopilot.db import get_engine, session_scope
from autopilot.models import Notification, NotificationDelivery, utcnow
from autopilot.security.credentials import store_credential
from autopilot.settings_store import AutomationSettings, NotificationSettings, load, save


def _port():
    with socket.socket() as so:
        so.bind(("127.0.0.1", 0))
        return so.getsockname()[1]


def test_email_notification_delivered_over_real_smtp(s, user):
    from aiosmtpd.controller import Controller

    from autopilot.notifications import deliver_pending, notify

    got = []

    class H:
        async def handle_DATA(self, server, session, envelope):
            got.append(envelope)
            return "250 OK"

    port = _port()
    ctl = Controller(H(), hostname="127.0.0.1", port=port)
    ctl.start()
    try:
        save(s, NotificationSettings(email_enabled=True, smtp_host="127.0.0.1", smtp_port=port, smtp_security="none",
                                     email_from="autopilot@example.invalid", email_to="me@example.invalid"))
        n = notify(s, "verification_required", "HUMAN VERIFICATION REQUIRED", "Application: X",
                   link_path="/verify/1", severity="critical")
        s.commit()
        assert deliver_pending(s) == {"sent": 1, "failed": 0}
        s.commit()
    finally:
        ctl.stop()
    assert len(got) == 1 and b"HUMAN VERIFICATION REQUIRED" in got[0].content
    d = s.scalar(select(NotificationDelivery).where(NotificationDelivery.notification_id == n.id))
    assert d.status == "SENT" and d.attempts == 1


def test_telegram_request_and_retry_then_give_up(s, user):
    from autopilot.notifications import deliver_pending, notify

    seen = []

    class Rec(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append((self.path, json.loads(self.rfile.read(int(self.headers["content-length"])))))
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Rec)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    store_credential(s, user_id=user.id, platform_key="notify:telegram", username=None, secret="123:BOTTOKEN")
    save(s, NotificationSettings(telegram_enabled=True, telegram_chat_id="42",
                                 telegram_api_base=f"http://127.0.0.1:{srv.server_address[1]}"))
    notify(s, "test", "Title", "Body", link_path="/x")
    s.commit()
    assert deliver_pending(s)["sent"] == 1
    srv.shutdown()
    srv.server_close()
    assert seen[0][0] == "/bot123:BOTTOKEN/sendMessage" and seen[0][1]["chat_id"] == "42"
    # Channel now unreachable: retried at the configured interval, then GAVE_UP
    auto = load(s, AutomationSettings)
    auto.max_notification_attempts = 2
    save(s, auto)
    n = notify(s, "test", "Again", "Body")
    s.commit()
    assert deliver_pending(s)["failed"] == 1
    d = s.scalar(select(NotificationDelivery).where(NotificationDelivery.notification_id == n.id))
    assert d.status == "PENDING" and d.next_attempt_at > utcnow()
    d.next_attempt_at = utcnow()
    s.commit()
    deliver_pending(s)
    s.commit()
    s.refresh(d)
    assert d.status == "GAVE_UP" and d.attempts == 2 and "BOTTOKEN" not in (d.last_error or "")
    assert s.get(Notification, n.id) is not None  # the dashboard notification always exists


def test_reconciliation_matches_only_real_confirmation(s):
    from autopilot.reconcile import Mail, matches

    t = dt.datetime(2026, 9, 1, 10, 0, tzinfo=dt.timezone.utc)
    ok = Mail("<1@x>", "Acme Careers <no-reply@greenhouse.io>", "Thank you for applying to Acme",
              t + dt.timedelta(minutes=2), "We have received your application for SOC Analyst.")
    assert matches("Acme", "SOC Analyst", t, ok)
    assert not matches("Globex", "SOC Analyst", t, ok)  # different employer
    early = Mail(ok.message_id, ok.sender, ok.subject, t - dt.timedelta(hours=1), ok.body)
    assert not matches("Acme", "SOC Analyst", t, early)  # before the submit click
    promo = Mail("<2@x>", "Acme <news@acme.example>", "Acme newsletter", t + dt.timedelta(minutes=5), "Our new product")
    assert not matches("Acme", "SOC Analyst", t, promo)  # no confirmation wording


def test_reconcile_by_email_promotes_unknown_to_submitted(s, profile):
    from autopilot.connectors.base import NormalizedJob
    from autopilot.jobs.pipeline import ingest
    from autopilot.models import Application, ApplicationStatus as S
    from autopilot.reconcile import Mail, reconcile_by_email
    from autopilot.state import transition

    job, _ = ingest(s, None, NormalizedJob(platform="greenhouse", board="b", external_id="1", url="https://x/1",
                                           apply_url="https://x/1", apply_method="greenhouse_hosted_form",
                                           title="SOC Analyst", company="Acme"), [])
    a = Application(job_id=job.id, mode="LIVE", status="EVALUATED")
    s.add(a)
    s.flush()
    for st in (S.QUEUED, S.STARTED, S.FORM_COMPLETED, S.SUBMITTING, S.UNKNOWN):
        transition(s, a, st)
    s.commit()
    mail = [Mail("<9@x>", "Acme Recruiting", "Application received", utcnow() + dt.timedelta(minutes=1),
                 "Thank you for applying. We've received your application.")]
    assert reconcile_by_email(s, mail)["confirmed"] == 1
    s.commit()
    assert a.status == "SUBMITTED" and any(e.kind == "CONFIRMATION_EMAIL" for e in a.evidence)


def test_migrations_upgrade_a_legacy_schema():
    from autopilot.migrations import run_migrations

    eng = get_engine()
    with eng.begin() as c:
        c.execute(text("ALTER TABLE applications DROP COLUMN submit_clicked_at"))
        c.execute(text("ALTER TABLE platforms DROP COLUMN capabilities"))
        c.execute(text("DELETE FROM schema_migrations"))
    applied = run_migrations(eng)
    assert applied == ["0001_applications_submit_clicked_at", "0002_platforms_capabilities"]
    with eng.connect() as c:
        cols = {r[0] for r in c.execute(text("SELECT column_name FROM information_schema.columns "
                                             "WHERE table_name IN ('applications','platforms')"))}
    assert {"submit_clicked_at", "capabilities"} <= cols
    assert run_migrations(eng) == []  # idempotent


def test_destination_policy_separates_environments():
    from autopilot.security.destinations import DestinationRefused, check_destination

    check_destination("http://127.0.0.1:8080/form", "test")
    with pytest.raises(DestinationRefused):
        check_destination("https://93.184.215.14/", "test")  # public host from a test env
    with pytest.raises(DestinationRefused):
        check_destination("https://127.0.0.1/", "production")  # SSRF to loopback
    with pytest.raises(DestinationRefused):
        check_destination("https://10.0.0.5/admin", "production")
    with pytest.raises(DestinationRefused):
        check_destination("https://169.254.169.254/latest/meta-data", "production")  # cloud metadata
    with pytest.raises(DestinationRefused):
        check_destination("http://93.184.215.14/", "production")  # plain http
    check_destination("https://93.184.215.14/", "production")
    with pytest.raises(DestinationRefused):
        check_destination("file:///etc/passwd", "production")


def test_live_mode_refused_outside_production(monkeypatch, user):
    from fastapi.testclient import TestClient

    from autopilot.config import reset_config_cache
    from autopilot.web.app import app

    monkeypatch.setenv("JOBAP_ENVIRONMENT", "development")
    reset_config_cache()
    try:
        with TestClient(app) as c:
            c.post("/login", data={"email": "owner@test.invalid", "password": "correct horse battery"})
            import re

            csrf = re.search(r'name="csrf" value="([^"]+)"', c.get("/").text).group(1)
            r = c.post("/automation", data={"csrf": csrf, "action": "mode", "mode": "LIVE", "confirm": "LIVE"})
            assert "requires JOBAP_ENVIRONMENT=production" in r.text
            m = c.get("/metrics")
            assert m.status_code == 200 and "jobap_queue_depth" in m.text
    finally:
        monkeypatch.setenv("JOBAP_ENVIRONMENT", "test")
        reset_config_cache()
    with TestClient(app) as c:
        assert c.get("/metrics").status_code == 401  # not logged in, no token


def test_capability_matrix_is_explicit(s):
    from autopilot.models import Platform

    li = s.get(Platform, "linkedin")
    assert li.status == "NOT_AUTOMATABLE" and set(li.capabilities.values()) == {"NOT_PERMITTED"}
    wd = s.get(Platform, "workday")
    assert wd.status == "NOT_IMPLEMENTED" and wd.capabilities["AUTOMATED_SUBMISSION"] == "NOT_IMPLEMENTED"
    gh = s.get(Platform, "greenhouse")
    assert gh.capabilities["AUTOMATED_SUBMISSION"] == "PENDING_LIVE"
