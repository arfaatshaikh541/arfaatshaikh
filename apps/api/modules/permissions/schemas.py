from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_platform_role: bool


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    module: str
    description: str


class MembershipRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    role_name: str
    status: str


class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role_name: str = Field(min_length=2, max_length=80)


class InvitationRead(BaseModel):
    id: uuid.UUID
    email: str
    role_name: str
    expires_at: str
    accepted: bool
