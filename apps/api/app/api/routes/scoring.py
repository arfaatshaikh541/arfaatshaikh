from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import MembershipContext, get_current_membership, require_permission
from app.db.session import get_db
from app.schemas.scoring import (
    ScoringRuleCreate,
    ScoringRuleOut,
    ScoringRuleUpdate,
    TenantScoringSettingsOut,
    TenantScoringSettingsUpdate,
)
from app.services.scoring_service import ScoringService

router = APIRouter(prefix="/tenants/me/scoring", tags=["scoring"])


@router.get("/rules", response_model=list[ScoringRuleOut])
def list_scoring_rules(
    db: Session = Depends(get_db), ctx: MembershipContext = Depends(get_current_membership)
) -> list[ScoringRuleOut]:
    rules = ScoringService(db).list_rules(ctx.tenant_id)
    return [ScoringRuleOut.model_validate(r) for r in rules]


@router.post("/rules", response_model=ScoringRuleOut, status_code=201)
def create_scoring_rule(
    payload: ScoringRuleCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("scoring.manage")),
) -> ScoringRuleOut:
    rule = ScoringService(db).create_rule(
        ctx.tenant_id,
        name=payload.name,
        rule_type=payload.rule_type,
        config=payload.config,
        points=payload.points,
        sort_order=payload.sort_order,
    )
    db.commit()
    return ScoringRuleOut.model_validate(rule)


@router.patch("/rules/{rule_id}", response_model=ScoringRuleOut)
def update_scoring_rule(
    rule_id: uuid.UUID,
    payload: ScoringRuleUpdate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("scoring.manage")),
) -> ScoringRuleOut:
    rule = ScoringService(db).update_rule(
        ctx.tenant_id, rule_id, **payload.model_dump(exclude_unset=True)
    )
    db.commit()
    return ScoringRuleOut.model_validate(rule)


@router.get("/thresholds", response_model=TenantScoringSettingsOut)
def get_scoring_thresholds(
    db: Session = Depends(get_db), ctx: MembershipContext = Depends(get_current_membership)
) -> TenantScoringSettingsOut:
    settings = ScoringService(db).get_thresholds(ctx.tenant_id)
    db.commit()
    return TenantScoringSettingsOut.model_validate(settings)


@router.patch("/thresholds", response_model=TenantScoringSettingsOut)
def update_scoring_thresholds(
    payload: TenantScoringSettingsUpdate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("scoring.manage")),
) -> TenantScoringSettingsOut:
    settings = ScoringService(db).update_thresholds(
        ctx.tenant_id, **payload.model_dump(exclude_unset=True)
    )
    db.commit()
    return TenantScoringSettingsOut.model_validate(settings)
