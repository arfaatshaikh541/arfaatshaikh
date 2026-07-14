from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.context import AuthContext, TenantContext
from app.core.db import get_db, set_rls_context
from app.core.errors import ForbiddenError, NotFoundError
from app.dependencies.auth import get_current_auth_context
from app.modules.identity.models import MembershipStatus
from app.modules.identity.repository import MembershipRepository
from app.modules.permissions import service as permissions_service
from app.modules.tenancy import service as tenancy_service
from app.modules.tenancy.models import TenantStatus

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_tenant_context(
    request: Request,
    auth: AuthContext = Depends(get_current_auth_context),
    db: Session = Depends(get_db),
) -> TenantContext:
    """Resolves the active tenant strictly from the authenticated session's
    `active_tenant_id` plus a live membership row — a client can never
    supply a tenant_id directly. Also enforces tenant-status restrictions
    (archived/suspended/read-only) before any handler runs, and sets the
    PostgreSQL RLS session variables for this transaction.
    """
    session = getattr(request.state, "session", None)
    active_tenant_id = session.active_tenant_id if session else None
    if active_tenant_id is None:
        raise ForbiddenError("No active tenant selected. Switch to a tenant first.", code="no_active_tenant")

    membership = MembershipRepository(db).get(active_tenant_id, auth.user_id)
    if membership is None or membership.status != MembershipStatus.ACTIVE:
        raise ForbiddenError("You are not an active member of this tenant.", code="not_a_member")

    tenant = tenancy_service.get_tenant(db, active_tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found.")

    if tenant.status == TenantStatus.ARCHIVED:
        raise ForbiddenError("This tenant has been archived.", code="tenant_archived")
    if tenant.status == TenantStatus.SUSPENDED:
        raise ForbiddenError("This tenant's subscription is suspended. Contact your administrator.", code="tenant_suspended")
    if tenant.status == TenantStatus.READ_ONLY and request.method.upper() not in _SAFE_METHODS:
        raise ForbiddenError("This tenant is in read-only mode. Write operations are disabled.", code="tenant_read_only")

    role = permissions_service.get_role(db, membership.role_id)
    if role is None:
        raise NotFoundError("Role not found.")
    permission_codes = permissions_service.get_role_permission_codes(db, membership.role_id)

    set_rls_context(db, tenant_id=tenant.id, is_platform_admin=auth.is_platform_admin)

    return TenantContext(
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        tenant_status=tenant.status,
        membership_id=membership.id,
        role_id=membership.role_id,
        role_name=role.name,
        permission_codes=frozenset(permission_codes),
        user_id=auth.user_id,
        is_platform_admin=auth.is_platform_admin,
    )


def require_platform_admin(auth: AuthContext = Depends(get_current_auth_context), db: Session = Depends(get_db)) -> AuthContext:
    if not auth.is_platform_admin:
        raise ForbiddenError("Platform administrator access required.", code="platform_admin_required")
    set_rls_context(db, tenant_id=None, is_platform_admin=True)
    return auth
