import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    full_name: str = Field(min_length=1, max_length=200)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if v.lower() == v or v.upper() == v or not any(c.isdigit() for c in v):
            raise ValueError(
                "Password must be at least 12 characters and include upper, lower, and numeric characters."
            )
        return v


class RegisterResponse(BaseModel):
    id: uuid.UUID
    email: str
    email_verified: bool


class VerifyEmailRequest(BaseModel):
    token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    email_verified: bool
    mfa_enabled: bool


class PasswordResetRequestPayload(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=12, max_length=256)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if v.lower() == v or v.upper() == v or not any(c.isdigit() for c in v):
            raise ValueError(
                "Password must be at least 12 characters and include upper, lower, and numeric characters."
            )
        return v


class MembershipSummary(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    tenant_status: str
    role_name: str


class SessionInfoResponse(BaseModel):
    user: UserResponse
    active_tenant_id: uuid.UUID | None
    memberships: list[MembershipSummary]
