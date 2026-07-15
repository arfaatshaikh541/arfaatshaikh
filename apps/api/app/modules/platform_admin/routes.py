import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import AuthContext
from app.core.db import get_db
from app.core.errors import NotFoundError
from app.core.pagination import PageParams
from app.dependencies.tenant import require_platform_admin
from app.modules.audit import service as audit_service
from app.modules.entitlements import service as entitlements_service
from app.modules.platform_admin import service as platform_admin_service
from app.modules.platform_admin.schemas import (
    AddOnDetail,
    AssignPlanRequest,
    CreateAddOnRequest,
    CreateFeatureRequest,
    CreateModuleRequest,
    CreatePlanRequest,
    CreateTenantRequest,
    CreateUsageMetricRequest,
    FeatureDetail,
    GrantAddOnRequest,
    GrantFeatureOverrideRequest,
    ModuleDetail,
    PlanDetail,
    PlanFeatureDetail,
    SetPlanActiveRequest,
    SetPlanFeatureRequest,
    SetTenantStatusRequest,
    SupportAccessRequest,
    TenantSummary,
    UpdateAddOnRequest,
    UpdateFeatureRequest,
    UpdateModuleRequest,
    UpdatePlanRequest,
    UpdateUsageMetricRequest,
    UsageMetricDetail,
    UsageSummaryItem,
)
from app.modules.subscriptions import service as subscriptions_service
from app.modules.subscriptions.repository import FeatureRepository, PlanRepository
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


@router.get("/modules", response_model=list[ModuleDetail])
def list_modules(db: Session = Depends(get_db)) -> list[ModuleDetail]:
    return [ModuleDetail.model_validate(m) for m in subscriptions_service.list_modules(db)]


@router.post("/modules", response_model=ModuleDetail, status_code=201)
def create_module(
    payload: CreateModuleRequest, auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db)
) -> ModuleDetail:
    module = subscriptions_service.create_module(
        db, code=payload.code, name=payload.name, description=payload.description, created_by=auth.user_id
    )
    return ModuleDetail.model_validate(module)


@router.put("/modules/{module_id}", response_model=ModuleDetail)
def update_module(
    module_id: uuid.UUID, payload: UpdateModuleRequest,
    auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> ModuleDetail:
    module = subscriptions_service.update_module(
        db, module_id=module_id, name=payload.name, description=payload.description, updated_by=auth.user_id
    )
    return ModuleDetail.model_validate(module)


@router.get("/features", response_model=list[FeatureDetail])
def list_features(db: Session = Depends(get_db)) -> list[FeatureDetail]:
    return [
        FeatureDetail(
            id=f.id, module_id=f.module_id, module_code=f.module.code, code=f.code, name=f.name, feature_type=f.feature_type
        )
        for f in subscriptions_service.list_all_features(db)
    ]


@router.post("/features", response_model=FeatureDetail, status_code=201)
def create_feature(
    payload: CreateFeatureRequest, auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db)
) -> FeatureDetail:
    feature = subscriptions_service.create_feature(
        db, module_id=payload.module_id, code=payload.code, name=payload.name,
        feature_type=payload.feature_type, created_by=auth.user_id,
    )
    return FeatureDetail(
        id=feature.id, module_id=feature.module_id, module_code=feature.module.code,
        code=feature.code, name=feature.name, feature_type=feature.feature_type,
    )


@router.put("/features/{feature_id}", response_model=FeatureDetail)
def update_feature(
    feature_id: uuid.UUID, payload: UpdateFeatureRequest,
    auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> FeatureDetail:
    feature = subscriptions_service.update_feature(db, feature_id=feature_id, name=payload.name, updated_by=auth.user_id)
    return FeatureDetail(
        id=feature.id, module_id=feature.module_id, module_code=feature.module.code,
        code=feature.code, name=feature.name, feature_type=feature.feature_type,
    )


@router.get("/plans", response_model=list[PlanDetail])
def list_plans(all_plans: bool = False, db: Session = Depends(get_db)) -> list[PlanDetail]:
    plans = subscriptions_service.list_all_plans(db) if all_plans else subscriptions_service.list_active_plans(db)
    return [PlanDetail.model_validate(p) for p in plans]


@router.post("/plans", response_model=PlanDetail, status_code=201)
def create_plan(
    payload: CreatePlanRequest, auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db)
) -> PlanDetail:
    plan = subscriptions_service.create_plan(
        db, code=payload.code, name=payload.name, description=payload.description,
        is_custom=payload.is_custom, created_by=auth.user_id,
    )
    return PlanDetail.model_validate(plan)


