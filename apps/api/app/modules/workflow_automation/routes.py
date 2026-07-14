import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.dependencies.entitlements import require_module
from app.dependencies.permissions import require_permission
from app.modules.workflow_automation import service as workflow_service
from app.modules.workflow_automation.schemas import AddStepRequest, CreateWorkflowRequest, UpdateWorkflowRequest

router = APIRouter(prefix="/tenant/workflows", tags=["workflow-automation"])


def _workflow_to_dict(workflow) -> dict:
    return {
        "id": str(workflow.id), "name": workflow.name, "description": workflow.description,
        "trigger_event": workflow.trigger_event.value, "trigger_config": workflow.trigger_config,
        "conditions": workflow.conditions, "is_active": workflow.is_active, "sort_order": workflow.sort_order,
    }


def _step_to_dict(step) -> dict:
    return {
        "id": str(step.id), "sequence_order": step.sequence_order, "delay_minutes": step.delay_minutes,
        "action_type": step.action_type.value, "action_config": step.action_config,
    }


def _run_to_dict(run) -> dict:
    return {
        "id": str(run.id), "workflow_id": str(run.workflow_id), "lead_id": str(run.lead_id), "status": run.status.value,
        "current_step_index": run.current_step_index, "next_run_at": run.next_run_at.isoformat() if run.next_run_at else None,
        "triggered_at": run.triggered_at.isoformat(),
    }


@router.get("")
def list_workflows(
    ctx: TenantContext = Depends(require_permission("workflows.view")),
    _mod: TenantContext = Depends(require_module("workflow_automation")), db: Session = Depends(get_db),
) -> list[dict]:
    return [_workflow_to_dict(w) for w in workflow_service.list_workflows(db, ctx.tenant_id)]


@router.post("", status_code=201)
def create_workflow(
    payload: CreateWorkflowRequest, ctx: TenantContext = Depends(require_permission("workflows.manage")),
    _mod: TenantContext = Depends(require_module("workflow_automation")), db: Session = Depends(get_db),
) -> dict:
    workflow = workflow_service.create_workflow(
        db, tenant_id=ctx.tenant_id, name=payload.name, description=payload.description, trigger_event=payload.trigger_event,
        trigger_config=payload.trigger_config, conditions=[c.model_dump() for c in payload.conditions],
    )
    return _workflow_to_dict(workflow)


@router.patch("/{workflow_id}")
def update_workflow(
    workflow_id: uuid.UUID, payload: UpdateWorkflowRequest, ctx: TenantContext = Depends(require_permission("workflows.manage")),
    _mod: TenantContext = Depends(require_module("workflow_automation")), db: Session = Depends(get_db),
) -> dict:
    workflow = workflow_service.get_workflow_or_404(db, ctx.tenant_id, workflow_id)
    updates = payload.model_dump(exclude_unset=True)
    if "conditions" in updates and updates["conditions"] is not None:
        updates["conditions"] = [c if isinstance(c, dict) else c.model_dump() for c in updates["conditions"]]
    updated = workflow_service.update_workflow(db, tenant_id=ctx.tenant_id, workflow=workflow, updates=updates)
    return _workflow_to_dict(updated)


@router.get("/{workflow_id}/steps")
def list_steps(
    workflow_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("workflows.view")),
    _mod: TenantContext = Depends(require_module("workflow_automation")), db: Session = Depends(get_db),
) -> list[dict]:
    workflow_service.get_workflow_or_404(db, ctx.tenant_id, workflow_id)
    return [_step_to_dict(s) for s in workflow_service.list_steps(db, ctx.tenant_id, workflow_id)]


@router.post("/{workflow_id}/steps", status_code=201)
def add_step(
    workflow_id: uuid.UUID, payload: AddStepRequest, ctx: TenantContext = Depends(require_permission("workflows.manage")),
    _mod: TenantContext = Depends(require_module("workflow_automation")), db: Session = Depends(get_db),
) -> dict:
    workflow_service.get_workflow_or_404(db, ctx.tenant_id, workflow_id)
    step = workflow_service.add_step(
        db, tenant_id=ctx.tenant_id, workflow_id=workflow_id, delay_minutes=payload.delay_minutes,
        action_type=payload.action_type, action_config=payload.action_config,
    )
    return _step_to_dict(step)


@router.get("/{workflow_id}/runs")
def list_runs(
    workflow_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("workflows.view")),
    _mod: TenantContext = Depends(require_module("workflow_automation")), db: Session = Depends(get_db),
) -> list[dict]:
    workflow_service.get_workflow_or_404(db, ctx.tenant_id, workflow_id)
    return [_run_to_dict(r) for r in workflow_service.list_runs(db, ctx.tenant_id, workflow_id=workflow_id)]


@router.get("/runs/{run_id}/logs")
def list_run_logs(
    run_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("workflows.view")),
    _mod: TenantContext = Depends(require_module("workflow_automation")), db: Session = Depends(get_db),
) -> list[dict]:
    return [
        {
            "id": str(log.id), "step_id": str(log.step_id), "status": log.status.value,
            "result_summary": log.result_summary, "executed_at": log.executed_at.isoformat(),
        }
        for log in workflow_service.list_run_step_logs(db, ctx.tenant_id, run_id)
    ]
