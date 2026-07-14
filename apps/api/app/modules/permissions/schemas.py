import uuid

from pydantic import BaseModel, Field


class RoleSummary(BaseModel):
    id: uuid.UUID
    name: str
    is_system: bool
    permission_codes: list[str]


class CreateRoleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    permission_codes: list[str] = Field(default_factory=list)


class UpdateRolePermissionsRequest(BaseModel):
    permission_codes: list[str]
