import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import AuthContext
from app.core.db import get_db
from app.core.pagination import PageParams
from app.dependencies.tenant import require_platform_admin
from app.modules.audit import service as audit_service
from app.modules.entitlements import service as entitlements_service
from app.modules.platform_admin import service as platform_admin_service
from app.modules.platform_admin.schemas import (
    AssignPlanRequest,
    CreateTenantRequest,
    GrantAddOnRequest,
    GrantFeatureOverrideRequest,
    SetTenantStatusRequest,
    SupportAccessRequest,
    TenantSummary,
    UsageSummaryItem,
)
from app.modules.subscriptions import service as subscriptions_service
from app.modules.tenancy import service as tenancy_service

router = APIRouter(prefix="/platform", tags=["platform-admin"], dependencies=[Depends(require_platform_admin)])


@router.post("/tenants", response_model=TenantSummary, status_code=201)
def create_tenant(
    payload: CreateTenantRequest, auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db)
) -> TenantSummary:
    tenant = platform_admin_service.create_tenant_with_owner(
        db, name=payload.name, slug=payload.slug, plan_code=payload.plan_code,
        owner_email=payload.owner_email, owner_first_name=payload.owner_first_name,
        owner_last_name=payload.owner_last_name, created_by=auth.user_id,
    )
    return TenantSummary.model_validate(tenant)


@router.get("/tenants", response_model=list[TenantSummary])
def list_tenants(db: Session = Depends(get_db)) -> list[TenantSummary]:
    tenants = tenancy_service.list_tenants(db)
    return [TenantSummary.model_validate(t) for t in tenants]


@router.get("/tenants/{tenant_id}", response_model=TenantSummary)
def get_tenant(tenant_id: uuid.UUID, db: Session = Depends(get_db)) -> TenantSummary:
    tenant = tenancy_service.get_tenant_or_404(db, tenant_id)
    return TenantSummary.model_validate(tenant)


@router.post("/tenants/{tenant_id}/status", response_model=TenantSummary)
def set_tenant_status(
    tenant_id: uuid.UUID, payload: SetTenantStatusRequest,
    auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> TenantSummary:
    tenant = tenancy_service.get_tenant_or_404(db, tenant_id)
    before_status = tenant.status.value
    tenant = tenancy_service.set_tenant_status(db, tenant=tenant, status=payload.status)
    audit_service.log_event(
        db, tenant_id=tenant.id, actor_user_id=auth.user_id, action="tenant.status_changed",
        entity_type="tenant", entity_id=tenant.id,
        before={"status": before_status}, after={"status": payload.status.value},
    )
    return TenantSummary.model_validate(tenant)


@router.post("/tenants/{tenant_id}/plan")
def assign_plan(
    tenant_id: uuid.UUID, payload: AssignPlanRequest,
    auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> dict:
    subscriptions_service.assign_plan(
        db, tenant_id=tenant_id, plan_code=payload.plan_code, changed_by=auth.user_id, trial_ends_at=payload.trial_ends_at
    )
    return {"status": "ok"}


@router.post("/tenants/{tenant_id}/add-ons")
def grant_add_on(
    tenant_id: uuid.UUID, payload: GrantAddOnRequest,
    auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> dict:
    subscriptions_service.grant_add_on(
        db, tenant_id=tenant_id, add_on_code=payload.add_on_code, granted_by=auth.user_id, ends_at=payload.ends_at
    )
    return {"status": "ok"}


@router.post("/tenants/{tenant_id}/overrides")
def grant_feature_override(
    tenant_id: uuid.UUID, payload: GrantFeatureOverrideRequest,
    auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> dict:
    entitlements_service.grant_feature_override(
        db, tenant_id=tenant_id, feature_code=payload.feature_code, config=payload.config,
        granted_by=auth.user_id, expires_at=payload.expires_at, reason=payload.reason,
    )
    return {"status": "ok"}


@router.get("/tenants/{tenant_id}/entitlements")
def get_tenant_entitlements(tenant_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    entitlements = entitlements_service.resolve_entitlements(db, tenant_id)
    return {
        "plan_code": entitlements.plan_code,
        "subscription_status": entitlements.subscription_status,
        "modules": entitlements.modules,
        "features": entitlements.features,
    }


@router.get("/tenants/{tenant_id}/usage", response_model=list[UsageSummaryItem])
def get_tenant_usage(tenant_id: uuid.UUID, db: Session = Depends(get_db)) -> list[UsageSummaryItem]:
    metrics = ["users"]
    return [
        UsageSummaryItem(metric_code=code, value=entitlements_service.get_current_usage(db, tenant_id, code))
        for code in metrics
    ]


@router.post("/tenants/{tenant_id}/support-access")
def record_support_access(
    tenant_id: uuid.UUID, payload: SupportAccessRequest,
    auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> dict:
    audit_service.log_support_access(
        db, tenant_id=tenant_id, platform_admin_user_id=auth.user_id, reason=payload.reason, resource=payload.resource
    )
    return {"status": "ok"}


@router.get("/modules")
def list_modules(db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": str(m.id), "code": m.code, "name": m.name} for m in subscriptions_service.list_modules(db)]


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": str(p.id), "code": p.code, "name": p.name, "is_custom": p.is_custom} for p in subscriptions_service.list_active_plans(db)]


@router.get("/audit-logs")
def list_audit_logs(tenant_id: uuid.UUID | None = None, params: PageParams = Depends(), db: Session = Depends(get_db)) -> list[dict]:
    logs = (
        audit_service.list_tenant_audit_logs(db, tenant_id, limit=params.page_size, offset=params.offset)
        if tenant_id
        else audit_service.list_all_audit_logs(db, limit=params.page_size, offset=params.offset)
    )
    return [
        {
            "id": str(log.id), "tenant_id": str(log.tenant_id) if log.tenant_id else None,
            "actor_user_id": str(log.actor_user_id) if log.actor_user_id else None,
            "action": log.action, "entity_type": log.entity_type,
            "entity_id": str(log.entity_id) if log.entity_id else None,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.get("/support-access-logs")
def list_support_access_logs(params: PageParams = Depends(), db: Session = Depends(get_db)) -> list[dict]:
    logs = audit_service.list_support_access_logs(db, limit=params.page_size, offset=params.offset)
    return [
        {
            "id": str(log.id), "tenant_id": str(log.tenant_id),
            "platform_admin_user_id": str(log.platform_admin_user_id),
            "reason": log.reason, "resource": log.resource, "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
