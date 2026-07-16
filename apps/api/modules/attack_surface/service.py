"""Domain ownership verification — the attack-surface perimeter a tenant
claims as their own. See `modules.tenancy.models.TenantDomain`'s
docstring for why this is HTTP-file based rather than the DNS TXT
originally planned: a real ownership check has to actually check
something, unlike a mock connector's demo data, so this makes a real
outbound HTTP request rather than simulating a result.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import ConflictError, NotFoundError, ValidationAppError
from core.security import generate_opaque_token
from modules.tenancy.models import TenantDomain

WELL_KNOWN_PATH = "/.well-known/gridkeep-verification.txt"
_VERIFICATION_METHOD = "http_file"
_REQUEST_TIMEOUT_SECONDS = 10.0


def verification_file_url(domain: str, *, scheme: str = "https") -> str:
    return f"{scheme}://{domain}{WELL_KNOWN_PATH}"


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


async def verify_domain(
    session: AsyncSession, *, tenant_id: uuid.UUID, domain_id: uuid.UUID, scheme: str = "https"
) -> tuple[TenantDomain, bool, str]:
    """Makes a real outbound HTTP request to the domain's well-known path
    and checks the response body contains this record's own verification
    token. `scheme` defaults to "https" for real domains; tests pointing
    at a local HTTP server override it — never exposed via the API
    route, which always verifies real domains over HTTPS."""
    record = await get_domain_or_404(session, tenant_id=tenant_id, domain_id=domain_id)
    if record.verification_token is None:
        raise ValidationAppError("This domain has no verification token to check against.")

    url = verification_file_url(record.domain, scheme=scheme)
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        return record, False, f"Could not reach {url}: {exc}"

    if response.status_code != 200:
        return record, False, f"{url} returned HTTP {response.status_code}, expected 200."
    if record.verification_token not in response.text:
        return record, False, f"{url} did not contain the expected verification token."

    record.is_verified = True
    record.verification_method = _VERIFICATION_METHOD
    record.verified_at = datetime.now(UTC)
    await session.flush()
    return record, True, "Domain ownership verified."
