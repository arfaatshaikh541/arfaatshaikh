"""Domain ownership verification — the attack-surface perimeter a tenant
claims as their own. Milestone 11 built the HTTP-file method first,
with a documented reason for not also building DNS TXT at the time: raw
DNS queries (arbitrary UDP/TCP port 53 to an external resolver) are
network-blocked in the environment this was built in — confirmed again,
directly, during Milestone 27 (a query to the system-configured resolver
times out). Milestone 27 adds DNS TXT anyway: dnspython's async
resolver genuinely performs the DNS protocol over the wire, and a real
local DNS server (not a mock) stands in for a live one in tests and
verification, the same "the whole point of the mechanism is that it's
real" standard the HTTP-file method already holds itself to — it's the
external network path that's blocked here, not DNS as a protocol.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import dns.asyncresolver
import dns.exception
import dns.resolver
import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import ConflictError, NotFoundError, ValidationAppError
from core.security import generate_opaque_token
from modules.tenancy.models import TenantDomain

WELL_KNOWN_PATH = "/.well-known/gridkeep-verification.txt"
DNS_TXT_RECORD_PREFIX = "_gridkeep-verification"
VERIFICATION_METHODS = ("http_file", "dns_txt")
_HTTP_VERIFICATION_METHOD = "http_file"
_DNS_VERIFICATION_METHOD = "dns_txt"
_REQUEST_TIMEOUT_SECONDS = 10.0
_DNS_TIMEOUT_SECONDS = 10.0


def verification_file_url(domain: str, *, scheme: str = "https") -> str:
    return f"{scheme}://{domain}{WELL_KNOWN_PATH}"


def dns_txt_record_name(domain: str) -> str:
    """A dedicated `_gridkeep-verification.` subdomain, not a TXT record on
    the domain's apex — the same pattern real DNS-based verification
    schemes (e.g. Google Search Console) use, so this never collides with
    a domain's existing TXT records (SPF, DKIM, etc.)."""
    return f"{DNS_TXT_RECORD_PREFIX}.{domain}"


async def add_domain(
    session: AsyncSession, *, tenant_id: uuid.UUID, domain: str
) -> TenantDomain:
    """`tenant_domains` has RLS restricting SELECT to the caller's own
    tenant (see the RLS migration's `_SIMPLE_TENANT_TABLES`), so this
    pre-check can only ever see a same-tenant duplicate — a domain already
    claimed by a *different* tenant is invisible here and is instead
    caught by the table's global unique constraint on `domain` when the
    insert below hits it."""
    normalized = domain.strip().lower()
    existing = (
        await session.execute(select(TenantDomain).where(TenantDomain.domain == normalized))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("This domain has already been added to your workspace.")

    record = TenantDomain(
        tenant_id=tenant_id,
        domain=normalized,
        is_verified=False,
        verification_method=None,
        verification_token=generate_opaque_token(num_bytes=16),
        verified_at=None,
    )
    session.add(record)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise ConflictError("This domain is already claimed by another workspace.") from None
    return record


async def list_domains(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[TenantDomain]:
    return list(
        (
            await session.execute(
                select(TenantDomain)
                .where(TenantDomain.tenant_id == tenant_id)
                .order_by(TenantDomain.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def get_domain_or_404(
    session: AsyncSession, *, tenant_id: uuid.UUID, domain_id: uuid.UUID
) -> TenantDomain:
    record = (
        await session.execute(
            select(TenantDomain).where(TenantDomain.id == domain_id, TenantDomain.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if record is None:
        raise NotFoundError("Domain not found.")
    return record


async def remove_domain(session: AsyncSession, *, tenant_id: uuid.UUID, domain_id: uuid.UUID) -> None:
    record = await get_domain_or_404(session, tenant_id=tenant_id, domain_id=domain_id)
    await session.delete(record)
    await session.flush()


async def _verify_via_http_file(record: TenantDomain, *, scheme: str) -> tuple[bool, str]:
    """Makes a real outbound HTTP request to the domain's well-known path
    and checks the response body contains this record's own verification
    token."""
    url = verification_file_url(record.domain, scheme=scheme)
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        return False, f"Could not reach {url}: {exc}"

    if response.status_code != 200:
        return False, f"{url} returned HTTP {response.status_code}, expected 200."
    if record.verification_token not in response.text:
        return False, f"{url} did not contain the expected verification token."
    return True, "Domain ownership verified via HTTP file."


async def _verify_via_dns_txt(
    record: TenantDomain, *, resolver: dns.asyncresolver.Resolver | None = None
) -> tuple[bool, str]:
    """Makes a real DNS TXT query (dnspython's async resolver performs the
    actual protocol exchange, not a simulated one) and checks that at
    least one returned TXT record contains this record's own verification
    token. `resolver` lets tests point at a real local DNS server instead
    of the system-configured one; the API route never overrides it, so
    production traffic always uses the real configured resolver."""
    name = dns_txt_record_name(record.domain)
    resolver = resolver or dns.asyncresolver.get_default_resolver()
    try:
        answers = await resolver.resolve(name, "TXT", lifetime=_DNS_TIMEOUT_SECONDS)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return False, f"No TXT record found at {name}."
    except dns.exception.DNSException as exc:
        return False, f"Could not query {name}: {exc}"

    for rdata in answers:
        # A TXT record's value is one or more quoted byte-strings; dnspython
        # exposes them as `.strings`, concatenated to form the full value —
        # the same convention `dig` and every DNS TXT verification scheme uses.
        value = b"".join(rdata.strings).decode("utf-8", errors="replace")
        if record.verification_token in value:
            return True, "Domain ownership verified via DNS TXT record."
    return False, f"{name} did not contain the expected verification token."


async def verify_domain(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    domain_id: uuid.UUID,
    method: str = _HTTP_VERIFICATION_METHOD,
    scheme: str = "https",
    resolver: dns.asyncresolver.Resolver | None = None,
) -> tuple[TenantDomain, bool, str]:
    """Dispatches to whichever verification method the caller chose.
    `scheme`/`resolver` are the two methods' respective test-only escape
    hatches — tests point `scheme` at `http` for a local HTTP server, or
    pass a `resolver` pointed at a local DNS server; the API route never
    overrides either, so production traffic always checks the real thing."""
    if method not in VERIFICATION_METHODS:
        raise ValidationAppError(f"Unknown verification method '{method}'.")
    record = await get_domain_or_404(session, tenant_id=tenant_id, domain_id=domain_id)
    if record.verification_token is None:
        raise ValidationAppError("This domain has no verification token to check against.")

    if method == _DNS_VERIFICATION_METHOD:
        verified, message = await _verify_via_dns_txt(record, resolver=resolver)
    else:
        verified, message = await _verify_via_http_file(record, scheme=scheme)

    if not verified:
        return record, False, message

    record.is_verified = True
    record.verification_method = method
    record.verified_at = datetime.now(UTC)
    await session.flush()
    return record, True, message
