from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Callable
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy import select

from app.api.dependencies.auth import DbSession, get_current_user
from app.core.errors import ApplicationError
from app.core.security import utcnow
from app.db.context import set_request_tenant_context
from app.models.identity import User
from app.models.tenancy import Membership, PlatformAdministrator, SupportAccessGrant
from app.services.organisations import OrganisationService


@dataclass(slots=True)
class TenantContext:
    organisation_id: UUID
    user: User
    membership: Membership | None
    permissions: frozenset[str]
    support_access: bool = False


async def get_tenant_context(
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    organisation_header: Annotated[str | None, Header(alias="X-Organisation-ID")] = None,
) -> TenantContext:
    if not organisation_header:
        raise ApplicationError("organisation_required", "X-Organisation-ID is required.", 400)
    try:
        organisation_id = UUID(organisation_header)
    except ValueError as exc:
        raise ApplicationError("invalid_organisation", "Organisation identifier is invalid.", 400) from exc

    service = OrganisationService(db)
    membership = await service.get_membership(organisation_id, user.id)
    if membership is not None:
        permissions = await service.permissions_for_membership(membership)
        await set_request_tenant_context(db, organisation_id)
        return TenantContext(organisation_id, user, membership, frozenset(permissions))

    is_admin = await db.scalar(select(PlatformAdministrator.id).where(
        PlatformAdministrator.user_id == user.id,
        PlatformAdministrator.active.is_(True),
    ))
    if is_admin:
        grant = await db.scalar(select(SupportAccessGrant.id).where(
            SupportAccessGrant.organisation_id == organisation_id,
            SupportAccessGrant.administrator_user_id == user.id,
            SupportAccessGrant.revoked_at.is_(None),
            SupportAccessGrant.expires_at > utcnow(),
        ))
        if grant:
            await set_request_tenant_context(db, organisation_id)
            return TenantContext(organisation_id, user, None, frozenset({"organisation.view", "members.view", "audit.view"}), True)

    raise ApplicationError("organisation_access_denied", "You do not have access to this organisation.", 403)


def require_permission(code: str) -> Callable:
    async def dependency(context: Annotated[TenantContext, Depends(get_tenant_context)]) -> TenantContext:
        if code not in context.permissions:
            raise ApplicationError("permission_denied", "You do not have permission to perform this action.", 403)
        return context
    return dependency
