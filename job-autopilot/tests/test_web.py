import re

import pytest
from fastapi.testclient import TestClient

PAGES = ["/", "/applications", "/jobs", "/sources", "/platforms", "/profile", "/cv", "/credentials", "/automation",
         "/reports", "/errors", "/audit", "/settings"]


@pytest.fixture
def client(user):
    from autopilot.web.app import app

    with TestClient(app) as c:
        yield c


def _login(c):
    r = c.post("/login", data={"email": "owner@test.invalid", "password": "correct horse battery"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    return re.search(r'name="csrf" value="([^"]+)"', c.get("/").text).group(1)


def test_requires_login_everywhere(client):
    for p in PAGES:
        r = client.get(p, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login", p
    assert client.get("/health").status_code == 401
    assert client.get("/healthz").json() == {"database": "HEALTHY"}


def test_bad_login_and_lockout(client):
    for _ in range(5):
        client.post("/login", data={"email": "owner@test.invalid", "password": "wrong password!!"})
    r = client.post("/login", data={"email": "owner@test.invalid", "password": "correct horse battery"},
                    follow_redirects=False)
    assert "locked" in r.headers["location"]


def test_all_pages_render_with_real_zero_state(client):
    _login(client)
    for p in PAGES:
        r = client.get(p)
        assert r.status_code == 200, (p, r.text[:500])
        assert "content-security-policy" in r.headers
    home = client.get("/").text
    assert "DRY RUN" in home and "AUTOMATION STOPPED" in home
    assert "Applications submitted today (LIVE)</div><div class=\"num\">0<" in home
    assert "NOT CONFIGURED" in home  # AI provider
    assert "NOT_AUTOMATABLE" in client.get("/platforms").text
    assert "0 applications." in client.get("/applications").text


def test_csrf_enforced(client):
    _login(client)
    r = client.post("/automation", data={"action": "start"})
    assert r.status_code == 403
    r = client.post("/automation", data={"action": "start", "csrf": "forged"})
    assert r.status_code == 403


def test_credentials_are_write_only(client):
    csrf = _login(client)
    r = client.post("/credentials", data={"csrf": csrf, "action": "store", "platform_key": "generic_portal",
                                          "username": "me@example.invalid", "secret": "S3cretPassw0rd!"})
    assert r.status_code == 200
    for p in PAGES:
        assert "S3cretPassw0rd!" not in client.get(p).text
    assert "S3cretPassw0rd!" not in client.get("/health").text
    # refuse storing credentials for NOT_AUTOMATABLE platforms
    r = client.post("/credentials", data={"csrf": csrf, "action": "store", "platform_key": "linkedin",
                                          "username": "x", "secret": "y"})
    assert "Refused" in r.text
    # platform not marked CONNECTED merely because a credential was entered
    from autopilot.db import session_scope
    from autopilot.models import Platform

    with session_scope() as s:
        assert s.get(Platform, "generic_portal").status == "NOT_CONFIGURED"


def test_mode_switch_requires_confirmation_and_is_audited(client):
    csrf = _login(client)
    r = client.post("/automation", data={"csrf": csrf, "action": "mode", "mode": "LIVE"})
    assert "Type LIVE" in r.text
    r = client.post("/automation", data={"csrf": csrf, "action": "mode", "mode": "LIVE", "confirm": "LIVE"})
    assert "LIVE MODE" in r.text
    assert "automation_mode" in client.get("/audit").text


def test_cv_upload_and_fact_review_and_xss_escaping(client):
    csrf = _login(client)
    cv = b"<script>alert(1)</script> Name\nSKILLS\nPython, <img src=x onerror=alert(2)>\n"
    r = client.post("/cv", data={"csrf": csrf, "action": "upload"}, files={"file": ("cv.txt", cv, "text/plain")})
    assert "Version 1 stored" in r.text
    prof = client.get("/profile").text
    assert "<img src=x" not in prof and "&lt;img src=x" in prof
    assert "EXTRACTED" in prof
    assert client.get("/cv/1/download").content == cv
    r = client.post("/cv", data={"csrf": csrf, "action": "upload"}, files={"file": ("cv.exe", b"MZ\x90", "application/x")})
    assert "Rejected" in r.text


def test_report_now_uses_db(client):
    csrf = _login(client)
    r = client.post("/automation", data={"csrf": csrf, "action": "report_now"})
    assert r.status_code == 200 and "Applications submitted:   0" in r.text


def test_source_add_validates_identifier(client):
    csrf = _login(client)
    r = client.post("/sources", data={"csrf": csrf, "action": "add", "connector": "greenhouse", "identifier": "../etc"})
    assert "Invalid" in r.text
    r = client.post("/sources", data={"csrf": csrf, "action": "add", "connector": "greenhouse", "identifier": "acme"})
    assert "Source added" in r.text
    r = client.post("/automation", data={"csrf": csrf, "action": "search_now"})
    assert "1 search task(s) queued" in r.text
