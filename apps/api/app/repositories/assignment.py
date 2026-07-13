import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment import AssignmentRule, AssignmentRuleState


class AssignmentRuleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_tenant(
        self, tenant_id: uuid.UUID, *, active_only: bool = False
    ) -> list[AssignmentRule]:
        stmt = select(AssignmentRule).where(AssignmentRule.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(AssignmentRule.is_active.is_(True))
        stmt = stmt.order_by(AssignmentRule.sort_order)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_for_tenant(
        self, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> AssignmentRule | None:
        stmt = select(AssignmentRule).where(
            AssignmentRule.tenant_id == tenant_id, AssignmentRule.id == rule_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        strategy: str,
        config: dict,
        sort_order: int = 0,
        fallback_membership_id: uuid.UUID | None = None,
    ) -> AssignmentRule:
        rule = AssignmentRule(
            tenant_id=tenant_id,
            name=name,
            strategy=strategy,
            config=config,
            sort_order=sort_order,
            fallback_membership_id=fallback_membership_id,
        )
        self.db.add(rule)
        self.db.flush()
        return rule

    def update(self, rule: AssignmentRule, **fields: object) -> AssignmentRule:
        for key, value in fields.items():
            if value is not None:
                setattr(rule, key, value)
        self.db.flush()
        return rule


class AssignmentRuleStateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create(self, rule_id: uuid.UUID) -> AssignmentRuleState:
        stmt = select(AssignmentRuleState).where(AssignmentRuleState.rule_id == rule_id)
        state = self.db.execute(stmt).scalar_one_or_none()
        if state is None:
            state = AssignmentRuleState(rule_id=rule_id, last_assigned_index=-1)
            self.db.add(state)
            self.db.flush()
        return state

    def advance(self, state: AssignmentRuleState, *, candidate_count: int) -> int:
        state.last_assigned_index = (state.last_assigned_index + 1) % candidate_count
        self.db.flush()
        return state.last_assigned_index
