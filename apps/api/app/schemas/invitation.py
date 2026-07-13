import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class InvitationCreate(BaseModel):
    email: EmailStr
    role_id: uuid.UUID


class InvitationOut(ORMModel):
    id: uuid.UUID
    email: str
    role_id: uuid.UUID
    status: str
    expires_at: datetime
    created_at: datetime


class InvitationAcceptRequest(BaseModel):
    token: str
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=10, max_length=200)
