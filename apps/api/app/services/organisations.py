from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.core.security import utcnow
from app.models.tenancy import AuditEvent, Membership, Organisation, Permission, Role, RolePermission
from app.models.identity import User

DEFAULT_PERMISSIONS = {
    "organisation.view": "View organisation details",
    "organisation.manage": "Manage organisation settings",
    "members.view": "View organisation members",
    "members.manage": "Manage organisation members and roles",
    "audit.view": "View organisation audit history",
}


class OrganisationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, owner: User, name: str, slug: str, request_id: str | None = None) -> Organisation:
        if await self.session.scalar(select(Organisation.id).where(Organisation.slug == slug)):
            raise ApplicationError("organisation_slug_unavailable", "This organisation slug is unavailable.", 409)
        organisation = Organisation(name=name.strip(), slug=slug, status="active")
        self.session.add(organisation)
        await self.session.flush()

        permissions: dict[str, Permission] = {}
        for code, description in DEFAULT_PERMISSIONS.items():
            permission = await self.session.scalar(select(Permission).where(Permission.code == code))
            if permission is None:
                permission = Permission(code=code, description=description)
                self.session.add(permission)
                await self.session.flush()
            permissions[code] = permission

        owner_role = Role(organisation_id=organisation.id, name="Owner", description="Organisation owner", is_system=True)
        member_role = Role(organisation_id=organisation.id, name="Member", description="Standard organisation member", is_system=True)
        self.session.add_all([owner_role, member_role])
        await self.session.flush()
        for permission in permissions.values():
            self.session.add(RolePermission(role_id=owner_role.id, permission_id=permission.id))
        self.session.add(RolePermission(role_id=member_role.id, permission_id=permissions["organisation.view"].id))
        membership = Membership(organisation_id=organisation.id, user_id=owner.id, role_id=owner_role.id, status="active")
        self.session.add(membership)
        self.session.add(AuditEvent(
            organisation_id=organisation.id,
            actor_user_id=owner.id,
            action="organisation.created",
            target_type="organisation",
            target_id=organisation.id,
            request_id=request_id,
            metadata_json=json.dumps({"slug": slug}, separators=(",", ":")),
            created_at=utcnow(),
        ))
        await self.session.flush()
        return organisation

    async def list_for_user(self, user_id: UUID) -> list[Organisation]:
        rows = await self.session.scalars(
            select(Organisation)
            .join(Membership, Membership.organisation_id == Organisation.id)
            .where(Membership.user_id == user_id, Membership.status == "active", Organisation.status == "active")
            .order_by(Organisation.name)
        )
        return list(rows)

    async def get_membership(self, organisation_id: UUID, user_id: UUID) -> Membership | None:
        return await self.session.scalar(
            select(Membership).where(
                Membership.organisation_id == organisation_id,
                Membership.user_id == user_id,
                Membership.status == "active",
            )
        )

    async def permissions_for_membership(self, membership: Membership) -> set[str]:
        result = await self.session.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == membership.role_id)
        )
        return set(result)
