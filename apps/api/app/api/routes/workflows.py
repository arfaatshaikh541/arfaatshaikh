from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import MembershipContext, require_permission
from app.db.session import get_db
from app.schemas.workflow import (
    WorkflowExecutionLogOut,
    WorkflowRuleCreate,
    WorkflowRuleOut,
    WorkflowRuleUpdate,
)
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/tenants/me/workflow-rules", tags=["workflows"])


@router.get("/execution-log", response_model=list[WorkflowExecutionLogOut])
def list_workflow_execution_log(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("workflows.manage")),
) -> list[WorkflowExecutionLogOut]:
    entries = WorkflowService(db).list_execution_log(ctx.tenant_id, limit=limit)
    return [WorkflowExecutionLogOut.model_validate(e) for e in entries]


@router.get("", response_model=list[WorkflowRuleOut])
def list_workflow_rules(
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("workflows.manage")),
) -> list[WorkflowRuleOut]:
    rules = WorkflowService(db).list_rules(ctx.tenant_id)
    return [WorkflowRuleOut.model_validate(r) for r in rules]


@router.post("", response_model=WorkflowRuleOut, status_code=201)
def create_workflow_rule(
    payload: WorkflowRuleCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("workflows.manage")),
) -> WorkflowRuleOut:
    rule = WorkflowService(db).create_rule(
        ctx.tenant_id,
        name=payload.name,
        trigger_type=payload.trigger_type,
        conditions=payload.conditions,
        actions=payload.actions,
        sort_order=payload.sort_order,
    )
    db.commit()
    return WorkflowRuleOut.model_validate(rule)


@router.patch("/{rule_id}", response_model=WorkflowRuleOut)
def update_workflow_rule(
    rule_id: uuid.UUID,
    payload: WorkflowRuleUpdate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("workflows.manage")),
) -> WorkflowRuleOut:
    rule = WorkflowService(db).update_rule(
        ctx.tenant_id, rule_id, **payload.model_dump(exclude_unset=True)
    )
    db.commit()
    return WorkflowRuleOut.model_validate(rule)
