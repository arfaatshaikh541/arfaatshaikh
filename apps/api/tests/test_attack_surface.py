"""Tests for modules.attack_surface. The `verify_domain` HTTP-file check
makes a real outbound request, so success/failure paths are exercised
against a real local HTTP server (not a mock) rather than faking the
network call — the whole point of the mechanism is that it's real. The
Milestone 27 DNS TXT check gets the same treatment: a real local DNS
server, answering real UDP DNS TXT queries via dnspython's async
resolver — the actual protocol, just not the live public internet
(raw external DNS queries are network-blocked in the environment these
tests run in, confirmed directly during Milestone 27's implementation;
see modules.attack_surface.service's module docstring)."""

from __future__ import annotations

import socket
import threading
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import dns.asyncresolver
import dns.message
import dns.rcode
import dns.rrset
import pytest

from core.errors import ConflictError, NotFoundError, ValidationAppError
from db.session import set_tenant_context
from modules.attack_surface import service as attack_surface_service
from modules.identity.models import User
from modules.tenancy.models import Tenant, TenantSecurityProfile, TenantSettings
from tests.helpers import invite_and_accept_member, login, onboard_verified_owner

pytestmark = pytest.mark.asyncio(loop_scope="session")


@contextmanager
def _local_well_known_server(body: str, *, status: int = 200):
    """Serves `body` at the well-known path on 127.0.0.1:<free port>, for
    the duration of the `with` block."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            payload = body.encode("utf-8") if status == 200 else b""
            self.send_response(status)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if payload:
                self.wfile.write(payload)

        def log_message(self, *args):  # silence request logging in test output
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


@contextmanager
def _local_dns_txt_server(txt_value: str | None):
    """Serves a single TXT record from a real local UDP DNS server for the
    duration of the `with` block — a real DNS protocol exchange (real
    query, real wire-format response via dnspython), just against a
    loopback server standing in for a live one, the same reasoning
    `_local_well_known_server` above uses for HTTP. `txt_value=None`
    simulates NXDOMAIN (no record at all)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    stop = threading.Event()

    def serve():
        sock.settimeout(0.2)
        while not stop.is_set():
            try:
                data, addr = sock.recvfrom(512)
            except TimeoutError:
                continue
            request = dns.message.from_wire(data)
            response = dns.message.make_response(request)
            if txt_value is not None:
                qname = request.question[0].name
                rrset = dns.rrset.from_text(qname, 60, "IN", "TXT", f'"{txt_value}"')
                response.answer.append(rrset)
            else:
                response.set_rcode(dns.rcode.NXDOMAIN)
            sock.sendto(response.to_wire(), addr)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        resolver = dns.asyncresolver.Resolver(configure=False)
        resolver.nameservers = ["127.0.0.1"]
        resolver.port = port
        yield resolver
    finally:
        stop.set()
        thread.join()
        sock.close()


async def _make_tenant(session, name: str) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    await set_tenant_context(session, tenant_id)
    slug = f"{name.lower().replace(' ', '-')}-{tenant_id.hex[:6]}"
    session.add(Tenant(id=tenant_id, name=name, slug=slug, status="active"))
    await session.flush()
    session.add(TenantSettings(tenant_id=tenant_id, display_name=name))
    session.add(TenantSecurityProfile(tenant_id=tenant_id))
    await session.flush()
    return tenant_id


async def _make_user(session, email: str) -> uuid.UUID:
    user = User(email=email, password_hash="not-a-real-hash", full_name="Test User", email_verified=True)
    session.add(user)
    await session.flush()
    return user.id


async def test_add_domain_generates_a_verification_token(db):
    tenant_id = await _make_tenant(db, "Attack Surface Add Co")

    domain = await attack_surface_service.add_domain(db, tenant_id=tenant_id, domain="EXAMPLE-add.com")

    assert domain.domain == "example-add.com"  # normalised to lowercase
    assert domain.is_verified is False
    assert domain.verification_token is not None
    assert len(domain.verification_token) > 10


async def test_add_domain_twice_for_same_tenant_conflicts(db):
    tenant_id = await _make_tenant(db, "Attack Surface Dup Co")
    await attack_surface_service.add_domain(db, tenant_id=tenant_id, domain="dup-self.example")
    await db.commit()
    await set_tenant_context(db, tenant_id)

    with pytest.raises(ConflictError, match="already been added to your workspace"):
        await attack_surface_service.add_domain(db, tenant_id=tenant_id, domain="dup-self.example")


async def test_add_domain_already_claimed_by_another_tenant_conflicts(db):
    tenant_a = await _make_tenant(db, "Attack Surface Claim A Co")
    await attack_surface_service.add_domain(db, tenant_id=tenant_a, domain="contested.example")
    await db.commit()

    tenant_b = await _make_tenant(db, "Attack Surface Claim B Co")

    with pytest.raises(ConflictError, match="already claimed by another workspace"):
        await attack_surface_service.add_domain(db, tenant_id=tenant_b, domain="contested.example")


