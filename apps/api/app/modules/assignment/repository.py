import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.assignment.models import AssignmentRule, AssignmentRuleRoundRobinState


class AssignmentRuleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, rule_id: uuid.UUID) -> AssignmentRule | None:
        return self.db.execute(
            select(AssignmentRule).where(AssignmentRule.tenant_id == tenant_id, AssignmentRule.id == rule_id)
        ).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID, *, active_only: bool = False) -> list[AssignmentRule]:
        stmt = select(AssignmentRule).where(AssignmentRule.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(AssignmentRule.is_active.is_(True))
        return list(self.db.execute(stmt.order_by(AssignmentRule.sort_order)).scalars().all())

    def create(
        self, *, tenant_id: uuid.UUID, name: str, strategy, conditions: dict, eligible_user_ids: list, sort_order: int = 0
    ) -> AssignmentRule:
        rule = AssignmentRule(
            tenant_id=tenant_id, name=name, strategy=strategy, conditions=conditions,
            eligible_user_ids=eligible_user_ids, sort_order=sort_order,
        )
        self.db.add(rule)
        self.db.flush()
        return rule

    def reorder(self, rules_in_order: list[AssignmentRule]) -> None:
        for index, rule in enumerate(rules_in_order):
            rule.sort_order = index
        self.db.flush()


class AssignmentRoundRobinStateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_for_update(self, tenant_id: uuid.UUID, rule_id: uuid.UUID) -> AssignmentRuleRoundRobinState:
        state = self.db.execute(
            select(AssignmentRuleRoundRobinState)
            .where(AssignmentRuleRoundRobinState.rule_id == rule_id)
            .with_for_update()
        ).scalar_one_or_none()
        if state is None:
            state = AssignmentRuleRoundRobinState(tenant_id=tenant_id, rule_id=rule_id, last_assigned_index=-1)
            self.db.add(state)
            self.db.flush()
        return state
