"""Test-only helpers. Where a token is deliberately never returned over
HTTP (invitation/reset/verification tokens — see modules/identity and
modules/permissions), tests reach into the service layer directly to
obtain the raw token, exactly as the (currently log-based, dev-only) email
adapter would have delivered it to a real inbox."""

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