async def test_list_domains_only_returns_the_tenant_own_domains(db):
    tenant_a = await _make_tenant(db, "Attack Surface List A Co")
    await attack_surface_service.add_domain(db, tenant_id=tenant_a, domain="a-owned.example")
    await db.commit()

    tenant_b = await _make_tenant(db, "Attack Surface List B Co")
    await attack_surface_service.add_domain(db, tenant_id=tenant_b, domain="b-owned.example")
    await db.commit()
    await set_tenant_context(db, tenant_b)

    domains = await attack_surface_service.list_domains(db, tenant_id=tenant_b)

    assert [d.domain for d in domains] == ["b-owned.example"]


async def test_remove_domain(db):
    tenant_id = await _make_tenant(db, "Attack Surface Remove Co")
    domain = await attack_surface_service.add_domain(db, tenant_id=tenant_id, domain="removeme.example")
    await db.commit()
    await set_tenant_context(db, tenant_id)

    await attack_surface_service.remove_domain(db, tenant_id=tenant_id, domain_id=domain.id)

    assert await attack_surface_service.list_domains(db, tenant_id=tenant_id) == []


async def test_remove_domain_not_found_raises(db):
    tenant_id = await _make_tenant(db, "Attack Surface Remove Missing Co")

    with pytest.raises(NotFoundError):
        await attack_surface_service.remove_domain(db, tenant_id=tenant_id, domain_id=uuid.uuid4())


async def test_verify_domain_succeeds_when_token_is_present(db):
    tenant_id = await _make_tenant(db, "Attack Surface Verify Ok Co")
    domain = await attack_surface_service.add_domain(db, tenant_id=tenant_id, domain="placeholder.invalid")
    await db.commit()
    await set_tenant_context(db, tenant_id)

    with _local_well_known_server(domain.verification_token) as host:
        domain.domain = host
        await db.flush()
        record, verified_now, message = await attack_surface_service.verify_domain(
            db, tenant_id=tenant_id, domain_id=domain.id, scheme="http"
        )

    assert verified_now is True
    assert record.is_verified is True
    assert record.verification_method == "http_file"
    assert record.verified_at is not None
    assert "verified" in message.lower()


async def test_verify_domain_fails_when_token_is_wrong(db):
    tenant_id = await _make_tenant(db, "Attack Surface Verify Wrong Co")
    domain = await attack_surface_service.add_domain(db, tenant_id=tenant_id, domain="placeholder2.invalid")
    await db.commit()
    await set_tenant_context(db, tenant_id)

    with _local_well_known_server("this-is-not-the-right-token") as host:
        domain.domain = host
        await db.flush()
        record, verified_now, message = await attack_surface_service.verify_domain(
            db, tenant_id=tenant_id, domain_id=domain.id, scheme="http"
        )

    assert verified_now is False
    assert record.is_verified is False
    assert "did not contain" in message


