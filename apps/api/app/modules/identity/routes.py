from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import clear_session_cookie, set_session_cookie
from app.core.db import get_db
from app.core.rate_limit import enforce_rate_limit
from app.dependencies import get_current_session, get_current_user
from app.modules.identity import services
from app.modules.identity.models import Session as SessionModel
from app.modules.identity.models import User
from app.modules.identity.schemas import (
    LoginRequest,
    MembershipSummary,
    PasswordResetConfirmRequest,
    PasswordResetRequestPayload,
    RegisterRequest,
    RegisterResponse,
    SessionInfoResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.modules.permissions.models import Role
from app.modules.tenancy.models import Tenant
from app.modules.tenancy.services import list_my_memberships

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(
        f"register:{request.client.host if request.client else 'unknown'}", 10, 3600
    )
    user = await services.register_user(
        db, email=payload.email, password=payload.password, full_name=payload.full_name
    )
    return RegisterResponse(id=user.id, email=user.email, email_verified=user.email_verified)


@router.post("/verify-email", response_model=UserResponse)
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    user = await services.verify_email(db, raw_token=payload.token)
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        email_verified=user.email_verified,
        mfa_enabled=user.mfa_enabled,
    )


@router.post("/login", response_model=UserResponse)
async def login(
    payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    client_ip = request.client.host if request.client else "unknown"
    await enforce_rate_limit(f"login:ip:{client_ip}", 5, 60)
    await enforce_rate_limit(f"login:account:{payload.email.lower()}", 20, 3600)

    user, session_row, raw_token = await services.login(
        db,
        email=payload.email,
        password=payload.password,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    set_session_cookie(response, raw_token)
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        email_verified=user.email_verified,
        mfa_enabled=user.mfa_enabled,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session_row: SessionModel = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    await services.logout(db, session_row=session_row)
    clear_session_cookie(response)


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    payload: PasswordResetRequestPayload, request: Request, db: AsyncSession = Depends(get_db)
):
    client_ip = request.client.host if request.client else "unknown"
    await enforce_rate_limit(f"password_reset:ip:{client_ip}", 5, 3600)
    await services.request_password_reset(db, email=payload.email)
    return {"message": "If an account exists for this email, a reset link has been sent."}


@router.post("/password-reset/confirm", response_model=UserResponse)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest, db: AsyncSession = Depends(get_db)
):
    user = await services.confirm_password_reset(
        db, raw_token=payload.token, new_password=payload.new_password
    )
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        email_verified=user.email_verified,
        mfa_enabled=user.mfa_enabled,
    )


@router.get("/session", response_model=SessionInfoResponse)
async def get_session_info(
    session_row: SessionModel = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    memberships = await list_my_memberships(db, user.id)
    summaries: list[MembershipSummary] = []
    for m in memberships:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.id == m.tenant_id))
        ).scalar_one_or_none()
        if tenant is None:
            continue
        role = (await db.execute(select(Role).where(Role.id == m.role_id))).scalar_one_or_none()
        summaries.append(
            MembershipSummary(
                tenant_id=tenant.id,
                tenant_name=tenant.name,
                tenant_slug=tenant.slug,
                tenant_status=tenant.status,
                role_name=role.name if role else "unknown",
            )
        )

    return SessionInfoResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            email_verified=user.email_verified,
            mfa_enabled=user.mfa_enabled,
        ),
        active_tenant_id=session_row.active_tenant_id,
        memberships=summaries,
    )
