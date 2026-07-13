import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.workflow import WorkflowExecutionLog, WorkflowRule


class WorkflowRuleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_tenant(
        self, tenant_id: uuid.UUID, *, trigger_type: str | None = None, active_only: bool = False
    ) -> list[WorkflowRule]:
        stmt = select(WorkflowRule).where(WorkflowRule.tenant_id == tenant_id)
        if trigger_type is not None:
            stmt = stmt.where(WorkflowRule.trigger_type == trigger_type)
        if active_only:
            stmt = stmt.where(WorkflowRule.is_active.is_(True))
        stmt = stmt.order_by(WorkflowRule.sort_order)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_for_tenant(self, tenant_id: uuid.UUID, rule_id: uuid.UUID) -> WorkflowRule | None:
        stmt = select(WorkflowRule).where(
            WorkflowRule.tenant_id == tenant_id, WorkflowRule.id == rule_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        trigger_type: str,
        conditions: list,
        actions: list,
        sort_order: int = 0,
    ) -> WorkflowRule:
        rule = WorkflowRule(
            tenant_id=tenant_id,
            name=name,
            trigger_type=trigger_type,
            conditions=conditions,
            actions=actions,
            sort_order=sort_order,
        )
        self.db.add(rule)
        self.db.flush()
        return rule

    def update(self, rule: WorkflowRule, **fields: object) -> WorkflowRule:
        for key, value in fields.items():
            if value is not None:
                setattr(rule, key, value)
        self.db.flush()
        return rule


class WorkflowExecutionLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        tenant_id: uuid.UUID,
        workflow_rule_id: uuid.UUID,
        lead_id: uuid.UUID | None,
        trigger_type: str,
        actions_taken: list,
    ) -> WorkflowExecutionLog:
        entry = WorkflowExecutionLog(
            tenant_id=tenant_id,
            workflow_rule_id=workflow_rule_id,
            lead_id=lead_id,
            trigger_type=trigger_type,
            actions_taken=actions_taken,
            executed_at=utcnow(),
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_for_tenant(
        self, tenant_id: uuid.UUID, *, limit: int = 100
    ) -> list[WorkflowExecutionLog]:
        stmt = (
            select(WorkflowExecutionLog)
            .where(WorkflowExecutionLog.tenant_id == tenant_id)
            .order_by(WorkflowExecutionLog.executed_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
