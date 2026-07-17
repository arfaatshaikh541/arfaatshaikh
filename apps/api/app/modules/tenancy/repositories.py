import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenancy.models import Invitation, Membership, Tenant, TenantSettings


async def get_active_memberships_for_user(
    session: AsyncSession, user_id: uuid.UUID
) -> list[Membership]:
    stmt = select(Membership).where(Membership.user_id == user_id, Membership.status == "active")
    return list((await session.execute(stmt)).scalars().all())


async def get_membership(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> Membership | None:
    stmt = select(Membership).where(
        Membership.tenant_id == tenant_id, Membership.user_id == user_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_tenant_by_id(session: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_tenant_by_slug(session: AsyncSession, slug: str) -> Tenant | None:
    stmt = select(Tenant).where(Tenant.slug == slug)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_tenant(
    session: AsyncSession, *, name: str, slug: str, status: str = "trial"
) -> Tenant:
    tenant = Tenant(name=name, slug=slug, status=status)
    session.add(tenant)
    await session.flush()
    return tenant


async def create_tenant_settings(session: AsyncSession, *, tenant_id: uuid.UUID) -> TenantSettings:
    settings_row = TenantSettings(tenant_id=tenant_id)
    session.add(settings_row)
    await session.flush()
    return settings_row


async def create_membership(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    status: str = "active",
) -> Membership:
    membership = Membership(tenant_id=tenant_id, user_id=user_id, role_id=role_id, status=status)
    session.add(membership)
    await session.flush()
    return membership


async def create_invitation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    email: str,
    role_id: uuid.UUID,
    invited_by_user_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
) -> Invitation:
    invitation = Invitation(
        tenant_id=tenant_id,
        email=email.lower(),
        role_id=role_id,
        invited_by_user_id=invited_by_user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(invitation)
    await session.flush()
    return invitation


async def get_invitation_by_token_hash(session: AsyncSession, token_hash: str) -> Invitation | None:
    stmt = select(Invitation).where(Invitation.token_hash == token_hash)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_invitations_for_tenant(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[Invitation]:
    stmt = (
        select(Invitation)
        .where(Invitation.tenant_id == tenant_id)
        .order_by(Invitation.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def count_active_memberships(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    stmt = select(Membership).where(
        Membership.tenant_id == tenant_id, Membership.status == "active"
    )
    return len((await session.execute(stmt)).scalars().all())


async def count_pending_invitations(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    stmt = select(Invitation).where(
        Invitation.tenant_id == tenant_id, Invitation.status == "pending"
    )
    return len((await session.execute(stmt)).scalars().all())
