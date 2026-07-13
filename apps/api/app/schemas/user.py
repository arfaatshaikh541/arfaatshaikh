import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.schemas.rbac import RoleOut


class MembershipSummary(ORMModel):
    tenant_id: uuid.UUID
    tenant_slug: str
    tenant_name: str
    role: RoleOut
    status: str


class CurrentUserOut(ORMModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    is_platform_super_admin: bool
    email_verified: bool
    memberships: list[MembershipSummary]


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=200)


class UpdateProfileRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
