from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.appointment import APPOINTMENT_LOCATION_TYPES, APPOINTMENT_STATUSES, Appointment
from app.models.lead import Lead
from app.repositories.appointment import AppointmentFilters, AppointmentPage, AppointmentRepository
from app.repositories.branch import BranchRepository
from app.repositories.communication import MessageLogRepository
from app.repositories.lead import LeadRepository
from app.repositories.membership import MembershipRepository
from app.repositories.service import ServiceRepository
from app.repositories.tenant import TenantRepository
from app.services.availability_service import AvailabilityService
from app.services.email_service import EmailMessage, send_email_safely
from app.services.errors import NotFoundError, ValidationError
from app.services.message_template_service import MessageTemplateService


class AppointmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.appointments = AppointmentRepository(db)
        self.leads = LeadRepository(db)
        self.memberships = MembershipRepository(db)
        self.branches = BranchRepository(db)
        self.services_repo = ServiceRepository(db)
        self.tenants = TenantRepository(db)
        self.availability = AvailabilityService(db)
        self.message_templates = MessageTemplateService(db)
        self.message_logs = MessageLogRepository(db)

    def get_or_404(self, tenant_id: uuid.UUID, appointment_id: uuid.UUID) -> Appointment:
        appointment = self.appointments.get_by_id_for_tenant(tenant_id, appointment_id)
        if appointment is None:
            raise NotFoundError("Appointment not found.")
        return appointment

    def list(
        self, tenant_id: uuid.UUID, *, filters: AppointmentFilters, page: int, page_size: int
    ) -> AppointmentPage:
        return self.appointments.list_for_tenant(
            tenant_id, filters=filters, page=page, page_size=page_size
        )

    def _assert_available(
        self,
        tenant_id: uuid.UUID,
        *,
        assigned_membership_id: uuid.UUID | None,
        starts_at: datetime,
        ends_at: datetime,
        exclude_appointment_id: uuid.UUID | None = None,
    ) -> None:
        if assigned_membership_id is None:
            return
        overlapping = self.appointments.list_overlapping(
            tenant_id,
            assigned_membership_id=assigned_membership_id,
            starts_at=starts_at,
            ends_at=ends_at,
            exclude_appointment_id=exclude_appointment_id,
        )
        if overlapping:
            raise ValidationError(
                "This staff member already has an appointment in that time range."
            )

    def create(
        self,
        tenant_id: uuid.UUID,
        *,
        created_by_user_id: uuid.UUID | None,
        lead_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
        assigned_membership_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        service_id: uuid.UUID | None = None,
        location_type: str = "in_person",
        notes: str | None = None,
    ) -> Appointment:
        if ends_at <= starts_at:
            raise ValidationError("Appointment end time must be after the start time.")
        if location_type not in APPOINTMENT_LOCATION_TYPES:
            raise ValidationError(f"Unknown location type '{location_type}'.")
        lead = self.leads.get_by_id_for_tenant(tenant_id, lead_id)
        if lead is None:
            raise ValidationError("Lead does not belong to this tenant.")
        if assigned_membership_id is not None:
            if self.memberships.get_by_id_for_tenant(tenant_id, assigned_membership_id) is None:
                raise ValidationError("Assignee does not belong to this tenant.")
        if (
            branch_id is not None
            and self.branches.get_by_id_for_tenant(tenant_id, branch_id) is None
        ):
            raise ValidationError("Branch does not belong to this tenant.")
        if (
            service_id is not None
            and self.services_repo.get_by_id_for_tenant(tenant_id, service_id) is None
        ):
            raise ValidationError("Service does not belong to this tenant.")

        self._assert_available(
            tenant_id,
            assigned_membership_id=assigned_membership_id,
            starts_at=starts_at,
            ends_at=ends_at,
        )

        appointment = self.appointments.create(
            tenant_id=tenant_id,
            lead_id=lead_id,
            assigned_membership_id=assigned_membership_id,
            branch_id=branch_id,
            service_id=service_id,
            starts_at=starts_at,
            ends_at=ends_at,
            location_type=location_type,
            notes=notes,
            created_by_user_id=created_by_user_id,
        )
        self._send_confirmation_email(tenant_id, appointment, lead)
        return appointment

    def reschedule(
        self,
        tenant_id: uuid.UUID,
        appointment_id: uuid.UUID,
        *,
        starts_at: datetime,
        ends_at: datetime,
    ) -> Appointment:
        if ends_at <= starts_at:
            raise ValidationError("Appointment end time must be after the start time.")
        appointment = self.get_or_404(tenant_id, appointment_id)
        self._assert_available(
            tenant_id,
            assigned_membership_id=appointment.assigned_membership_id,
            starts_at=starts_at,
            ends_at=ends_at,
            exclude_appointment_id=appointment.id,
        )
        return self.appointments.update(appointment, starts_at=starts_at, ends_at=ends_at)

    def cancel(
        self, tenant_id: uuid.UUID, appointment_id: uuid.UUID, *, reason: str
    ) -> Appointment:
        if not reason.strip():
            raise ValidationError("A cancellation reason is required.")
        appointment = self.get_or_404(tenant_id, appointment_id)
        return self.appointments.update(appointment, status="cancelled", cancellation_reason=reason)

    def complete(self, tenant_id: uuid.UUID, appointment_id: uuid.UUID) -> Appointment:
        appointment = self.get_or_404(tenant_id, appointment_id)
        return self.appointments.update(appointment, status="completed")

    def mark_no_show(self, tenant_id: uuid.UUID, appointment_id: uuid.UUID) -> Appointment:
        appointment = self.get_or_404(tenant_id, appointment_id)
        return self.appointments.update(appointment, status="no_show")

    def confirm(self, tenant_id: uuid.UUID, appointment_id: uuid.UUID) -> Appointment:
        appointment = self.get_or_404(tenant_id, appointment_id)
        if appointment.status not in APPOINTMENT_STATUSES:
            raise ValidationError("Invalid appointment status.")
        return self.appointments.update(appointment, status="confirmed")

    # -- communications --------------------------------------------------

    def _send_confirmation_email(
        self, tenant_id: uuid.UUID, appointment: Appointment, lead: Lead
    ) -> None:
        if not lead.email:
            return
        tenant = self.tenants.get_by_id(tenant_id)
        rendered = self.message_templates.render(
            tenant_id,
            "appointment_confirmation",
            {
                "first_name": lead.first_name,
                "tenant_name": tenant.name if tenant else "",
                "appointment_time": appointment.starts_at.isoformat(),
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
        except Exception as exc:  # noqa: BLE001 - a delivery failure must not break booking
            status = "failed"
            error_message = str(exc)
        self.message_logs.record(
            tenant_id=tenant_id,
            template_key="appointment_confirmation",
            channel="email",
            recipient=lead.email,
            status=status,
            lead_id=lead.id,
            error_message=error_message,
        )
