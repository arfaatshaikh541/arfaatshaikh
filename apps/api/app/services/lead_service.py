from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.lead import Lead, LeadNote
from app.repositories.audit import AuditLogRepository
from app.repositories.branch import BranchRepository
from app.repositories.communication import MessageLogRepository
from app.repositories.lead import (
    LeadAnswerRepository,
    LeadFilters,
    LeadNoteRepository,
    LeadPage,
    LeadRepository,
    LeadStageHistoryRepository,
    LeadTagRepository,
)
from app.repositories.membership import MembershipRepository
from app.repositories.pipeline import LossReasonRepository, PipelineStageRepository, TagRepository
from app.repositories.service import ServiceRepository
from app.repositories.tenant import TenantRepository
from app.repositories.user import UserRepository
from app.services.assignment_service import AssignmentService
from app.services.email_service import EmailMessage, send_email_safely
from app.services.errors import NotFoundError, ValidationError
from app.services.message_template_service import MessageTemplateService
from app.services.notification_service import NotificationService
from app.services.scoring_service import ScoringService
from app.services.workflow_service import WorkflowService

REFERENCE_PREFIX = "LD"


@dataclass
class AnswerInput:
    question_id: uuid.UUID
    value: object


class LeadService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.leads = LeadRepository(db)
        self.answers = LeadAnswerRepository(db)
        self.notes = LeadNoteRepository(db)
        self.stage_history = LeadStageHistoryRepository(db)
        self.lead_tags = LeadTagRepository(db)
        self.stages = PipelineStageRepository(db)
        self.services_repo = ServiceRepository(db)
        self.branches = BranchRepository(db)
        self.memberships = MembershipRepository(db)
        self.tags = TagRepository(db)
        self.loss_reasons = LossReasonRepository(db)
        self.audit = AuditLogRepository(db)
        self.scoring = ScoringService(db)
        self.assignment = AssignmentService(db)
        self.tenants = TenantRepository(db)
        self.users = UserRepository(db)
        self.message_logs = MessageLogRepository(db)
        self.message_templates = MessageTemplateService(db)
        self.notifications = NotificationService(db)
        self.workflows = WorkflowService(db)

    # -- lookups -------------------------------------------------------

    def get_or_404(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> Lead:
        lead = self.leads.get_by_id_for_tenant(tenant_id, lead_id)
        if lead is None:
            raise NotFoundError("Lead not found.")
        return lead

    def list_leads(
        self, tenant_id: uuid.UUID, *, filters: LeadFilters, page: int, page_size: int
    ) -> LeadPage:
        return self.leads.list_for_tenant(
            tenant_id, filters=filters, page=page, page_size=page_size
        )

    def generate_reference_number(self, tenant_id: uuid.UUID) -> str:
        for _ in range(5):
            candidate = f"{REFERENCE_PREFIX}-{secrets.token_hex(4).upper()}"
            if self.leads.get_by_reference_for_tenant(tenant_id, candidate) is None:
                return candidate
        raise RuntimeError("Could not generate a unique lead reference number.")

    def check_duplicate(
        self, tenant_id: uuid.UUID, *, email: str | None, phone: str | None
    ) -> Lead | None:
        return self.leads.find_possible_duplicate(tenant_id, email=email, phone=phone)

    def _default_stage(self, tenant_id: uuid.UUID):  # type: ignore[no-untyped-def]
        stage = self.stages.get_by_slug_for_tenant(tenant_id, "new")
        if stage is None:
            stages = self.stages.list_for_tenant(tenant_id)
            if not stages:
                raise ValidationError("This tenant has no pipeline stages configured.")
            stage = stages[0]
        return stage

    # -- create ----------------------------------------------------------

    def create(
        self,
        tenant_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None,
        first_name: str,
        last_name: str = "",
        phone: str | None = None,
        email: str | None = None,
        company: str | None = None,
        service_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        source: str = "manual",
        priority: str = "standard",
        estimated_value: float | None = None,
        preferred_contact_method: str | None = None,
        consent_given: bool = False,
        consent_text_shown: str | None = None,
        utm: dict | None = None,
        referrer_url: str | None = None,
        answers: list[AnswerInput] | None = None,
        question_lookup: dict[uuid.UUID, tuple[str, str]] | None = None,
    ) -> Lead:
        if (
            service_id is not None
            and self.services_repo.get_by_id_for_tenant(tenant_id, service_id) is None
        ):
            raise ValidationError("Service does not belong to this tenant.")
        if (
            branch_id is not None
            and self.branches.get_by_id_for_tenant(tenant_id, branch_id) is None
        ):
            raise ValidationError("Branch does not belong to this tenant.")

        stage = self._default_stage(tenant_id)
        utm = utm or {}
        duplicate = self.check_duplicate(tenant_id, email=email, phone=phone)

        lead = Lead(
            tenant_id=tenant_id,
            reference_number=self.generate_reference_number(tenant_id),
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            company=company,
            service_id=service_id,
            branch_id=branch_id,
            stage_id=stage.id,
            source=source,
            priority=priority,
            estimated_value=estimated_value,
            preferred_contact_method=preferred_contact_method,
            consent_given=consent_given,
            consent_text_shown=consent_text_shown,
            consented_at=utcnow() if consent_given else None,
            utm_source=utm.get("utm_source"),
            utm_medium=utm.get("utm_medium"),
            utm_campaign=utm.get("utm_campaign"),
            utm_term=utm.get("utm_term"),
            utm_content=utm.get("utm_content"),
            referrer_url=referrer_url,
            is_possible_duplicate=duplicate is not None,
            duplicate_of_lead_id=duplicate.id if duplicate else None,
        )
        self.leads.create(lead)

        for answer in answers or []:
            label, field_type = (question_lookup or {}).get(
                answer.question_id, ("Unknown question", "short_text")
            )
            self.answers.create(
                lead_id=lead.id,
                question_id=answer.question_id,
                question_label_snapshot=label,
                field_type_snapshot=field_type,
                value=answer.value,
            )

        # Score after answers are attached: the answer_equals rule type
        # inspects lead.answers, and priority defaults to whatever the
        # scoring engine derives unless a caller later overrides it via
        # an explicit `priority` field on update().
        self.scoring.apply(tenant_id, lead)

        self.stage_history.create(
            lead_id=lead.id,
            from_stage_id=None,
            to_stage_id=stage.id,
            changed_by_user_id=actor_user_id,
        )
        self.audit.record(
            event_type="lead.created",
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            entity_type="lead",
            entity_id=str(lead.id),
            metadata={"source": source, "reference_number": lead.reference_number},
        )

        if lead.email:
            self._send_acknowledgement_email(tenant_id, lead)

        decision = self.assignment.auto_assign(tenant_id, lead)
        if decision.membership_id is not None:
            lead.assigned_membership_id = decision.membership_id
            self.db.flush()
            self.audit.record(
                event_type="lead.assigned",
                tenant_id=tenant_id,
                actor_user_id=None,
                entity_type="lead",
                entity_id=str(lead.id),
                metadata={
                    "assigned_membership_id": str(decision.membership_id),
                    "strategy": decision.strategy,
                    "rule_id": str(decision.rule_id) if decision.rule_id else None,
                    "automatic": True,
                },
            )
            self._send_assignment_alert(tenant_id, lead, decision.membership_id)
            self._run_workflows(tenant_id, trigger_type="lead_assigned", lead=lead)

        self._run_workflows(tenant_id, trigger_type="lead_created", lead=lead)

        return lead

    def _run_workflows(
        self, tenant_id: uuid.UUID, *, trigger_type: str, lead: Lead, context: dict | None = None
    ) -> None:
        fired = self.workflows.evaluate_triggers(
            tenant_id, trigger_type=trigger_type, lead=lead, context=context
        )
        if fired:
            self.audit.record(
                event_type="workflow.executed",
                tenant_id=tenant_id,
                actor_user_id=None,
                entity_type="lead",
                entity_id=str(lead.id),
                metadata={"trigger_type": trigger_type, "rule_ids": [str(r.id) for r in fired]},
            )

    # -- communications (Module 10) -----------------------------------------
    # Best-effort: a delivery failure here must never break lead creation, so
    # every send is wrapped and logged to MessageLogRepository (append-only)
    # rather than propagated. See docs/architecture/erd-summary-m3.md.

    def _lead_render_context(self, tenant_id: uuid.UUID, lead: Lead) -> dict[str, str]:
        tenant = self.tenants.get_by_id(tenant_id)
        service = (
            self.services_repo.get_by_id_for_tenant(tenant_id, lead.service_id)
            if lead.service_id
            else None
        )
        return {
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "lead_name": f"{lead.first_name} {lead.last_name}".strip(),
            "lead_email": lead.email or "",
            "lead_id": str(lead.id),
            "reference_number": lead.reference_number,
            "tenant_name": tenant.name if tenant else "",
            "service_name": service.name if service else "",
        }

    def _send_acknowledgement_email(self, tenant_id: uuid.UUID, lead: Lead) -> None:
        rendered = self.message_templates.render(
            tenant_id, "acknowledgement", self._lead_render_context(tenant_id, lead)
        )
        if rendered is None or not lead.email:
            return
        status = "sent"
        error_message = None
        try:
            send_email_safely(
                EmailMessage(to=lead.email, subject=rendered.subject, text_body=rendered.body)
            )
        except Exception as exc:  # noqa: BLE001 - delivery failure must not break lead creation
            status = "failed"
            error_message = str(exc)
        self.message_logs.record(
            tenant_id=tenant_id,
            template_key="acknowledgement",
            channel="email",
            recipient=lead.email,
            status=status,
            lead_id=lead.id,
            error_message=error_message,
        )

    def _send_assignment_alert(
        self, tenant_id: uuid.UUID, lead: Lead, membership_id: uuid.UUID
    ) -> None:
        membership = self.memberships.get_by_id_for_tenant(tenant_id, membership_id)
        if membership is None:
            return
        assignee = self.users.get_by_id(membership.user_id)
        if assignee is None:
            return

        self.notifications.create(
            tenant_id,
            user_id=assignee.id,
            title="New lead assigned to you",
            body=f"{lead.first_name} {lead.last_name}".strip() or lead.reference_number,
            related_entity_type="lead",
            related_entity_id=str(lead.id),
        )

        context = self._lead_render_context(tenant_id, lead)
        context["assignee_name"] = f"{assignee.first_name} {assignee.last_name}".strip()
        rendered = self.message_templates.render(tenant_id, "assignment_alert", context)
        if rendered is None:
            return
        status = "sent"
        error_message = None
        try:
            send_email_safely(
                EmailMessage(to=assignee.email, subject=rendered.subject, text_body=rendered.body)
            )
        except Exception as exc:  # noqa: BLE001 - delivery failure must not break lead creation
            status = "failed"
            error_message = str(exc)
        self.message_logs.record(
            tenant_id=tenant_id,
            template_key="assignment_alert",
            channel="email",
            recipient=assignee.email,
            status=status,
            lead_id=lead.id,
            error_message=error_message,
        )

    # -- update ------------------------------------------------------------

    def update(
        self,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        **fields: object,
    ) -> Lead:
        lead = self.get_or_404(tenant_id, lead_id)
        if "service_id" in fields and fields["service_id"] is not None:
            if self.services_repo.get_by_id_for_tenant(tenant_id, fields["service_id"]) is None:  # type: ignore[arg-type]
                raise ValidationError("Service does not belong to this tenant.")
        if "branch_id" in fields and fields["branch_id"] is not None:
            if self.branches.get_by_id_for_tenant(tenant_id, fields["branch_id"]) is None:  # type: ignore[arg-type]
                raise ValidationError("Branch does not belong to this tenant.")

        manual_priority_override = fields.get("priority") is not None
        scoring_relevant_fields = {"service_id", "estimated_value"}

        changed_fields = []
        for key, value in fields.items():
            if value is not None and getattr(lead, key, None) != value:
                setattr(lead, key, value)
                changed_fields.append(key)
        self.db.flush()

        # A caller who explicitly set `priority` is manually overriding the
        # scoring engine's band for this lead - don't immediately recompute
        # it back. Otherwise, if a scoring-relevant field changed, recompute
        # both score and priority so they never go stale.
        if (
            changed_fields
            and not manual_priority_override
            and scoring_relevant_fields.intersection(changed_fields)
        ):
            self.scoring.apply(tenant_id, lead)

        if changed_fields:
            self.audit.record(
                event_type="lead.updated",
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                entity_type="lead",
                entity_id=str(lead.id),
                metadata={"changed_fields": changed_fields},
            )
        return lead

    # -- stage / assignment / tags / notes ----------------------------------

    def change_stage(
        self,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        to_stage_id: uuid.UUID,
        loss_reason_id: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> Lead:
        lead = self.get_or_404(tenant_id, lead_id)
        to_stage = self.stages.get_by_id_for_tenant(tenant_id, to_stage_id)
        if to_stage is None:
            raise ValidationError("Pipeline stage does not belong to this tenant.")
        if to_stage.is_lost:
            if loss_reason_id is None:
                raise ValidationError(
                    "A loss reason is required when moving a lead to a lost stage."
                )
            if self.loss_reasons.get_by_id_for_tenant(tenant_id, loss_reason_id) is None:
                raise ValidationError("Loss reason does not belong to this tenant.")
            lead.loss_reason_id = loss_reason_id

        from_stage_id = lead.stage_id
        lead.stage_id = to_stage.id
        self.db.flush()

        self.stage_history.create(
            lead_id=lead.id,
            from_stage_id=from_stage_id,
            to_stage_id=to_stage.id,
            changed_by_user_id=actor_user_id,
            reason=reason,
        )
        self.audit.record(
            event_type="lead.stage_changed",
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            entity_type="lead",
            entity_id=str(lead.id),
            metadata={"from_stage_id": str(from_stage_id), "to_stage_id": str(to_stage.id)},
        )

        # Module 12: tenant-configurable workflow rules react to stage
        # changes (e.g. the default "qualified lead callback" rule seeded
        # for every tenant - see WorkflowService.create_defaults_for_tenant).
        if from_stage_id != to_stage.id:
            self._run_workflows(
                tenant_id,
                trigger_type="lead_stage_changed",
                lead=lead,
                context={"to_stage_slug": to_stage.slug},
            )

        return lead

    def assign(
        self,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        membership_id: uuid.UUID | None,
    ) -> Lead:
        lead = self.get_or_404(tenant_id, lead_id)
        if membership_id is not None:
            membership = self.memberships.get_by_id_for_tenant(tenant_id, membership_id)
            if membership is None:
                raise ValidationError("Assignee does not belong to this tenant.")
        lead.assigned_membership_id = membership_id
        self.db.flush()
        self.audit.record(
            event_type="lead.assigned",
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            entity_type="lead",
            entity_id=str(lead.id),
            metadata={"assigned_membership_id": str(membership_id) if membership_id else None},
        )
        if membership_id is not None:
            self._run_workflows(tenant_id, trigger_type="lead_assigned", lead=lead)
        return lead

    def add_note(
        self, tenant_id: uuid.UUID, lead_id: uuid.UUID, *, actor_user_id: uuid.UUID, body: str
    ) -> LeadNote:
        lead = self.get_or_404(tenant_id, lead_id)
        note = self.notes.create(lead_id=lead.id, author_user_id=actor_user_id, body=body)
        self.audit.record(
            event_type="lead.note_added",
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            entity_type="lead",
            entity_id=str(lead.id),
        )
        return note

    def add_tag(
        self,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        tag_id: uuid.UUID,
    ) -> None:
        lead = self.get_or_404(tenant_id, lead_id)
        if self.tags.get_by_id_for_tenant(tenant_id, tag_id) is None:
            raise ValidationError("Tag does not belong to this tenant.")
        added = self.lead_tags.add(lead_id=lead.id, tag_id=tag_id)
        if added:
            self.audit.record(
                event_type="lead.tag_added",
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                entity_type="lead",
                entity_id=str(lead.id),
                metadata={"tag_id": str(tag_id)},
            )

    def remove_tag(
        self,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
        tag_id: uuid.UUID,
    ) -> None:
        lead = self.get_or_404(tenant_id, lead_id)
        removed = self.lead_tags.remove(lead_id=lead.id, tag_id=tag_id)
        if removed:
            self.audit.record(
                event_type="lead.tag_removed",
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                entity_type="lead",
                entity_id=str(lead.id),
                metadata={"tag_id": str(tag_id)},
            )

    # -- bulk actions --------------------------------------------------------
    # Iterates and re-validates tenant ownership per item rather than a
    # single blanket query, so batching can never smuggle in a cross-tenant
    # id. See docs/product/milestone-2-acceptance-criteria.md.

    def bulk_change_stage(
        self,
        tenant_id: uuid.UUID,
        lead_ids: list[uuid.UUID],
        *,
        actor_user_id: uuid.UUID,
        to_stage_id: uuid.UUID,
        loss_reason_id: uuid.UUID | None = None,
    ) -> dict:
        updated, failed = [], []
        for lead_id in lead_ids:
            try:
                self.change_stage(
                    tenant_id,
                    lead_id,
                    actor_user_id=actor_user_id,
                    to_stage_id=to_stage_id,
                    loss_reason_id=loss_reason_id,
                )
                updated.append(lead_id)
            except (NotFoundError, ValidationError):
                failed.append(lead_id)
        return {"updated": updated, "failed": failed}

    def bulk_assign(
        self,
        tenant_id: uuid.UUID,
        lead_ids: list[uuid.UUID],
        *,
        actor_user_id: uuid.UUID,
        membership_id: uuid.UUID | None,
    ) -> dict:
        updated, failed = [], []
        for lead_id in lead_ids:
            try:
                self.assign(
                    tenant_id, lead_id, actor_user_id=actor_user_id, membership_id=membership_id
                )
                updated.append(lead_id)
            except (NotFoundError, ValidationError):
                failed.append(lead_id)
        return {"updated": updated, "failed": failed}

    # -- timeline ------------------------------------------------------------

    def get_timeline(self, tenant_id: uuid.UUID, lead_id: uuid.UUID):  # type: ignore[no-untyped-def]
        self.get_or_404(tenant_id, lead_id)
        return self.audit.list_for_entity(tenant_id, entity_type="lead", entity_id=str(lead_id))
