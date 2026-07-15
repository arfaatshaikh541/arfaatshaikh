import uuid

from fastapi import APIRouter, Depends, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import PortalContext, TenantContext
from app.core.db import get_db
from app.core.errors import NotFoundError, RateLimitedError
from app.core.rate_limit import is_rate_limited, reset_rate_limit
from app.dependencies.entitlements import require_module
from app.dependencies.permissions import require_permission
from app.dependencies.portal_auth import get_portal_auth_context
from app.modules.portal import service as portal_service
from app.modules.portal.repository import PortalAccountRepository
from app.modules.portal.schemas import (
    CurrentPortalAccountResponse,
    InviteToPortalRequest,
    PortalAcceptInvitationRequest,
    PortalForgotPasswordRequest,
    PortalLoginRequest,
    PortalResetPasswordRequest,
)
from app.modules.proposals.schemas import AcceptProposalRequest, RejectProposalRequest

auth_router = APIRouter(prefix="/portal/auth", tags=["portal-auth"])
router = APIRouter(prefix="/portal", tags=["portal-content"])
staff_router = APIRouter(prefix="/tenant/portal-accounts", tags=["portal-accounts"])
settings = get_settings()

PORTAL_LOGIN_MAX_ATTEMPTS = 8
PORTAL_LOGIN_WINDOW_SECONDS = 15 * 60


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_portal_session_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.portal_session_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.portal_session_absolute_ttl_hours * 3600,
        path="/",
    )


def _clear_portal_session_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.portal_session_cookie_name, path="/")


def _current_account_response(db: Session, ctx: PortalContext) -> CurrentPortalAccountResponse:
    from app.modules.leads.repository import LeadRepository
    from app.modules.tenancy import service as tenancy_service

    account = PortalAccountRepository(db).get(ctx.tenant_id, ctx.portal_account_id)
    lead = LeadRepository(db).get(ctx.tenant_id, ctx.lead_id)
    tenant = tenancy_service.get_tenant_or_404(db, ctx.tenant_id)
    return CurrentPortalAccountResponse(
        id=account.id, tenant_id=ctx.tenant_id, tenant_name=tenant.name, lead_id=ctx.lead_id, email=account.email,
        first_name=lead.first_name if lead else "", last_name=lead.last_name if lead else "",
    )


def _assert_belongs_to_lead(resource_lead_id: uuid.UUID, ctx: PortalContext) -> None:
    """Every portal route touching a specific resource must call this
    before returning or acting on it — a portal account must only ever
    see its own lead's data, never another lead's in the same tenant."""
    if resource_lead_id != ctx.lead_id:
        raise NotFoundError("Not found.")


# --- Auth ------------------------------------------------------------

