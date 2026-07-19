"""Milestone 29 — HTTP-level verification that the security headers and
cookie-security defaults actually reach the wire (finding H-02), not just
that the underlying settings/helper functions compute the right values in
isolation."""

from __future__ import annotations

import pytest

from modules.identity import routes as identity_routes
from tests.helpers import onboard_verified_owner

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_hsts_header_present_on_every_response(client):
    resp = await client.get("/healthz")
    assert resp.headers["strict-transport-security"] == "max-age=63072000; includeSubDomains"


async def test_security_headers_present_on_every_response(client):
    resp = await client.get("/healthz")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["x-permitted-cross-domain-policies"] == "none"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"


async def test_session_and_csrf_cookies_are_secure_by_default_without_explicit_opt_out(
    client, db, monkeypatch, unique_email
):
    """The whole test suite runs with ALLOW_INSECURE_COOKIES_FOR_LOCAL_DEV=true
    (conftest.py) so httpx's cookie jar can round-trip cookies over the
    plain http://testserver ASGI transport every other authenticated test
    relies on. This test explicitly flips that one setting off for its own
    duration to prove the real *default* — Secure, opt-out required —
    actually reaches the wire in a genuine Set-Cookie header, not just a
    helper function evaluated in isolation."""
    monkeypatch.setattr(identity_routes.settings, "allow_insecure_cookies_for_local_dev", False)

    await onboard_verified_owner(
        client,
        db,
        org_name="Secure Cookie Co",
        full_name="Owner",
        email=unique_email,
        password="Tenant-Pass1!",
    )
    resp = await client.post(
        "/api/auth/login", json={"email": unique_email, "password": "Tenant-Pass1!"}
    )
    assert resp.status_code == 200

    set_cookie_headers = resp.headers.get_list("set-cookie")
    assert set_cookie_headers, "login did not set any cookies"

    session_cookie = next(h for h in set_cookie_headers if h.startswith("gridkeep_session="))
    csrf_cookie = next(h for h in set_cookie_headers if h.startswith("gridkeep_csrf="))
    assert "Secure" in session_cookie
    assert "HttpOnly" in session_cookie
    assert "Secure" in csrf_cookie


async def test_session_cookie_omits_secure_only_with_explicit_local_dev_opt_out(
    client, db, unique_email
):
    """The inverse of the test above, exercised with the suite's real
    ambient configuration (ALLOW_INSECURE_COOKIES_FOR_LOCAL_DEV=true,
    conftest.py) rather than a monkeypatch — proves the opt-out genuinely
    does what it claims, which is also what makes every other
    cookie-dependent test in this suite able to run at all."""
    await onboard_verified_owner(
        client,
        db,
        org_name="Insecure Local Co",
        full_name="Owner",
        email=unique_email,
        password="Tenant-Pass1!",
    )
    resp = await client.post(
        "/api/auth/login", json={"email": unique_email, "password": "Tenant-Pass1!"}
    )
    assert resp.status_code == 200
    set_cookie_headers = resp.headers.get_list("set-cookie")
    session_cookie = next(h for h in set_cookie_headers if h.startswith("gridkeep_session="))
    assert "Secure" not in session_cookie
