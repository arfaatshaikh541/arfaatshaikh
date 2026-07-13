from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.repositories.membership import MembershipRepository
from app.repositories.role import RoleRepository
from app.services.errors import NotFoundError, ValidationError


class MembershipService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.memberships = MembershipRepository(db)
        self.roles = RoleRepository(db)

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[Membership]:
        return self.memberships.list_for_tenant(tenant_id)

    def _get_or_404(self, tenant_id: uuid.UUID, membership_id: uuid.UUID) -> Membership:
        membership = self.memberships.get_by_id_for_tenant(tenant_id, membership_id)
        if membership is None:
            raise NotFoundError("Member not found.")
        return membership

    def _guard_last_owner(self, tenant_id: uuid.UUID, membership: Membership) -> None:
        owner_role = self.roles.get_by_slug_for_tenant(tenant_id, "owner")
        if owner_role is None or membership.role_id != owner_role.id:
            return
        remaining_owners = [
            m
            for m in self.memberships.list_for_tenant(tenant_id)
            if m.role_id == owner_role.id and m.status == "active" and m.id != membership.id
        ]
        if not remaining_owners:
            raise ValidationError("A tenant must always have at least one active Owner.")

    def update_role(
        self, tenant_id: uuid.UUID, membership_id: uuid.UUID, role_id: uuid.UUID
    ) -> Membership:
        membership = self._get_or_404(tenant_id, membership_id)
        role = self.roles.get_by_id_for_tenant(tenant_id, role_id)
        if role is None:
            raise ValidationError("Role does not belong to this tenant.")
        self._guard_last_owner(tenant_id, membership)
        return self.memberships.update_role(membership, role_id)

    def suspend(self, tenant_id: uuid.UUID, membership_id: uuid.UUID) -> Membership:
        membership = self._get_or_404(tenant_id, membership_id)
        self._guard_last_owner(tenant_id, membership)
        return self.memberships.update_status(membership, "suspended")

    def reactivate(self, tenant_id: uuid.UUID, membership_id: uuid.UUID) -> Membership:
        membership = self._get_or_404(tenant_id, membership_id)
        return self.memberships.update_status(membership, "active")
