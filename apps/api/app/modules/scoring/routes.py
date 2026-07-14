import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.dependencies.entitlements import require_module
from app.dependencies.permissions import require_permission
from app.modules.scoring import service as scoring_service
from app.modules.scoring.schemas import (
    CreateScoringRuleRequest,
    ReorderScoringRulesRequest,
    UpdateScoringRuleRequest,
    UpdateScoringSettingsRequest,
)

router = APIRouter(prefix="/tenant/scoring", tags=["scoring"])


def _rule_to_dict(rule) -> dict:
    return {
        "id": str(rule.id), "name": rule.name, "field": rule.field, "operator": rule.operator.value,
        "value": rule.value.get("value"), "points": rule.points, "sort_order": rule.sort_order, "is_active": rule.is_active,
    }


@router.get("/rules")
def list_rules(
    ctx: TenantContext = Depends(require_permission("leads.view")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> list[dict]:
    return [_rule_to_dict(r) for r in scoring_service.list_rules(db, ctx.tenant_id)]


@router.post("/rules", status_code=201)
def create_rule(
    payload: CreateScoringRuleRequest,
    ctx: TenantContext = Depends(require_permission("scoring.manage")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    rule = scoring_service.create_rule(
        db, tenant_id=ctx.tenant_id, name=payload.name, field=payload.field, operator=payload.operator,
        value=payload.value, points=payload.points,
    )
    return _rule_to_dict(rule)


@router.patch("/rules/{rule_id}")
def update_rule(
    rule_id: uuid.UUID, payload: UpdateScoringRuleRequest,
    ctx: TenantContext = Depends(require_permission("scoring.manage")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    rule = scoring_service.get_rule_or_404(db, ctx.tenant_id, rule_id)
    updated = scoring_service.update_rule(db, tenant_id=ctx.tenant_id, rule=rule, updates=payload.model_dump(exclude_unset=True))
    return _rule_to_dict(updated)


@router.put("/rules/reorder")
def reorder_rules(
    payload: ReorderScoringRulesRequest,
    ctx: TenantContext = Depends(require_permission("scoring.manage")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    scoring_service.reorder_rules(db, tenant_id=ctx.tenant_id, rule_ids_in_order=payload.rule_ids)
    return {"status": "ok"}


@router.get("/settings")
def get_settings(
    ctx: TenantContext = Depends(require_permission("leads.view")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    settings = scoring_service.ensure_scoring_settings(db, ctx.tenant_id)
    return {"hot_threshold": settings.hot_threshold, "warm_threshold": settings.warm_threshold, "auto_priority": settings.auto_priority}


@router.patch("/settings")
def update_settings(
    payload: UpdateScoringSettingsRequest,
    ctx: TenantContext = Depends(require_permission("scoring.manage")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    settings = scoring_service.update_scoring_settings(db, ctx.tenant_id, updates=payload.model_dump(exclude_unset=True))
    return {"hot_threshold": settings.hot_threshold, "warm_threshold": settings.warm_threshold, "auto_priority": settings.auto_priority}


@router.get("/leads/{lead_id}/breakdown")
def get_score_breakdown(
    lead_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("leads.view")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    log = scoring_service.get_latest_score_log(db, ctx.tenant_id, lead_id)
    if log is None:
        return {"total_score": None, "breakdown": [], "computed_at": None}
    return {"total_score": log.total_score, "breakdown": log.breakdown, "computed_at": log.created_at.isoformat()}


@router.post("/leads/{lead_id}/rescore")
def rescore_lead(
    lead_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("leads.update")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    from app.modules.leads.service import get_lead_or_404

    lead = get_lead_or_404(db, ctx.tenant_id, lead_id)
    scoring_service.score_and_apply(db, tenant_id=ctx.tenant_id, lead=lead, actor_id=ctx.user_id)
    return {"score": lead.score, "priority": lead.priority.value}
