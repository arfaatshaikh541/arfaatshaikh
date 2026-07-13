"""Public, unauthenticated enquiry form: config lookup + submission.

Security controls live here per docs/architecture and
docs/product/milestone-2-acceptance-criteria.md: honeypot, IP rate
limiting, idempotency, and duplicate flagging (never blocking).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.qualification import QualificationForm
from app.models.tenant import Tenant
from app.repositories.audit import AuditLogRepository
from app.repositories.public_submission import IdempotencyKeyRepository, PublicFormAttemptRepository
from app.repositories.qualification import QualificationFormRepository
from app.repositories.service import ServiceRepository
from app.repositories.tenant import TenantRepository
from app.services.errors import ConflictError, NotFoundError, RateLimitedError, ValidationError
from app.services.lead_service import AnswerInput, LeadService

RATE_LIMIT_WINDOW_MINUTES = 15
RATE_LIMIT_MAX_ATTEMPTS = 20


@dataclass
class FormConfig:
    tenant: Tenant
    services: list
    form: QualificationForm | None
    privacy_text: str | None


@dataclass
class SubmissionResult:
    reference_number: str
    accepted: bool


class PublicEnquiryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.tenants = TenantRepository(db)
        self.services_repo = ServiceRepository(db)
        self.forms = QualificationFormRepository(db)
        self.attempts = PublicFormAttemptRepository(db)
        self.idempotency = IdempotencyKeyRepository(db)
        self.leads = LeadService(db)
        self.audit = AuditLogRepository(db)

    def _resolve_active_tenant(self, public_key: uuid.UUID) -> Tenant:
        tenant = self.tenants.get_by_public_key(public_key)
        if tenant is None or tenant.status != "active":
            raise NotFoundError("Form not found.")
        return tenant

    def get_form_config(self, public_key: uuid.UUID) -> FormConfig:
        tenant = self._resolve_active_tenant(public_key)
        services = self.services_repo.list_for_tenant(tenant.id, active_only=True)
        form = self.forms.get_default_for_tenant(tenant.id)
        settings = self.tenants.get_settings(tenant.id)
        return FormConfig(
            tenant=tenant,
            services=services,
            form=form,
            privacy_text=settings.privacy_text if settings else None,
        )

    def submit(
        self,
        public_key: uuid.UUID,
        *,
        first_name: str,
        last_name: str,
        phone: str | None,
        email: str | None,
        company: str | None,
        service_id: uuid.UUID | None,
        preferred_contact_method: str | None,
        consent_given: bool,
        answers: list[AnswerInput],
        honeypot_value: str,
        utm: dict,
        referrer_url: str | None,
        ip_address: str,
        idempotency_key: str | None,
    ) -> SubmissionResult:
        tenant = self._resolve_active_tenant(public_key)

        recent = self.attempts.count_recent(
            tenant_id=tenant.id, ip_address=ip_address, window_minutes=RATE_LIMIT_WINDOW_MINUTES
        )
        if recent >= RATE_LIMIT_MAX_ATTEMPTS:
            raise RateLimitedError("Too many submissions. Please try again later.")
        self.attempts.record(tenant_id=tenant.id, ip_address=ip_address)

        request_fingerprint = {
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "email": email,
            "service_id": str(service_id) if service_id else None,
            "answers": [(str(a.question_id), a.value) for a in answers],
        }
        request_hash = hashlib.sha256(
            json.dumps(request_fingerprint, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

        if idempotency_key:
            existing = self.idempotency.get(tenant.id, idempotency_key)
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise ConflictError(
                        "Idempotency-Key was already used with a different payload."
                    )
                lead = self.leads.get_or_404(tenant.id, existing.lead_id)
                return SubmissionResult(reference_number=lead.reference_number, accepted=True)

        if honeypot_value:
            # Silently "succeed" without creating anything - never tip off bots.
            return SubmissionResult(reference_number="", accepted=False)

        if not consent_given:
            raise ValidationError("Consent is required to submit this form.")
        if not first_name.strip():
            raise ValidationError("First name is required.")

        if (
            service_id is not None
            and self.services_repo.get_by_id_for_tenant(tenant.id, service_id) is None
        ):
            raise ValidationError("Invalid service selected.")

        form = self.forms.get_default_for_tenant(tenant.id)
        question_lookup: dict[uuid.UUID, tuple[str, str]] = {}
        answers_by_question = {a.question_id: a for a in answers}
        if form:
            for question in form.questions:
                if not question.is_active:
                    continue
                question_lookup[question.id] = (
                    question.field_definition.label,
                    question.field_definition.field_type,
                )
                if question.is_required and question.id not in answers_by_question:
                    raise ValidationError(f"'{question.field_definition.label}' is required.")

        settings = self.tenants.get_settings(tenant.id)
        lead = self.leads.create(
            tenant.id,
            actor_user_id=None,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            company=company,
            service_id=service_id,
            source="public_form",
            preferred_contact_method=preferred_contact_method,
            consent_given=consent_given,
            consent_text_shown=settings.privacy_text if settings else None,
            utm=utm,
            referrer_url=referrer_url,
            answers=list(answers_by_question.values()),
            question_lookup=question_lookup,
        )

        if idempotency_key:
            self.idempotency.create(
                tenant_id=tenant.id, key=idempotency_key, request_hash=request_hash, lead_id=lead.id
            )

        return SubmissionResult(reference_number=lead.reference_number, accepted=True)
