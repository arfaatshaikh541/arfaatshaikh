"""Test-only helpers. Where a token is deliberately never returned over
HTTP (invitation/reset/verification tokens — see modules/identity and
modules/permissions), tests reach into the service layer directly to
obtain the raw token rather than parsing it out of the real dispatched
email (see the `sent_emails` fixture in conftest.py for tests that do
want to assert on the email itself)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.identity import service as identity_service
from modules.identity.models import User


async def get_user_by_email(db: AsyncSession, email: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one()


async def verify_user_email(db: AsyncSession, user: User) -> None:
    token = await identity_service.issue_email_verification_token(db, user)
    await identity_service.verify_email(db, token)
    await db.commit()


async def onboard_verified_owner(
    client, db: AsyncSession, *, org_name: str, full_name: str, email: str, password: str
) -> dict:
    resp = await client.post(
        "/api/tenancy/onboarding",
        json={
            "organisation_name": org_name,
            "full_name": full_name,
            "email": email,
            "password": password,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    user = await get_user_by_email(db, email)
    await verify_user_email(db, user)
    return body


async def login(client, email: str, password: str):
    return await client.post("/api/auth/login", json={"email": email, "password": password})


async def invite_and_accept_member(
    client,
    db: AsyncSession,
    *,
    tenant_id: str,
    inviter_csrf_token: str,
    email: str,
    full_name: str,
    password: str,
    role_name: str,
) -> dict:
    """Invites a second member with a specific tenant role and accepts on
    their behalf — the invitation token is never returned over HTTP (it is
    genuinely emailed, see `core/email.py`), so this reaches into the
    service layer to re-issue a known raw token rather than parsing it out
    of the dispatched email. Does not log the inviter out; the caller
    decides when to switch sessions."""
    import uuid

    from core.security import generate_opaque_token, hash_token
    from db.session import AsyncSessionLocal, set_tenant_context
    from modules.permissions.models import Invitation

    invite_resp = await client.post(
        "/api/users/invitations",
        json={"email": email, "role_name": role_name},
        headers={"X-CSRF-Token": inviter_csrf_token},
    )
    assert invite_resp.status_code == 200, invite_resp.text

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, uuid.UUID(tenant_id))
        invitation = (
            await session.execute(select(Invitation).where(Invitation.email == email))
        ).scalar_one()
        raw_token = generate_opaque_token()
        invitation.token_hash = hash_token(raw_token)
        await session.commit()

    accept_resp = await client.post(
        "/api/auth/accept-invitation",
        json={"token": raw_token, "full_name": full_name, "password": password},
    )
    assert accept_resp.status_code == 200, accept_resp.text
    return accept_resp.json()
