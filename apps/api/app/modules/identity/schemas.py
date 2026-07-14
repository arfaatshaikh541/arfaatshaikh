import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class AcceptInvitationRequest(BaseModel):
    token: str
    password: str = Field(min_length=10, max_length=200)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if value.isalpha() or value.isdigit():
            raise ValueError("Password must contain a mix of letters and numbers or symbols.")
        return value


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=10, max_length=200)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if value.isalpha() or value.isdigit():
            raise ValueError("Password must contain a mix of letters and numbers or symbols.")
        return value


class VerifyEmailRequest(BaseModel):
    token: str


class SwitchTenantRequest(BaseModel):
    tenant_id: uuid.UUID


class MembershipSummary(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    role_name: str

    model_config = {"from_attributes": True}


class CurrentUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    email_verified: bool
    is_platform_admin: bool
    active_tenant_id: uuid.UUID | None
    memberships: list[MembershipSummary]

    model_config = {"from_attributes": True}
