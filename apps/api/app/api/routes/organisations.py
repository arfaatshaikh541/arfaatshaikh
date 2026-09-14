from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from app.api.dependencies.auth import DbSession, get_current_user, require_csrf
from app.api.dependencies.tenancy import TenantContext, require_permission
from app.models.identity import Session, User
from app.models.tenancy import Membership, Organisation
from app.schemas.organisations import MembershipView, OrganisationCreate, OrganisationView
from app.services.organisations import OrganisationService

router = APIRouter(prefix="/organisations", tags=["organisations"])


@router.post("", response_model=OrganisationView, status_code=201)
async def create_organisation(
    payload: OrganisationCreate,
    request: Request,
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    _: Annotated[Session, Depends(require_csrf)],
) -> Organisation:
    organisation = await OrganisationService(db).create(user, payload.name, payload.slug, request.headers.get("X-Request-ID"))
    await db.commit()
    return organisation


@router.get("", response_model=list[OrganisationView])
async def list_organisations(db: DbSession, user: Annotated[User, Depends(get_current_user)]) -> list[Organisation]:
    return await OrganisationService(db).list_for_user(user.id)


@router.get("/{organisation_id}/members", response_model=list[MembershipView])
async def list_members(
    organisation_id: UUID,
    db: DbSession,
    context: Annotated[TenantContext, Depends(require_permission("members.view"))],
) -> list[Membership]:
    if organisation_id != context.organisation_id:
        from app.core.errors import ApplicationError
        raise ApplicationError("organisation_mismatch", "Path and tenant context do not match.", 400)
    result = await db.scalars(select(Membership).where(Membership.organisation_id == organisation_id).order_by(Membership.created_at))
    return list(result)
