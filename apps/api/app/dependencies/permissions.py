from collections.abc import Callable

from fastapi import Depends

from app.core.context import TenantContext
from app.core.errors import ForbiddenError
from app.dependencies.tenant import get_tenant_context


def require_permission(code: str) -> Callable[[TenantContext], TenantContext]:
    """Backend-enforced RBAC check. Tenant Owner/Administrator-style "grant
    everything" behaviour is achieved by that role's seeded permission set
    containing every tenant permission — this dependency itself never
    special-cases a role name, so there is exactly one code path to audit.
    """

    def dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not ctx.has_permission(code):
            raise ForbiddenError(f"You do not have the '{code}' permission.", code="permission_denied")
        return ctx

    return dependency
