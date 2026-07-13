from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import MembershipContext, get_current_membership, require_permission
from app.db.session import get_db
from app.schemas.assignment import AssignmentRuleCreate, AssignmentRuleOut, AssignmentRuleUpdate
from app.services.assignment_service import AssignmentService

router = APIRouter(prefix="/tenants/me/assignment-rules", tags=["assignment"])


@router.get("", response_model=list[AssignmentRuleOut])
def list_assignment_rules(
    db: Session = Depends(get_db), ctx: MembershipContext = Depends(get_current_membership)
) -> list[AssignmentRuleOut]:
    rules = AssignmentService(db).list_rules(ctx.tenant_id)
    return [AssignmentRuleOut.model_validate(r) for r in rules]


@router.post("", response_model=AssignmentRuleOut, status_code=201)
def create_assignment_rule(
    payload: AssignmentRuleCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("assignment.manage")),
) -> AssignmentRuleOut:
    rule = AssignmentService(db).create_rule(
        ctx.tenant_id,
        name=payload.name,
        strategy=payload.strategy,
        config=payload.config,
        sort_order=payload.sort_order,
        fallback_membership_id=payload.fallback_membership_id,
    )
    db.commit()
    return AssignmentRuleOut.model_validate(rule)


@router.patch("/{rule_id}", response_model=AssignmentRuleOut)
def update_assignment_rule(
    rule_id: uuid.UUID,
    payload: AssignmentRuleUpdate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("assignment.manage")),
) -> AssignmentRuleOut:
    rule = AssignmentService(db).update_rule(
        ctx.tenant_id, rule_id, **payload.model_dump(exclude_unset=True)
    )
    db.commit()
    return AssignmentRuleOut.model_validate(rule)
