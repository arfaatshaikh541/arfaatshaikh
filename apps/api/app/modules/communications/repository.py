import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.communications.models import EmailDeliveryLog, EmailDeliveryStatus, EmailTemplate, EmailTriggerEvent


class EmailTemplateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, template_id: uuid.UUID) -> EmailTemplate | None:
        return self.db.execute(
            select(EmailTemplate).where(EmailTemplate.tenant_id == tenant_id, EmailTemplate.id == template_id)
        ).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[EmailTemplate]:
        return list(self.db.execute(select(EmailTemplate).where(EmailTemplate.tenant_id == tenant_id)).scalars().all())

    def get_active_by_trigger(
        self, tenant_id: uuid.UUID, trigger_event: EmailTriggerEvent, *, stage_outcome: str | None = None
    ) -> EmailTemplate | None:
        stmt = select(EmailTemplate).where(
            EmailTemplate.tenant_id == tenant_id, EmailTemplate.trigger_event == trigger_event, EmailTemplate.is_active.is_(True)
        )
        if trigger_event == EmailTriggerEvent.STAGE_CHANGED:
            stmt = stmt.where(EmailTemplate.trigger_stage_outcome == stage_outcome)
        return self.db.execute(stmt).scalars().first()

    def create(
        self, *, tenant_id: uuid.UUID, name: str, trigger_event: EmailTriggerEvent, subject: str, body_text: str,
        body_html: str | None = None, trigger_stage_outcome: str | None = None,
    ) -> EmailTemplate:
        template = EmailTemplate(
            tenant_id=tenant_id, name=name, trigger_event=trigger_event, subject=subject, body_text=body_text,
            body_html=body_html, trigger_stage_outcome=trigger_stage_outcome,
        )
        self.db.add(template)
        self.db.flush()
        return template


class EmailDeliveryLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, log_id: uuid.UUID) -> EmailDeliveryLog | None:
        return self.db.execute(
            select(EmailDeliveryLog).where(EmailDeliveryLog.tenant_id == tenant_id, EmailDeliveryLog.id == log_id)
        ).scalar_one_or_none()

    def list_for_tenant(
        self, tenant_id: uuid.UUID, *, lead_id: uuid.UUID | None = None, status: EmailDeliveryStatus | None = None
    ) -> list[EmailDeliveryLog]:
        stmt = select(EmailDeliveryLog).where(EmailDeliveryLog.tenant_id == tenant_id)
        if lead_id:
            stmt = stmt.where(EmailDeliveryLog.lead_id == lead_id)
        if status:
            stmt = stmt.where(EmailDeliveryLog.status == status)
        return list(self.db.execute(stmt.order_by(EmailDeliveryLog.created_at.desc())).scalars().all())

    def list_failed_for_retry(self, tenant_id: uuid.UUID | None, *, max_attempts: int) -> list[EmailDeliveryLog]:
        stmt = select(EmailDeliveryLog).where(
            EmailDeliveryLog.status == EmailDeliveryStatus.FAILED, EmailDeliveryLog.attempt_count < max_attempts
        )
        if tenant_id is not None:
            stmt = stmt.where(EmailDeliveryLog.tenant_id == tenant_id)
        return list(self.db.execute(stmt).scalars().all())

    def create(
        self, *, tenant_id: uuid.UUID, template_id: uuid.UUID | None, lead_id: uuid.UUID | None, recipient: str,
        subject: str, body_text: str, body_html: str | None, created_at: datetime,
    ) -> EmailDeliveryLog:
        log = EmailDeliveryLog(
            tenant_id=tenant_id, template_id=template_id, lead_id=lead_id, recipient=recipient, subject=subject,
            body_text=body_text, body_html=body_html, created_at=created_at,
        )
        self.db.add(log)
        self.db.flush()
        return log