@auth_router.post("/login", response_model=CurrentPortalAccountResponse)
def login(payload: PortalLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> CurrentPortalAccountResponse:
    ip_address = _client_ip(request)
    throttle_key = f"throttle:portal_login:{payload.tenant_slug}:{payload.email.lower()}:{ip_address}"
    limited, retry_after = is_rate_limited(throttle_key, max_attempts=PORTAL_LOGIN_MAX_ATTEMPTS, window_seconds=PORTAL_LOGIN_WINDOW_SECONDS)
    if limited:
        raise RateLimitedError(f"Too many login attempts. Try again in {retry_after} seconds.", code="login_rate_limited")

    account, tenant = portal_service.authenticate_portal(
        db, tenant_slug=payload.tenant_slug, email=payload.email, password=payload.password, ip_address=ip_address
    )
    reset_rate_limit(throttle_key)

    session, raw_token = portal_service.create_portal_session(
        db, account=account, ip_address=ip_address, user_agent=request.headers.get("user-agent")
    )
    _set_portal_session_cookie(response, raw_token)

    ctx = PortalContext(tenant_id=tenant.id, tenant_slug=tenant.slug, lead_id=account.lead_id, portal_account_id=account.id, portal_session_id=session.id)
    return _current_account_response(db, ctx)


@auth_router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    raw_token = request.cookies.get(settings.portal_session_cookie_name)
    if raw_token:
        session = portal_service.get_portal_session_by_raw_token(db, raw_token)
        if session:
            portal_service.revoke_portal_session(db, session)
    _clear_portal_session_cookie(response)


@auth_router.get("/me", response_model=CurrentPortalAccountResponse)
def get_me(ctx: PortalContext = Depends(get_portal_auth_context), db: Session = Depends(get_db)) -> CurrentPortalAccountResponse:
    return _current_account_response(db, ctx)


@auth_router.post("/accept-invitation", response_model=CurrentPortalAccountResponse, status_code=201)
def accept_invitation(payload: PortalAcceptInvitationRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> CurrentPortalAccountResponse:
    account, invitation = portal_service.accept_portal_invitation(db, token=payload.token, password=payload.password)
    session, raw_token = portal_service.create_portal_session(
        db, account=account, ip_address=_client_ip(request), user_agent=request.headers.get("user-agent")
    )
    _set_portal_session_cookie(response, raw_token)

    from app.modules.tenancy import service as tenancy_service

    tenant = tenancy_service.get_tenant_or_404(db, invitation.tenant_id)
    ctx = PortalContext(tenant_id=tenant.id, tenant_slug=tenant.slug, lead_id=account.lead_id, portal_account_id=account.id, portal_session_id=session.id)
    return _current_account_response(db, ctx)


@auth_router.post("/forgot-password", status_code=202)
def forgot_password(payload: PortalForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    from app.modules.tenancy import service as tenancy_service

    tenant = tenancy_service.get_tenant_by_slug(db, payload.tenant_slug)
    if tenant is not None:
        portal_service.request_portal_password_reset(db, tenant=tenant, email=payload.email)
    return {"status": "ok"}


@auth_router.post("/reset-password", status_code=204)
def reset_password(payload: PortalResetPasswordRequest, db: Session = Depends(get_db)) -> None:
    portal_service.reset_portal_password(db, token=payload.token, new_password=payload.new_password)


# --- Content: proposals -------------------------------------------------

@router.get("/proposals")
def list_my_proposals(ctx: PortalContext = Depends(get_portal_auth_context), db: Session = Depends(get_db)) -> list[dict]:
    from app.modules.proposals import service as proposals_service

    proposals = proposals_service.list_proposals(db, ctx.tenant_id, lead_id=ctx.lead_id)
    return [_proposal_to_dict(db, ctx.tenant_id, p) for p in proposals]


@router.get("/proposals/{proposal_id}")
def get_my_proposal(proposal_id: uuid.UUID, ctx: PortalContext = Depends(get_portal_auth_context), db: Session = Depends(get_db)) -> dict:
    from app.modules.proposals import service as proposals_service

    proposal = proposals_service.get_proposal_or_404(db, ctx.tenant_id, proposal_id)
    _assert_belongs_to_lead(proposal.lead_id, ctx)
    return _proposal_to_dict(db, ctx.tenant_id, proposal)


@router.post("/proposals/{proposal_id}/accept")
def accept_my_proposal(
    proposal_id: uuid.UUID, payload: AcceptProposalRequest,
    ctx: PortalContext = Depends(get_portal_auth_context), db: Session = Depends(get_db),
) -> dict:
    from app.modules.proposals import service as proposals_service

    proposal = proposals_service.get_proposal_or_404(db, ctx.tenant_id, proposal_id)
    _assert_belongs_to_lead(proposal.lead_id, ctx)
    proposal = proposals_service.accept_proposal(db, proposal=proposal, accepted_by_name=payload.accepted_by_name)
    return {"status": proposal.status.value}


@router.post("/proposals/{proposal_id}/reject")
def reject_my_proposal(
    proposal_id: uuid.UUID, payload: RejectProposalRequest,
    ctx: PortalContext = Depends(get_portal_auth_context), db: Session = Depends(get_db),
) -> dict:
    from app.modules.proposals import service as proposals_service

    proposal = proposals_service.get_proposal_or_404(db, ctx.tenant_id, proposal_id)
    _assert_belongs_to_lead(proposal.lead_id, ctx)
    proposal = proposals_service.reject_proposal(db, proposal=proposal, rejection_reason=payload.rejection_reason)
    return {"status": proposal.status.value}


def _proposal_to_dict(db: Session, tenant_id: uuid.UUID, proposal) -> dict:
    from app.modules.proposals import service as proposals_service

    items = proposals_service.list_line_items(db, tenant_id, proposal.id)
    totals = proposals_service.compute_totals(items, tax_rate=proposal.tax_rate)
    return {
        "id": str(proposal.id), "title": proposal.title, "status": proposal.status.value, "currency": proposal.currency,
        "terms": proposal.terms, "valid_until": proposal.valid_until.isoformat() if proposal.valid_until else None,
        "line_items": [{"description": i.description, "quantity": float(i.quantity), "unit_price": float(i.unit_price)} for i in items],
        "subtotal": float(totals["subtotal"]), "tax_amount": float(totals["tax_amount"]), "total": float(totals["total"]),
    }


# --- Content: document requests ----------------------------------------

@router.get("/documents")
def list_my_document_requests(ctx: PortalContext = Depends(get_portal_auth_context), db: Session = Depends(get_db)) -> list[dict]:
    from app.modules.documents import service as documents_service

    requests = documents_service.list_requests_for_lead(db, ctx.tenant_id, ctx.lead_id)
    return [_document_request_to_dict(r) for r in requests]


@router.get("/documents/{request_id}")
def get_my_document_request(request_id: uuid.UUID, ctx: PortalContext = Depends(get_portal_auth_context), db: Session = Depends(get_db)) -> dict:
    from app.modules.documents import service as documents_service

    document_request = documents_service.get_request_or_404(db, ctx.tenant_id, request_id)
    _assert_belongs_to_lead(document_request.lead_id, ctx)
    return _document_request_to_dict(document_request)


@router.post("/documents/{request_id}/upload", status_code=201)
async def upload_my_document(request_id: uuid.UUID, file: UploadFile, ctx: PortalContext = Depends(get_portal_auth_context), db: Session = Depends(get_db)) -> dict:
    from app.modules.documents import service as documents_service

    document_request = documents_service.get_request_or_404(db, ctx.tenant_id, request_id)
    _assert_belongs_to_lead(document_request.lead_id, ctx)
    content = await file.read()
    document = documents_service.upload_document(
        db, tenant_id=ctx.tenant_id, request=document_request, uploaded_by=None,
        file_name=file.filename or "upload", content_type=file.content_type or "application/octet-stream", content=content,
    )
    return {"id": str(document.id), "file_name": document.file_name}


def _document_request_to_dict(document_request) -> dict:
    return {
        "id": str(document_request.id), "title": document_request.title, "description": document_request.description,
        "status": document_request.status.value, "review_notes": document_request.review_notes,
    }


# --- Content: onboarding cases -------------------------------------------

@router.get("/onboarding-cases")
def list_my_onboarding_cases(ctx: PortalContext = Depends(get_portal_auth_context), db: Session = Depends(get_db)) -> list[dict]:
    from app.modules.onboarding import service as onboarding_service

    cases = onboarding_service.list_cases_for_lead(db, ctx.tenant_id, ctx.lead_id)
    return [_onboarding_case_to_dict(db, ctx.tenant_id, c) for c in cases]


def _onboarding_case_to_dict(db: Session, tenant_id: uuid.UUID, case) -> dict:
    from app.modules.onboarding import service as onboarding_service

    steps = onboarding_service.list_case_steps(db, tenant_id, case.id)
    return {
        "id": str(case.id), "name": case.name, "status": case.status.value,
        "steps": [{"title": s.title, "step_type": s.step_type.value, "status": s.status.value} for s in steps],
    }


# --- Content: appointments & deadlines (read-only) ---------------------

@router.get("/appointments")
def list_my_appointments(ctx: PortalContext = Depends(get_portal_auth_context), db: Session = Depends(get_db)) -> list[dict]:
    from app.modules.booking import service as booking_service

    appointments = booking_service.list_appointments(db, ctx.tenant_id, lead_id=ctx.lead_id)
    return [
        {
            "id": str(a.id), "title": a.title, "starts_at": a.starts_at.isoformat(), "ends_at": a.ends_at.isoformat(),
            "status": a.status.value, "location": a.location,
        }
        for a in appointments
    ]


@router.get("/deadlines")
def list_my_deadlines(ctx: PortalContext = Depends(get_portal_auth_context), db: Session = Depends(get_db)) -> list[dict]:
    from app.modules.deadlines import service as deadlines_service

    deadlines = deadlines_service.list_deadlines_for_lead(db, ctx.tenant_id, ctx.lead_id)
    return [
        {"id": str(d.id), "title": d.title, "description": d.description, "due_date": d.due_date.isoformat(), "status": d.status.value}
        for d in deadlines
    ]


# --- Staff-side portal account management --------------------------------

def _portal_account_to_dict(account) -> dict:
    return {
        "id": str(account.id), "lead_id": str(account.lead_id), "email": account.email,
        "is_active": account.is_active, "created_at": account.created_at.isoformat(),
    }


@staff_router.get("")
def list_portal_accounts(
    ctx: TenantContext = Depends(require_permission("portal.manage")),
    _mod: TenantContext = Depends(require_module("client_portal")), db: Session = Depends(get_db),
) -> list[dict]:
    return [_portal_account_to_dict(a) for a in portal_service.list_portal_accounts(db, ctx.tenant_id)]


@staff_router.post("/invite", status_code=201)
def invite_to_portal(
    payload: InviteToPortalRequest, ctx: TenantContext = Depends(require_permission("portal.manage")),
    _mod: TenantContext = Depends(require_module("client_portal")), db: Session = Depends(get_db),
) -> dict:
    from app.modules.tenancy import service as tenancy_service

    tenant = tenancy_service.get_tenant_or_404(db, ctx.tenant_id)
    invitation = portal_service.invite_to_portal(db, tenant_id=ctx.tenant_id, lead_id=payload.lead_id, invited_by=ctx.user_id, tenant=tenant)
    return {"id": str(invitation.id), "lead_id": str(invitation.lead_id), "email": invitation.email}


@staff_router.post("/{account_id}/revoke")
def revoke_portal_account(
    account_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("portal.manage")),
    _mod: TenantContext = Depends(require_module("client_portal")), db: Session = Depends(get_db),
) -> dict:
    account = PortalAccountRepository(db).get(ctx.tenant_id, account_id)
    if account is None:
        raise NotFoundError("Portal account not found.")
    account = portal_service.revoke_portal_account(db, tenant_id=ctx.tenant_id, account=account, actor_id=ctx.user_id)
    return _portal_account_to_dict(account)
