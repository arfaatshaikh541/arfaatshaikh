import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str


class SwitchTenantRequest(BaseModel):
    tenant_id: uuid.UUID


class RoleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role_id: uuid.UUID


class InvitationResponse(BaseModel):
    id: uuid.UUID
    email: str
    role_id: uuid.UUID
    status: str
    expires_at: datetime


class AcceptInvitationRequest(BaseModel):
    token: str
