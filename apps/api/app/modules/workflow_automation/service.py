"""The workflow automation engine.

Execution model: every step — including `delay_minutes=0` ones — is
picked up only by the Celery beat sweep (`process_due_steps_for_tenant`,
called from `apps/worker/app/tasks/workflow_automation.py`), never run
synchronously at trigger time. This mirrors Milestone 3/4's reminder
sweeps exactly and keeps a single execution code path instead of two
(trigger-time-synchronous vs. sweep-driven), at the cost of "immediate"
steps taking up to one sweep interval (15 minutes) to actually run — see
the project status doc's known limitations.
"""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, UsageLimitExceededError, ValidationFailedError
from app.modules.workflow_automation.conditions import evaluate_all
from app.modules.workflow_automation.models import (
    Workflow,
    WorkflowActionType,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowStep,
    WorkflowStepLogStatus,
    WorkflowTriggerEvent,
)
from app.modules.workflow_automation.repository import (
    WorkflowRepository,
    WorkflowRunRepository,
    WorkflowStepLogRepository,
    WorkflowStepRepository,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


# --- Workflow / step CRUD -------------------------------------------------

def list_workflows(db: Session, tenant_id: uuid.UUID) -> list[Workflow]:
    return WorkflowRepository(db).list_for_tenant(tenant_id)


def get_workflow_or_404(db: Session, tenant_id: uuid.UUID, workflow_id: uuid.UUID) -> Workflow:
    workflow = WorkflowRepository(db).get(tenant_id, workflow_id)
    if workflow is None:
        raise NotFoundError("Workflow not found.")
    return workflow


def create_workflow(
    db: Session, *, tenant_id: uuid.UUID, name: str, description: str, trigger_event: WorkflowTriggerEvent,
    trigger_config: dict, conditions: list,
) -> Workflow:
    for condition in conditions:
        if "field" not in condition or "operator" not in condition:
            raise ValidationFailedError("Each condition needs a 'field' and an 'operator'.", code="invalid_condition")
    existing = WorkflowRepository(db).list_for_tenant(tenant_id)
    return WorkflowRepository(db).create(
        tenant_id=tenant_id, name=name, description=description, trigger_event=trigger_event,
        trigger_config=trigger_config, conditions=conditions, sort_order=len(existing),
    )


def update_workflow(db: Session, *, tenant_id: uuid.UUID, workflow: Workflow, updates: dict) -> Workflow:
    for field, value in updates.items():
        if value is not None:
            setattr(workflow, field, value)
    db.add(workflow)
    db.flush()
    return workflow


def list_steps(db: Session, tenant_id: uuid.UUID, workflow_id: uuid.UUID) -> list[WorkflowStep]:
    return WorkflowStepRepository(db).list_for_workflow(tenant_id, workflow_id)


def add_step(
    db: Session, *, tenant_id: uuid.UUID, workflow_id: uuid.UUID, delay_minutes: int, action_type: WorkflowActionType, action_config: dict
) -> WorkflowStep:
    if delay_minutes < 0:
        raise ValidationFailedError("delay_minutes cannot be negative.", code="invalid_delay")
    existing = WorkflowStepRepository(db).list_for_workflow(tenant_id, workflow_id)
    return WorkflowStepRepository(db).create(
        tenant_id=tenant_id, workflow_id=workflow_id, sequence_order=len(existing), delay_minutes=delay_minutes,
        action_type=action_type, action_config=action_config,
    )


def list_runs(db: Session, tenant_id: uuid.UUID, *, workflow_id: uuid.UUID | None = None, lead_id: uuid.UUID | None = None) -> list[WorkflowRun]:
    repo = WorkflowRunRepository(db)
    if workflow_id is not None:
        return repo.list_for_workflow(tenant_id, workflow_id)
    if lead_id is not None:
        return repo.list_for_lead(tenant_id, lead_id)
    return []


def list_run_step_logs(db: Session, tenant_id: uuid.UUID, workflow_run_id: uuid.UUID):
    return WorkflowStepLogRepository(db).list_for_run(tenant_id, workflow_run_id)


# --- Trigger matching -------------------------------------------------

def _trigger_config_matches(trigger_event: WorkflowTriggerEvent, trigger_config: dict, context: dict) -> bool:
    if trigger_event == WorkflowTriggerEvent.STAGE_CHANGED:
        wanted = trigger_config.get("stage_name")
        return wanted is None or wanted == context.get("stage_name")
    if trigger_event == WorkflowTriggerEvent.TAG_ADDED:
        wanted = trigger_config.get("tag_name")
        return wanted is None or wanted == context.get("tag_name")
    if trigger_event == WorkflowTriggerEvent.SCORE_THRESHOLD_REACHED:
        min_score = trigger_config.get("min_score")
        score = context.get("score")
        return min_score is None or (score is not None and score >= min_score)
    if trigger_event in (WorkflowTriggerEvent.APPOINTMENT_BOOKED, WorkflowTriggerEvent.APPOINTMENT_COMPLETED):
        wanted = trigger_config.get("appointment_type_name")
        return wanted is None or wanted == context.get("appointment_type_name")
    return True  # LEAD_CREATED: no trigger_config to narrow


def evaluate_triggers_for_lead(
    db: Session, *, tenant_id: uuid.UUID, trigger_event: WorkflowTriggerEvent, lead, context: dict | None = None
) -> int:
    """Matches active workflows for this trigger event against the lead,
    and creates a `WorkflowRun` for each match. Soft-fails (returns 0
    without raising) when the `workflow_automation` module is disabled —
    a workflow trigger must never block the lead/stage/tag/appointment
    action that fired it. Returns the number of runs created."""
    from app.modules.entitlements import service as entitlements_service

    entitlements = entitlements_service.resolve_entitlements(db, tenant_id)
    if not entitlements.module_enabled("workflow_automation"):
        return 0

    context = context or {}
    created = 0
    for workflow in WorkflowRepository(db).list_active_by_trigger(tenant_id, trigger_event):
        if not _trigger_config_matches(trigger_event, workflow.trigger_config, context):
            continue
        if not evaluate_all(lead, workflow.conditions):
            continue
        steps = WorkflowStepRepository(db).list_for_workflow(tenant_id, workflow.id)
        if not steps:
            continue
        try:
            entitlements_service.check_and_increment_usage(db, tenant_id, metric_code="automation_runs", feature_code="automation_runs")
        except UsageLimitExceededError:
            continue

        now = _utcnow()
        WorkflowRunRepository(db).create(
            tenant_id=tenant_id, workflow_id=workflow.id, lead_id=lead.id,
            next_run_at=now + timedelta(minutes=steps[0].delay_minutes), triggered_at=now,
        )
        created += 1
    return created


# --- Step execution -------------------------------------------------

def _lead_merge_context(lead, tenant) -> dict:
    return {
        "first_name": lead.first_name, "last_name": lead.last_name, "company": lead.company or "",
        "reference_number": lead.reference_number, "tenant_name": tenant.name,
    }


def _execute_step(db: Session, *, tenant_id: uuid.UUID, lead, step: WorkflowStep) -> str:
    if step.action_type == WorkflowActionType.SEND_EMAIL_TEMPLATE:
        template_id = step.action_config.get("template_id")
        if not template_id or not lead.email:
            return "Skipped: no template configured or lead has no email."
        from app.modules.communications.service import send_template_by_id
        from app.modules.tenancy import service as tenancy_service

        tenant = tenancy_service.get_tenant_or_404(db, tenant_id)
        sent = send_template_by_id(
            db, tenant_id=tenant_id, template_id=uuid.UUID(template_id), recipient=lead.email, lead_id=lead.id,
            context=_lead_merge_context(lead, tenant),
        )
        return "Email sent." if sent is not None else "Email soft-skipped (module disabled, limit reached, or template inactive)."

    if step.action_type == WorkflowActionType.CREATE_TASK:
        from app.modules.crm.service import create_task

        due_in_hours = step.action_config.get("due_in_hours", 24)
        assigned_user_id = step.action_config.get("assigned_user_id")
        task = create_task(
            db, tenant_id=tenant_id, lead_id=lead.id, title=step.action_config.get("title", "Follow up"),
            description=step.action_config.get("description", ""),
            assigned_user_id=uuid.UUID(assigned_user_id) if assigned_user_id else None,
            created_by=None, due_at=_utcnow() + timedelta(hours=due_in_hours), source="workflow",
        )
        return f"Task created: {task.title}"

    if step.action_type == WorkflowActionType.CHANGE_STAGE:
        from app.modules.crm.repository import PipelineRepository
        from app.modules.crm.service import change_stage

        stage_name = step.action_config.get("stage_name")
        if not lead.pipeline_id or not stage_name:
            return "Skipped: lead has no pipeline or step has no stage_name."
        stage = PipelineRepository(db).get_stage_by_name(tenant_id, lead.pipeline_id, stage_name)
        if stage is None:
            return f"Skipped: stage '{stage_name}' not found in this lead's pipeline."
        change_stage(db, tenant_id=tenant_id, lead_id=lead.id, new_stage_id=stage.id, actor_id=None)
        return f"Stage changed to {stage_name}."

    if step.action_type == WorkflowActionType.ADD_TAG:
        from app.modules.crm.service import add_tag_to_lead

        tag_name = step.action_config.get("tag_name")
        if not tag_name:
            return "Skipped: step has no tag_name."
        add_tag_to_lead(db, tenant_id=tenant_id, lead_id=lead.id, tag_name=tag_name, actor_id=None)
        return f"Tag added: {tag_name}."

    if step.action_type == WorkflowActionType.START_ONBOARDING_CASE:
        from app.modules.onboarding.service import start_case

        template_id = step.action_config.get("template_id")
        if not template_id:
            return "Skipped: no onboarding template configured."
        case = start_case(db, tenant_id=tenant_id, lead_id=lead.id, template_id=uuid.UUID(template_id), created_by=None)
        return f"Onboarding case started: {case.name}"

    return f"Unknown action type: {step.action_type}"


def process_due_steps_for_tenant(db: Session, *, tenant_id: uuid.UUID, before: datetime) -> int:
    from app.modules.leads.repository import LeadRepository

    processed = 0
    for run in WorkflowRunRepository(db).list_due(before=before, tenant_id=tenant_id):
        steps = WorkflowStepRepository(db).list_for_workflow(tenant_id, run.workflow_id)
        if run.current_step_index >= len(steps):
            run.status = WorkflowRunStatus.COMPLETED
            run.next_run_at = None
            db.add(run)
            continue

        lead = LeadRepository(db).get(tenant_id, run.lead_id)
        if lead is None:
            run.status = WorkflowRunStatus.CANCELLED
            run.next_run_at = None
            db.add(run)
            continue

        step = steps[run.current_step_index]
        try:
            summary = _execute_step(db, tenant_id=tenant_id, lead=lead, step=step)
            WorkflowStepLogRepository(db).create(
                tenant_id=tenant_id, workflow_run_id=run.id, step_id=step.id, status=WorkflowStepLogStatus.EXECUTED, result_summary=summary
            )
        except Exception as exc:  # noqa: BLE001 — one failing step must not crash the sweep or strand the run
            WorkflowStepLogRepository(db).create(
                tenant_id=tenant_id, workflow_run_id=run.id, step_id=step.id, status=WorkflowStepLogStatus.FAILED, result_summary=str(exc)[:500]
            )

        run.current_step_index += 1
        if run.current_step_index >= len(steps):
            run.status = WorkflowRunStatus.COMPLETED
            run.next_run_at = None
        else:
            run.next_run_at = _utcnow() + timedelta(minutes=steps[run.current_step_index].delay_minutes)
        db.add(run)
        processed += 1
    return processed
