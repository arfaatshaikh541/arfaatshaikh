from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AuthenticationError, ConflictError, NotFoundError
from core.security import generate_opaque_token, hash_password, hash_token
from db.session import set_tenant_context
from modules.identity.models import User
from modules.permissions.models import Invitation, Membership, Role

INVITATION_TTL = timedelta(days=7)


def _now() -> datetime:
    return datetime.now(UTC)


async def create_invitation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    invited_by_user_id: uuid.UUID,
    email: str,
    role_name: str,
) -> tuple[Invitation, str]:
    role = (
        await session.execute(
            select(Role).where(Role.name == role_name, Role.is_platform_role.is_(False))
        )
    ).scalar_one_or_none()
    if role is None:
        raise NotFoundError(f"Unknown role '{role_name}'.")

    existing_membership = (
        await session.execute(
            select(Membership)
            .join(User, User.id == Membership.user_id)
            .where(Membership.tenant_id == tenant_id, User.email == email, Membership.status == "active")
        )
    ).scalar_one_or_none()
    if existing_membership is not None:
        raise ConflictError("This person is already a member of this workspace.")

    raw_token = generate_opaque_token()
    invitation = Invitation(
        tenant_id=tenant_id,
        email=email,
        role_id=role.id,
        invited_by_user_id=invited_by_user_id,
        token_hash=hash_token(raw_token),
        expires_at=_now() + INVITATION_TTL,
    )
    session.add(invitation)
    await session.flush()
    return invitation, raw_token


async def accept_invitation(
    session: AsyncSession, *, raw_token: str, full_name: str, password: str
) -> tuple[User, Membership]:
    token_hash = hash_token(raw_token)
    invitation = (
        await session.execute(select(Invitation).where(Invitation.token_hash == token_hash))
    ).scalar_one_or_none()

    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.revoked_at is not None
        or invitation.expires_at <= _now()
    ):
        raise AuthenticationError("This invitation link is invalid or has expired.")

    await set_tenant_context(session, invitation.tenant_id)

    user = (
        await session.execute(select(User).where(User.email == invitation.email))
    ).scalar_one_or_none()

    if user is None:
        user = User(
            email=invitation.email,
            password_hash=hash_password(password),
            full_name=full_name,
            email_verified=True,  # invitation to this address is itself proof of ownership
            email_verified_at=_now(),
        )
        session.add(user)
        await session.flush()

    existing_membership = (
        await session.execute(
            select(Membership).where(
                Membership.tenant_id == invitation.tenant_id, Membership.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if existing_membership is not None and existing_membership.status == "active":
        raise ConflictError("You're already a member of this workspace.")

    if existing_membership is not None:
        existing_membership.status = "active"
        existing_membership.role_id = invitation.role_id
        membership = existing_membership
    else:
        membership = Membership(
            tenant_id=invitation.tenant_id,
            user_id=user.id,
            role_id=invitation.role_id,
            status="active",
        )
        session.add(membership)

    invitation.accepted_at = _now()
    await session.flush()
    return user, membership


async def list_tenant_roles(session: AsyncSession) -> list[Role]:
    result = await session.execute(select(Role).where(Role.is_platform_role.is_(False)))
    return list(result.scalars().all())