async def test_verify_domain_fails_when_host_is_unreachable(db):
    tenant_id = await _make_tenant(db, "Attack Surface Verify Unreachable Co")
    domain = await attack_surface_service.add_domain(
        db, tenant_id=tenant_id, domain="127.0.0.1:1"
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    record, verified_now, message = await attack_surface_service.verify_domain(
        db, tenant_id=tenant_id, domain_id=domain.id, scheme="http"
    )

    assert verified_now is False
    assert record.is_verified is False
    assert "Could not reach" in message


async def test_verify_domain_fails_when_status_is_not_200(db):
    tenant_id = await _make_tenant(db, "Attack Surface Verify 404 Co")
    domain = await attack_surface_service.add_domain(db, tenant_id=tenant_id, domain="placeholder3.invalid")
    await db.commit()
    await set_tenant_context(db, tenant_id)

    with _local_well_known_server("irrelevant", status=404) as host:
        domain.domain = host
        await db.flush()
        record, verified_now, message = await attack_surface_service.verify_domain(
            db, tenant_id=tenant_id, domain_id=domain.id, scheme="http"
        )

    assert verified_now is False
    assert "HTTP 404" in message


async def test_verify_domain_dns_txt_succeeds_when_token_is_present(db):
    tenant_id = await _make_tenant(db, "Attack Surface DNS Ok Co")
    domain = await attack_surface_service.add_domain(db, tenant_id=tenant_id, domain="dns-verify-ok.invalid")
    await db.commit()
    await set_tenant_context(db, tenant_id)

    with _local_dns_txt_server(domain.verification_token) as resolver:
        record, verified_now, message = await attack_surface_service.verify_domain(
            db, tenant_id=tenant_id, domain_id=domain.id, method="dns_txt", resolver=resolver
        )

    assert verified_now is True
    assert record.is_verified is True
    assert record.verification_method == "dns_txt"
    assert record.verified_at is not None
    assert "verified" in message.lower()


async def test_verify_domain_dns_txt_fails_when_token_is_wrong(db):
    tenant_id = await _make_tenant(db, "Attack Surface DNS Wrong Co")
    domain = await attack_surface_service.add_domain(
        db, tenant_id=tenant_id, domain="dns-verify-wrong.invalid"
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    with _local_dns_txt_server("this-is-not-the-right-token") as resolver:
        record, verified_now, message = await attack_surface_service.verify_domain(
            db, tenant_id=tenant_id, domain_id=domain.id, method="dns_txt", resolver=resolver
        )

    assert verified_now is False
    assert record.is_verified is False
    assert "did not contain" in message


async def test_verify_domain_dns_txt_fails_when_no_record_exists(db):
    tenant_id = await _make_tenant(db, "Attack Surface DNS Missing Co")
    domain = await attack_surface_service.add_domain(
        db, tenant_id=tenant_id, domain="dns-verify-missing.invalid"
    )
    await db.commit()
    await set_tenant_context(db, tenant_id)

    with _local_dns_txt_server(None) as resolver:
        record, verified_now, message = await attack_surface_service.verify_domain(
            db, tenant_id=tenant_id, domain_id=domain.id, method="dns_txt", resolver=resolver
        )

    assert verified_now is False
    assert "No TXT record found" in message


async def test_verify_domain_unknown_method_is_rejected(db):
    tenant_id = await _make_tenant(db, "Attack Surface Bad Method Co")
    domain = await attack_surface_service.add_domain(db, tenant_id=tenant_id, domain="bad-method.invalid")
    await db.commit()
    await set_tenant_context(db, tenant_id)

    with pytest.raises(ValidationAppError, match="Unknown verification method"):
        await attack_surface_service.verify_domain(
            db, tenant_id=tenant_id, domain_id=domain.id, method="carrier_pigeon"
        )


async def test_verify_domain_without_a_token_raises_validation_error(db):
    tenant_id = await _make_tenant(db, "Attack Surface Verify No Token Co")
    domain = await attack_surface_service.add_domain(db, tenant_id=tenant_id, domain="notoken.invalid")
    domain.verification_token = None
    await db.commit()
    await set_tenant_context(db, tenant_id)

    with pytest.raises(ValidationAppError):
        await attack_surface_service.verify_domain(db, tenant_id=tenant_id, domain_id=domain.id)


async def _connected_owner(client, db, *, org: str, email: str, password: str = "Owner-Pass1!"):
    await onboard_verified_owner(client, db, org_name=org, full_name="Owner", email=email, password=password)
    resp = await login(client, email, password)
    assert resp.status_code == 200
    body = resp.json()
    return {
        "tenant_id": body["memberships"][0]["tenant_id"],
        "csrf_token": body["csrf_token"],
        "user_id": body["user"]["id"],
    }


async def test_api_add_list_and_remove_domain(client, db):
    ctx = await _connected_owner(
        client, db, org="API Attack Surface Co", email="owner@api-attack-surface.example"
    )

    add_resp = await client.post(
        "/api/attack-surface/domains",
        json={"domain": "API-Example.com"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert add_resp.status_code == 200, add_resp.text
    body = add_resp.json()
    assert body["domain"] == "api-example.com"
    assert body["is_verified"] is False
    assert body["verification_file_url"] == (
        "https://api-example.com/.well-known/gridkeep-verification.txt"
    )
    domain_id = body["id"]

    list_resp = await client.get("/api/attack-surface/domains")
    assert list_resp.status_code == 200
    assert [d["id"] for d in list_resp.json()] == [domain_id]

    delete_resp = await client.delete(
        f"/api/attack-surface/domains/{domain_id}", headers={"X-CSRF-Token": ctx["csrf_token"]}
    )
    assert delete_resp.status_code == 200

    list_after_resp = await client.get("/api/attack-surface/domains")
    assert list_after_resp.json() == []


async def test_api_verify_domain_unreachable_returns_not_verified(client, db):
    ctx = await _connected_owner(
        client, db, org="API Attack Surface Verify Co", email="owner@api-attack-surface-verify.example"
    )
    add_resp = await client.post(
        "/api/attack-surface/domains",
        json={"domain": "definitely-not-a-real-domain-gridkeep-test.invalid"},
        headers={"X-CSRF-Token": ctx["csrf_token"]},
    )
    assert add_resp.status_code == 200
    domain_id = add_resp.json()["id"]

    verify_resp = await client.post(
        f"/api/attack-surface/domains/{domain_id}/verify", headers={"X-CSRF-Token": ctx["csrf_token"]}
    )

    assert verify_resp.status_code == 200
    body = verify_resp.json()
    assert body["verified_now"] is False
    assert body["domain"]["is_verified"] is False


async def test_security_analyst_can_view_but_not_manage_domains(client, db):
    ctx = await _connected_owner(
        client, db, org="API Attack Surface Perm Co", email="owner@api-attack-surface-perm.example"
    )
    member = await invite_and_accept_member(
        client, db, tenant_id=ctx["tenant_id"], inviter_csrf_token=ctx["csrf_token"],
        email="analyst@api-attack-surface-perm.example", full_name="Analyst", password="Analyst-Pass1!",
        role_name="security_analyst",
    )

    view_resp = await client.get("/api/attack-surface/domains")
    assert view_resp.status_code == 200

    add_resp = await client.post(
        "/api/attack-surface/domains",
        json={"domain": "analyst-cannot-add.example"},
        headers={"X-CSRF-Token": member["csrf_token"]},
    )
    assert add_resp.status_code == 403
