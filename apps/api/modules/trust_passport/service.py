"""Trust Passport settings + the public, unauthenticated passport lookup.

The public lookup is the first place in this codebase that returns
tenant data with no session cookie and no `TenantContext` at all: it
resolves a tenant purely from a public `public_slug`, via the widened
`trust_passport_settings_select` RLS policy (see the Milestone 9 RLS
migration), then explicitly narrows every subsequent query in the same
request to that one resolved tenant via `set_tenant_context` — the same
mechanism `get_tenant_context` uses after resolving a tenant from a
session cookie, just resolved from a slug instead.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import NotFoundError
from core.security import generate_opaque_token
from db.session import set_tenant_context
from modules.compliance import service as compliance_service
from modules.trust_passport.models import TrustPassportSettings

# Coarse, non-numeric labels only — a public page never shows a raw
# compliance percentage, deliberately: "62% compliant" reads as an
# admission of failure to an outside visitor in a way "In Progress"
# doesn't, and the internal /compliance page already has the real number
# for anyone with compliance.view.
_STRONG_THRESHOLD = 80
_IN_PROGRESS_THRESHOLD = 50


def _status_label(score: int) -> str:
    if score >= _STRONG_THRESHOLD:
        return "Strong"
    if score >= _IN_PROGRESS_THRESHOLD:
        return "In Progress"
    return "Building"


async def get_settings(session: AsyncSession, *, tenant_id: uuid.UUID) -> TrustPassportSettings | None:
    return (
        await session.execute(
            select(TrustPassportSettings).where(TrustPassportSettings.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()


async def update_settings(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    is_published: bool,
    headline: str,
    description: str,
    show_compliance_frameworks: bool,
    actor_user_id: uuid.UUID,
) -> TrustPassportSettings:
    settings = await get_settings(session, tenant_id=tenant_id)
    if settings is None:
        settings = TrustPassportSettings(tenant_id=tenant_id)
        session.add(settings)
    settings.is_published = is_published
    settings.headline = headline
    settings.description = description
    settings.show_compliance_frameworks = show_compliance_frameworks
    settings.updated_by_user_id = actor_user_id
    if is_published and not settings.public_slug:
        settings.public_slug = generate_opaque_token(num_bytes=16)
    await session.flush()
    return settings


async def regenerate_slug(
    session: AsyncSession, *, tenant_id: uuid.UUID, actor_user_id: uuid.UUID
) -> TrustPassportSettings:
    settings = await get_settings(session, tenant_id=tenant_id)
    if settings is None:
        raise NotFoundError("Trust passport has not been configured yet.")
    settings.public_slug = generate_opaque_token(num_bytes=16)
    settings.updated_by_user_id = actor_user_id
    await session.flush()
    return settings


async def get_public_passport(session: AsyncSession, *, slug: str) -> dict:
    settings = (
        await session.execute(
            select(TrustPassportSettings).where(
                TrustPassportSettings.public_slug == slug,
                TrustPassportSettings.is_published.is_(True),
            )
        )
    ).scalar_one_or_none()
    if settings is None:
        raise NotFoundError("Trust passport not found.")

    await set_tenant_context(session, settings.tenant_id)

    compliance_frameworks = None
    if settings.show_compliance_frameworks:
        summary = await compliance_service.get_compliance_summary(session, tenant_id=settings.tenant_id)
        compliance_frameworks = [
            {"name": f["name"], "status_label": _status_label(f["score"])} for f in summary["frameworks"]
        ]

    return {
        "headline": settings.headline,
        "description": settings.description,
        "generated_at": datetime.now(UTC),
        "compliance_frameworks": compliance_frameworks,
    }
