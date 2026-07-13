from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import MembershipContext, get_optional_current_user, require_permission
from app.api.routes.auth import set_auth_cookies
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.invitation import InvitationAcceptRequest, InvitationCreate, InvitationOut
from app.services.auth_service import AuthService
from app.services.errors import ConflictError
from app.services.invitation_service import InvitationService

tenant_router = APIRouter(prefix="/tenants/me/invitations", tags=["invitations"])
public_router = APIRouter(prefix="/invitations", tags=["invitations"])


@tenant_router.get("", response_model=list[InvitationOut])
def list_invitations(
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("users.manage")),
) -> list[InvitationOut]:
    invitations = InvitationService(db).list_for_tenant(ctx.tenant_id)
    return [InvitationOut.model_validate(i) for i in invitations]


@tenant_router.post("", response_model=InvitationOut, status_code=201)
def create_invitation(
    payload: InvitationCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("users.manage")),
) -> InvitationOut:
    invitation = InvitationService(db).create(
        tenant=ctx.tenant,
        email=payload.email,
        role_id=payload.role_id,
        invited_by_user_id=ctx.user.id,
    )
    db.commit()
    return InvitationOut.model_validate(invitation)


@tenant_router.delete("/{invitation_id}", response_model=MessageResponse)
def revoke_invitation(
    invitation_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("users.manage")),
) -> MessageResponse:
    InvitationService(db).revoke(ctx.tenant_id, invitation_id)
    db.commit()
    return MessageResponse(message="Invitation revoked.")


@public_router.post("/accept", response_model=MessageResponse)
def accept_invitation(
    payload: InvitationAcceptRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> MessageResponse:
    service = InvitationService(db)
    if current_user is not None:
        service.accept_for_existing_user(token=payload.token, user=current_user)
        db.commit()
        return MessageResponse(message="Invitation accepted.")

    try:
        user, _invitation = service.accept_for_new_user(
            token=payload.token,
            first_name=payload.first_name,
            last_name=payload.last_name,
            password=payload.password,
        )
    except ConflictError:
        raise

    db.commit()
    tokens = AuthService(db).login(
        email=user.email, password=payload.password, ip_address="invitation-accept", user_agent=None
    )
    db.commit()
    set_auth_cookies(response, tokens)
    return MessageResponse(message="Invitation accepted. You are now signed in.")
