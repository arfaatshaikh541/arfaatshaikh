import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.dependencies.entitlements import require_module
from app.dependencies.permissions import require_permission
from app.modules.assignment import service as assignment_service
from app.modules.assignment.schemas import (
    CreateAssignmentRuleRequest,
    ReorderAssignmentRulesRequest,
    UpdateAssignmentRuleRequest,
)

router = APIRouter(prefix="/tenant/assignment", tags=["assignment"])


def _rule_to_dict(rule) -> dict:
    return {
        "id": str(rule.id), "name": rule.name, "strategy": rule.strategy.value, "conditions": rule.conditions,
        "eligible_user_ids": rule.eligible_user_ids, "sort_order": rule.sort_order, "is_active": rule.is_active,
    }


@router.get("/rules")
def list_rules(
    ctx: TenantContext = Depends(require_permission("leads.view")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> list[dict]:
    return [_rule_to_dict(r) for r in assignment_service.list_rules(db, ctx.tenant_id)]


@router.post("/rules", status_code=201)
def create_rule(
    payload: CreateAssignmentRuleRequest,
    ctx: TenantContext = Depends(require_permission("assignment.manage")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    rule = assignment_service.create_rule(
        db, tenant_id=ctx.tenant_id, name=payload.name, strategy=payload.strategy,
        conditions=payload.conditions, eligible_user_ids=payload.eligible_user_ids,
    )
    return _rule_to_dict(rule)


@router.patch("/rules/{rule_id}")
def update_rule(
    rule_id: uuid.UUID, payload: UpdateAssignmentRuleRequest,
    ctx: TenantContext = Depends(require_permission("assignment.manage")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    rule = assignment_service.get_rule_or_404(db, ctx.tenant_id, rule_id)
    updated = assignment_service.update_rule(db, tenant_id=ctx.tenant_id, rule=rule, updates=payload.model_dump(exclude_unset=True))
    return _rule_to_dict(updated)


@router.put("/rules/reorder")
def reorder_rules(
    payload: ReorderAssignmentRulesRequest,
    ctx: TenantContext = Depends(require_permission("assignment.manage")),
    _mod: TenantContext = Depends(require_module("crm")), db: Session = Depends(get_db),
) -> dict:
    assignment_service.reorder_rules(db, tenant_id=ctx.tenant_id, rule_ids_in_order=payload.rule_ids)
    return {"status": "ok"}
