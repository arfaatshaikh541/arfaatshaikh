import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.workflow_automation.models import (
    Workflow,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowStep,
    WorkflowStepLog,
    WorkflowTriggerEvent,
)


class WorkflowRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, workflow_id: uuid.UUID) -> Workflow | None:
        return self.db.execute(
            select(Workflow).where(Workflow.tenant_id == tenant_id, Workflow.id == workflow_id)
        ).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[Workflow]:
        return list(
            self.db.execute(select(Workflow).where(Workflow.tenant_id == tenant_id).order_by(Workflow.sort_order)).scalars().all()
        )

    def list_active_by_trigger(self, tenant_id: uuid.UUID, trigger_event: WorkflowTriggerEvent) -> list[Workflow]:
        return list(
            self.db.execute(
                select(Workflow)
                .where(Workflow.tenant_id == tenant_id, Workflow.trigger_event == trigger_event, Workflow.is_active.is_(True))
                .order_by(Workflow.sort_order)
            )
            .scalars()
            .all()
        )

    def create(
        self, *, tenant_id: uuid.UUID, name: str, description: str, trigger_event: WorkflowTriggerEvent,
        trigger_config: dict, conditions: list, sort_order: int = 0,
    ) -> Workflow:
        workflow = Workflow(
            tenant_id=tenant_id, name=name, description=description, trigger_event=trigger_event,
            trigger_config=trigger_config, conditions=conditions, sort_order=sort_order,
        )
        self.db.add(workflow)
        self.db.flush()
        return workflow


class WorkflowStepRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, step_id: uuid.UUID) -> WorkflowStep | None:
        return self.db.execute(
            select(WorkflowStep).where(WorkflowStep.tenant_id == tenant_id, WorkflowStep.id == step_id)
        ).scalar_one_or_none()

    def list_for_workflow(self, tenant_id: uuid.UUID, workflow_id: uuid.UUID) -> list[WorkflowStep]:
        return list(
            self.db.execute(
                select(WorkflowStep)
                .where(WorkflowStep.tenant_id == tenant_id, WorkflowStep.workflow_id == workflow_id)
                .order_by(WorkflowStep.sequence_order)
            )
            .scalars()
            .all()
        )

    def create(
        self, *, tenant_id: uuid.UUID, workflow_id: uuid.UUID, sequence_order: int, delay_minutes: int, action_type, action_config: dict
    ) -> WorkflowStep:
        step = WorkflowStep(
            tenant_id=tenant_id, workflow_id=workflow_id, sequence_order=sequence_order, delay_minutes=delay_minutes,
            action_type=action_type, action_config=action_config,
        )
        self.db.add(step)
        self.db.flush()
        return step


class WorkflowRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, run_id: uuid.UUID) -> WorkflowRun | None:
        return self.db.execute(
            select(WorkflowRun).where(WorkflowRun.tenant_id == tenant_id, WorkflowRun.id == run_id)
        ).scalar_one_or_none()

    def list_for_workflow(self, tenant_id: uuid.UUID, workflow_id: uuid.UUID) -> list[WorkflowRun]:
        return list(
            self.db.execute(
                select(WorkflowRun)
                .where(WorkflowRun.tenant_id == tenant_id, WorkflowRun.workflow_id == workflow_id)
                .order_by(WorkflowRun.triggered_at.desc())
            )
            .scalars()
            .all()
        )

    def list_for_lead(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> list[WorkflowRun]:
        return list(
            self.db.execute(
                select(WorkflowRun).where(WorkflowRun.tenant_id == tenant_id, WorkflowRun.lead_id == lead_id).order_by(WorkflowRun.triggered_at.desc())
            )
            .scalars()
            .all()
        )

    def list_due(self, *, before: datetime, tenant_id: uuid.UUID | None = None) -> list[WorkflowRun]:
        stmt = select(WorkflowRun).where(
            WorkflowRun.status == WorkflowRunStatus.RUNNING, WorkflowRun.next_run_at.isnot(None), WorkflowRun.next_run_at <= before,
        ).with_for_update()
        if tenant_id is not None:
            stmt = stmt.where(WorkflowRun.tenant_id == tenant_id)
        return list(self.db.execute(stmt).scalars().all())

    def create(
        self, *, tenant_id: uuid.UUID, workflow_id: uuid.UUID, lead_id: uuid.UUID, next_run_at: datetime, triggered_at: datetime
    ) -> WorkflowRun:
        run = WorkflowRun(tenant_id=tenant_id, workflow_id=workflow_id, lead_id=lead_id, next_run_at=next_run_at, triggered_at=triggered_at)
        self.db.add(run)
        self.db.flush()
        return run


class WorkflowStepLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, tenant_id: uuid.UUID, workflow_run_id: uuid.UUID, step_id: uuid.UUID, status, result_summary: str = "") -> WorkflowStepLog:
        log = WorkflowStepLog(tenant_id=tenant_id, workflow_run_id=workflow_run_id, step_id=step_id, status=status, result_summary=result_summary)
        self.db.add(log)
        self.db.flush()
        return log

    def list_for_run(self, tenant_id: uuid.UUID, workflow_run_id: uuid.UUID) -> list[WorkflowStepLog]:
        return list(
            self.db.execute(
                select(WorkflowStepLog)
                .where(WorkflowStepLog.tenant_id == tenant_id, WorkflowStepLog.workflow_run_id == workflow_run_id)
                .order_by(WorkflowStepLog.executed_at)
            )
            .scalars()
            .all()
        )
