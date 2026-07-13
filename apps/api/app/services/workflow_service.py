"""Module 12: tenant-configurable automation.

WHEN trigger_type fires AND every condition matches, THEN run each
action in order. Trigger types, condition fields/operators, and action
types are all closed enums (see app.models.workflow) matched with plain
if/elif dispatch - there is no eval/exec, no dynamic import, and no
user-supplied code string anywhere in this file. See
docs/architecture/erd-summary-m4.md.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.lead import Lead
from app.models.workflow import (
    WORKFLOW_ACTION_TYPES,
    WORKFLOW_CONDITION_FIELDS,
    WORKFLOW_CONDITION_OPERATORS,
    WORKFLOW_TRIGGER_TYPES,
    WorkflowExecutionLog,
    WorkflowRule,
)
from app.repositories.communication import MessageLogRepository, NotificationRepository
from app.repositories.lead import LeadTagRepository
from app.repositories.membership import MembershipRepository
from app.repositories.tenant import TenantRepository
from app.repositories.user import UserRepository
from app.repositories.workflow import WorkflowExecutionLogRepository, WorkflowRuleRepository
from app.services.email_service import EmailMessage, send_email_safely
from app.services.errors import NotFoundError, ValidationError
from app.services.message_template_service import MessageTemplateService
from app.services.task_service import TaskService


def _condition_matches(condition: dict, lead: Lead, context: dict) -> bool:
    field = condition.get("field")
    operator = condition.get("operator", "equals")
    expected = condition.get("value")

    if field == "to_stage_slug":
        actual = context.get("to_stage_slug")
    elif field == "service_id":
        actual = str(lead.service_id) if lead.service_id else None
    elif field == "source":
        actual = lead.source
    elif field == "priority":
        actual = lead.priority
    elif field == "estimated_value":
        actual = lead.estimated_value
    else:
        return False

    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected
    if operator == "at_least":
        return actual is not None and expected is not None and float(actual) >= float(expected)
    return False


class WorkflowService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.rules = WorkflowRuleRepository(db)
        self.logs = WorkflowExecutionLogRepository(db)
        self.memberships = MembershipRepository(db)
        self.users = UserRepository(db)
        self.tenants = TenantRepository(db)
        self.tags = LeadTagRepository(db)
        self.notifications = NotificationRepository(db)
        self.message_logs = MessageLogRepository(db)
        self.message_templates = MessageTemplateService(db)
        self.tasks = TaskService(db)

    # -- evaluation --------------------------------------------------------

    def evaluate_triggers(
        self,
        tenant_id: uuid.UUID,
        *,
        trigger_type: str,
        lead: Lead,
        context: dict | None = None,
    ) -> list[WorkflowRule]:
        context = context or {}
        active_rules = self.rules.list_for_tenant(
            tenant_id, trigger_type=trigger_type, active_only=True
        )
        fired: list[WorkflowRule] = []
        for rule in active_rules:
            if not all(_condition_matches(c, lead, context) for c in rule.conditions):
                continue
            actions_taken = [
                self._execute_action(action, tenant_id, lead) for action in rule.actions
            ]
            self.logs.record(
                tenant_id=tenant_id,
                workflow_rule_id=rule.id,
                lead_id=lead.id,
                trigger_type=trigger_type,
                actions_taken=actions_taken,
            )
            fired.append(rule)
        return fired

    def _execute_action(self, action: dict, tenant_id: uuid.UUID, lead: Lead) -> dict:
        action_type = action.get("type")
        try:
            if action_type == "create_task":
                self._run_create_task(action, tenant_id, lead)
            elif action_type == "send_email":
                self._run_send_email(action, tenant_id, lead)
            elif action_type == "add_tag":
                self._run_add_tag(action, lead)
            elif action_type == "create_notification":
                self._run_create_notification(action, tenant_id, lead)
            else:
                return {"type": action_type, "result": "skipped_unknown_action_type"}
        except Exception as exc:  # noqa: BLE001 - one failing action must not block the rest
            return {"type": action_type, "result": "failed", "error": str(exc)}
        return {"type": action_type, "result": "ok"}

    def _run_create_task(self, action: dict, tenant_id: uuid.UUID, lead: Lead) -> None:
        due_offset_hours = action.get("due_offset_hours")
        self.tasks.create(
            tenant_id,
            created_by_user_id=None,
            title=action.get("title", "Follow up"),
            description=action.get("description"),
            lead_id=lead.id,
            assigned_membership_id=lead.assigned_membership_id
            if action.get("assign_to") == "assignee"
            else None,
            priority=action.get("priority", "normal"),
            due_at=(utcnow() + timedelta(hours=due_offset_hours)) if due_offset_hours else None,
        )

    def _run_send_email(self, action: dict, tenant_id: uuid.UUID, lead: Lead) -> None:
        template_key = action.get("template_key")
        if not lead.email or not template_key:
            return
        tenant = self.tenants.get_by_id(tenant_id)
        rendered = self.message_templates.render(
            tenant_id,
            template_key,
            {
                "first_name": lead.first_name,
                "lead_name": f"{lead.first_name} {lead.last_name}".strip(),
                "tenant_name": tenant.name if tenant else "",
            },
        )
        if rendered is None:
            return
        status = "sent"
        error_message = None
        try:
            send_email_safely(
                EmailMessage(to=lead.email, subject=rendered.subject, text_body=rendered.body)
            )
        except Exception as exc:  # noqa: BLE001 - logged below, never raised further
            status = "failed"
            error_message = str(exc)
        self.message_logs.record(
            tenant_id=tenant_id,
            template_key=template_key,
            channel="email",
            recipient=lead.email,
            status=status,
            lead_id=lead.id,
            error_message=error_message,
        )

    def _run_add_tag(self, action: dict, lead: Lead) -> None:
        tag_id = action.get("tag_id")
        if not tag_id:
            return
        self.tags.add(lead_id=lead.id, tag_id=uuid.UUID(tag_id))

    def _run_create_notification(self, action: dict, tenant_id: uuid.UUID, lead: Lead) -> None:
        if action.get("target") != "assignee" or lead.assigned_membership_id is None:
            return
        membership = self.memberships.get_by_id_for_tenant(tenant_id, lead.assigned_membership_id)
        if membership is None:
            return
        self.notifications.create(
            tenant_id=tenant_id,
            user_id=membership.user_id,
            title=action.get("title", "Workflow notification"),
            body=f"{lead.first_name} {lead.last_name}".strip() or lead.reference_number,
            related_entity_type="lead",
            related_entity_id=str(lead.id),
        )

    # -- rule configuration --------------------------------------------

    def list_rules(self, tenant_id: uuid.UUID) -> list[WorkflowRule]:
        return self.rules.list_for_tenant(tenant_id)

    def create_rule(
        self,
        tenant_id: uuid.UUID,
        *,
        name: str,
        trigger_type: str,
        conditions: list,
        actions: list,
        sort_order: int = 0,
    ) -> WorkflowRule:
        if trigger_type not in WORKFLOW_TRIGGER_TYPES:
            raise ValidationError(f"Unknown trigger type '{trigger_type}'.")
        for condition in conditions:
            if condition.get("field") not in WORKFLOW_CONDITION_FIELDS:
                raise ValidationError(f"Unknown condition field '{condition.get('field')}'.")
            if condition.get("operator", "equals") not in WORKFLOW_CONDITION_OPERATORS:
                raise ValidationError(f"Unknown condition operator '{condition.get('operator')}'.")
        for action in actions:
            if action.get("type") not in WORKFLOW_ACTION_TYPES:
                raise ValidationError(f"Unknown action type '{action.get('type')}'.")
        return self.rules.create(
            tenant_id=tenant_id,
            name=name,
            trigger_type=trigger_type,
            conditions=conditions,
            actions=actions,
            sort_order=sort_order,
        )

    def update_rule(
        self, tenant_id: uuid.UUID, rule_id: uuid.UUID, **fields: object
    ) -> WorkflowRule:
        rule = self.rules.get_by_id_for_tenant(tenant_id, rule_id)
        if rule is None:
            raise NotFoundError("Workflow rule not found.")
        return self.rules.update(rule, **fields)

    def list_execution_log(
        self, tenant_id: uuid.UUID, *, limit: int = 100
    ) -> list[WorkflowExecutionLog]:
        return self.logs.list_for_tenant(tenant_id, limit=limit)

    def create_defaults_for_tenant(self, tenant_id: uuid.UUID) -> None:
        """Reproduces the Milestone 3 hardcoded qualified-stage-callback
        automation as a seeded default rule - see erd-summary-m4.md."""
        existing = self.rules.list_for_tenant(tenant_id, trigger_type="lead_stage_changed")
        if existing:
            return
        self.rules.create(
            tenant_id=tenant_id,
            name="Qualified lead callback",
            trigger_type="lead_stage_changed",
            conditions=[{"field": "to_stage_slug", "operator": "equals", "value": "qualified"}],
            actions=[
                {
                    "type": "create_task",
                    "title": "Call back qualified lead",
                    "description": (
                        "This lead was just marked as qualified - reach out within 24 hours."
                    ),
                    "priority": "high",
                    "due_offset_hours": 24,
                    "assign_to": "assignee",
                }
            ],
            sort_order=0,
        )
