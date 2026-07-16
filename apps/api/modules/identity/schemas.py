from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class MembershipSummary(BaseModel):
    membership_id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    tenant_status: str
    role_name: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    email_verified: bool
    mfa_enabled: bool
    is_platform_user: bool
    platform_role_name: str | None = None


class LoginResponse(BaseModel):
    user: UserRead
    memberships: list[MembershipSummary]
    active_membership_id: uuid.UUID | None
    csrf_token: str


class MfaRequiredResponse(BaseModel):
    """Returned by `/api/auth/login` in place of `LoginResponse` when the
    password check succeeded but the account has MFA enabled — no
    session exists yet, only this short-lived challenge token."""

    mfa_required: bool = True
    mfa_challenge_token: str


class MeResponse(BaseModel):
    user: UserRead
    memberships: list[MembershipSummary]
    active_membership_id: uuid.UUID | None


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=12, max_length=200)


class AcceptInvitationRequest(BaseModel):
    token: str
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=12, max_length=200)


class TenantSwitchRequest(BaseModel):
    membership_id: uuid.UUID


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role_name: str


class MfaEnrollResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class MfaDisableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class MfaVerifyLoginRequest(BaseModel):
    mfa_challenge_token: str
    code: str = Field(min_length=6, max_length=6)


class StepUpRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class StepUpResponse(BaseModel):
    status: str
    step_up_expires_at: datetime
