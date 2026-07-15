import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator


def _password_strength(value: str) -> str:
    if value.isalpha() or value.isdigit():
        raise ValueError("Password must contain a mix of letters and numbers or symbols.")
    return value


class PortalLoginRequest(BaseModel):
    tenant_slug: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class PortalAcceptInvitationRequest(BaseModel):
    token: str
    password: str = Field(min_length=10, max_length=200)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return _password_strength(value)


class PortalForgotPasswordRequest(BaseModel):
    tenant_slug: str = Field(min_length=1, max_length=100)
    email: EmailStr


class PortalResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=10, max_length=200)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return _password_strength(value)


class InviteToPortalRequest(BaseModel):
    lead_id: uuid.UUID


class CurrentPortalAccountResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    lead_id: uuid.UUID
    email: str
    first_name: str
    last_name: str
