from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import generate_opaque_token, hash_opaque_token, hash_password
from app.db.base import utcnow
from app.models.invitation import Invitation
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.invitation import InvitationRepository
from app.repositories.membership import MembershipRepository
from app.repositories.role import RoleRepository
from app.repositories.tenant import TenantRepository
from app.repositories.user import UserRepository
from app.services.email_service import send_invitation_email
from app.services.errors import ConflictError, NotFoundError, ValidationError


class InvitationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.invitations = InvitationRepository(db)
        self.memberships = MembershipRepository(db)
        self.roles = RoleRepository(db)
        self.tenants = TenantRepository(db)
        self.users = UserRepository(db)

    def create(
        self, *, tenant: Tenant, email: str, role_id: uuid.UUID, invited_by_user_id: uuid.UUID
    ) -> Invitation:
        role = self.roles.get_by_id_for_tenant(tenant.id, role_id)
        if role is None:
            raise ValidationError("Role does not belong to this tenant.")

        existing_user = self.users.get_by_email(email)
        if existing_user is not None:
            existing_membership = self.memberships.get_for_user_and_tenant(
                existing_user.id, tenant.id
            )
            if existing_membership is not None:
                raise ConflictError("This person is already a member of this tenant.")

        token = generate_opaque_token()
        invitation = self.invitations.create(
            tenant_id=tenant.id,
            email=email,
            role_id=role_id,
            invited_by_user_id=invited_by_user_id,
            token_hash=hash_opaque_token(token),
            expires_at=utcnow() + timedelta(days=7),
        )
        accept_url = f"{self.settings.web_base_url}/accept-invitation?token={token}"
        send_invitation_email(to=email, tenant_name=tenant.name, accept_url=accept_url)
        return invitation

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[Invitation]:
        return self.invitations.list_for_tenant(tenant_id)

    def revoke(self, tenant_id: uuid.UUID, invitation_id: uuid.UUID) -> Invitation:
        invitation = self.invitations.get_by_id_for_tenant(tenant_id, invitation_id)
        if invitation is None:
            raise NotFoundError("Invitation not found.")
        if invitation.status != "pending":
            raise ValidationError("Only pending invitations can be revoked.")
        return self.invitations.mark_status(invitation, "revoked")

    def _get_valid_invitation(self, token: str) -> Invitation:
        invitation = self.invitations.get_by_token_hash(hash_opaque_token(token))
        if invitation is None or invitation.status != "pending":
            raise ValidationError("Invalid or already-used invitation link.")
        if invitation.expires_at < utcnow():
            self.invitations.mark_status(invitation, "expired")
            raise ValidationError("This invitation has expired.")
        return invitation

    def accept_for_new_user(
        self, *, token: str, first_name: str, last_name: str, password: str
    ) -> tuple[User, Invitation]:
        invitation = self._get_valid_invitation(token)
        existing_user = self.users.get_by_email(invitation.email)
        if existing_user is not None:
            raise ConflictError(
                "An account already exists for this email. Please log in to accept the invitation."
            )
        user = self.users.create(
            email=invitation.email,
            hashed_password=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            email_verified=True,  # clicking the emailed invitation link proves ownership
        )
        self.memberships.create(
            tenant_id=invitation.tenant_id, user_id=user.id, role_id=invitation.role_id
        )
        self.invitations.mark_status(invitation, "accepted")
        return user, invitation

    def accept_for_existing_user(self, *, token: str, user: User) -> Invitation:
        invitation = self._get_valid_invitation(token)
        if invitation.email != user.email:
            raise ValidationError("This invitation was sent to a different email address.")
        if self.memberships.get_for_user_and_tenant(user.id, invitation.tenant_id) is not None:
            raise ConflictError("You are already a member of this tenant.")
        self.memberships.create(
            tenant_id=invitation.tenant_id, user_id=user.id, role_id=invitation.role_id
        )
        self.invitations.mark_status(invitation, "accepted")
        return invitation
