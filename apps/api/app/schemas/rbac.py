import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PermissionOut(ORMModel):
    code: str
    description: str


class RoleOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    is_system: bool
    permissions: list[PermissionOut] = Field(default_factory=list)


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    permission_codes: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    permission_codes: list[str] | None = None
