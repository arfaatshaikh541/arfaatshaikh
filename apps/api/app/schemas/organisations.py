from uuid import UUID
from pydantic import BaseModel, Field


class OrganisationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=80)


class OrganisationView(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str


class MembershipView(BaseModel):
    id: UUID
    organisation_id: UUID
    user_id: UUID
    role_id: UUID
    status: str


class MembershipRoleUpdate(BaseModel):
    role_id: UUID
