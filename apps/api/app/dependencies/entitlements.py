from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.dependencies.tenant import get_tenant_context
from app.modules.entitlements import service as entitlements_service


def require_module(module_code: str) -> Callable[[TenantContext, Session], TenantContext]:
    def dependency(ctx: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> TenantContext:
        entitlements_service.assert_module_enabled(db, ctx.tenant_id, module_code)
        return ctx

    return dependency


def require_feature(feature_code: str) -> Callable[[TenantContext, Session], TenantContext]:
    def dependency(ctx: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> TenantContext:
        entitlements_service.assert_feature_enabled(db, ctx.tenant_id, feature_code)
        return ctx

    return dependency


def check_usage_limit(metric_code: str, *, feature_code: str | None = None, amount: int = 1) -> Callable[[TenantContext, Session], TenantContext]:
    """Reserves `amount` units of `metric_code` for this request. The
    resolved limit is read from `feature_code` (defaults to the same code
    as the metric, matching our seed convention of e.g. metric `users` /
    feature `users`).

    Only checks and increments — callers whose action ultimately fails
    after this dependency runs will over-count slightly within a
    request's transaction lifetime is fine since the whole request's DB
    transaction rolls back together on error via `get_db`.
    """

    def dependency(ctx: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> TenantContext:
        entitlements_service.check_and_increment_usage(
            db, ctx.tenant_id, metric_code=metric_code, feature_code=feature_code or metric_code, amount=amount
        )
        return ctx

    return dependency