@router.put("/plans/{plan_id}", response_model=PlanDetail)
def update_plan(
    plan_id: uuid.UUID, payload: UpdatePlanRequest,
    auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> PlanDetail:
    plan = subscriptions_service.update_plan(
        db, plan_id=plan_id, name=payload.name, description=payload.description, updated_by=auth.user_id
    )
    return PlanDetail.model_validate(plan)


@router.post("/plans/{plan_id}/active", response_model=PlanDetail)
def set_plan_active(
    plan_id: uuid.UUID, payload: SetPlanActiveRequest,
    auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> PlanDetail:
    plan = subscriptions_service.set_plan_active(db, plan_id=plan_id, is_active=payload.is_active, updated_by=auth.user_id)
    return PlanDetail.model_validate(plan)


@router.get("/plans/{plan_id}/features", response_model=list[PlanFeatureDetail])
def list_plan_features(plan_id: uuid.UUID, db: Session = Depends(get_db)) -> list[PlanFeatureDetail]:
    plan_repo = PlanRepository(db)
    if plan_repo.get(plan_id) is None:
        raise NotFoundError("Plan not found.")
    feature_repo = FeatureRepository(db)
    result = []
    for pf in plan_repo.list_plan_features(plan_id):
        feature = feature_repo.get(pf.feature_id)
        if feature is None:
            continue
        result.append(
            PlanFeatureDetail(
                feature_code=feature.code, feature_name=feature.name,
                module_code=feature.module.code, feature_type=feature.feature_type, config=pf.config,
            )
        )
    return result


@router.put("/plans/{plan_id}/features")
def set_plan_feature(
    plan_id: uuid.UUID, payload: SetPlanFeatureRequest,
    auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> dict:
    subscriptions_service.set_plan_feature(
        db, plan_id=plan_id, feature_code=payload.feature_code, enabled=payload.enabled,
        limit=payload.limit, updated_by=auth.user_id,
    )
    return {"status": "ok"}


@router.delete("/plans/{plan_id}/features")
def remove_plan_feature(
    plan_id: uuid.UUID, feature_code: str,
    auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> dict:
    subscriptions_service.remove_plan_feature(
        db, plan_id=plan_id, feature_code=feature_code, updated_by=auth.user_id
    )
    return {"status": "ok"}


@router.get("/add-ons", response_model=list[AddOnDetail])
def list_add_ons(db: Session = Depends(get_db)) -> list[AddOnDetail]:
    return [AddOnDetail.model_validate(a) for a in subscriptions_service.list_all_add_ons(db)]


@router.post("/add-ons", response_model=AddOnDetail, status_code=201)
def create_add_on(
    payload: CreateAddOnRequest, auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db)
) -> AddOnDetail:
    add_on = subscriptions_service.create_add_on(
        db, code=payload.code, name=payload.name, grants=payload.grants, created_by=auth.user_id
    )
    return AddOnDetail.model_validate(add_on)


@router.put("/add-ons/{add_on_id}", response_model=AddOnDetail)
def update_add_on(
    add_on_id: uuid.UUID, payload: UpdateAddOnRequest,
    auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> AddOnDetail:
    add_on = subscriptions_service.update_add_on(
        db, add_on_id=add_on_id, name=payload.name, grants=payload.grants, updated_by=auth.user_id
    )
    return AddOnDetail.model_validate(add_on)


@router.get("/usage-metrics", response_model=list[UsageMetricDetail])
def list_usage_metrics(db: Session = Depends(get_db)) -> list[UsageMetricDetail]:
    return [UsageMetricDetail.model_validate(m) for m in entitlements_service.list_usage_metrics(db)]


@router.post("/usage-metrics", response_model=UsageMetricDetail, status_code=201)
def create_usage_metric(
    payload: CreateUsageMetricRequest, auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db)
) -> UsageMetricDetail:
    metric = entitlements_service.create_usage_metric(
        db, code=payload.code, name=payload.name, unit=payload.unit, created_by=auth.user_id
    )
    return UsageMetricDetail.model_validate(metric)


@router.put("/usage-metrics/{metric_id}", response_model=UsageMetricDetail)
def update_usage_metric(
    metric_id: uuid.UUID, payload: UpdateUsageMetricRequest,
    auth: AuthContext = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> UsageMetricDetail:
    metric = entitlements_service.update_usage_metric(
        db, metric_id=metric_id, name=payload.name, unit=payload.unit, updated_by=auth.user_id
    )
    return UsageMetricDetail.model_validate(metric)


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
