from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import PortalContext
from app.core.db import get_db, set_rls_context
from app.core.errors import ForbiddenError, UnauthorizedError
from app.modules.entitlements import service as entitlements_service
from app.modules.portal import service as portal_service
from app.modules.portal.repository import PortalAccountRepository
from app.modules.tenancy import service as tenancy_service
from app.modules.tenancy.models import TenantStatus

settings = get_settings()


def get_portal_auth_context(request: Request, db: Session = Depends(get_db)) -> PortalContext:
    """The portal analogue of `dependencies.tenant.get_tenant_context` —
    resolves the authenticated client strictly from the portal session
    cookie (never a client-supplied tenant/lead id), and gates on the
    `client_portal` module on every request: unlike Milestone 6's public
    proposal accept/reject routes, ongoing portal access is a feature a
    tenant pays for, not a one-time completed transaction, so a lapsed
    subscription should lock the whole portal out.
    """
    raw_token = request.cookies.get(settings.portal_session_cookie_name)
    if not raw_token:
        raise UnauthorizedError("Not authenticated.", code="not_authenticated")

    session = portal_service.get_portal_session_by_raw_token(db, raw_token)
    if session is None:
        raise UnauthorizedError("Session is invalid or has expired.", code="session_invalid")

    portal_service.touch_portal_session(db, session)

    # `session.tenant_id` is a denormalized copy carried on the (RLS-excluded)
    # session row itself precisely so this context can be established
    # before touching the row-level-secured `portal_accounts` table.
    set_rls_context(db, tenant_id=session.tenant_id, is_platform_admin=False)

    account = PortalAccountRepository(db).get(session.tenant_id, session.portal_account_id)
    if account is None or not account.is_active:
        raise UnauthorizedError("Account is no longer active.", code="account_inactive")

    tenant = tenancy_service.get_tenant(db, session.tenant_id)
    if tenant is None:
        raise UnauthorizedError("Tenant not found.", code="account_inactive")
    if tenant.status in {TenantStatus.ARCHIVED, TenantStatus.SUSPENDED}:
        raise ForbiddenError("This client portal is currently unavailable.", code="tenant_unavailable")

    entitlements_service.assert_module_enabled(db, tenant.id, "client_portal")

    request.state.portal_session = session
    return PortalContext(
        tenant_id=tenant.id, tenant_slug=tenant.slug, lead_id=account.lead_id,
        portal_account_id=account.id, portal_session_id=session.id,
    )
