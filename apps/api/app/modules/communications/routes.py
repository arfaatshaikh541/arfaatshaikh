import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.db import get_db
from app.core.errors import NotFoundError
from app.dependencies.entitlements import require_module
from app.dependencies.permissions import require_permission
from app.modules.communications import service as communications_service
from app.modules.communications.models import EmailDeliveryStatus
from app.modules.communications.schemas import CreateEmailTemplateRequest, UpdateEmailTemplateRequest
from app.modules.identity.repository import UserRepository

router = APIRouter(prefix="/tenant/communications", tags=["communications"])


def _template_to_dict(template) -> dict:
    return {
        "id": str(template.id), "name": template.name, "trigger_event": template.trigger_event.value,
        "trigger_stage_outcome": template.trigger_stage_outcome, "subject": template.subject,
        "body_text": template.body_text, "body_html": template.body_html, "is_active": template.is_active,
    }


def _log_to_dict(log) -> dict:
    return {
        "id": str(log.id), "template_id": str(log.template_id) if log.template_id else None,
        "lead_id": str(log.lead_id) if log.lead_id else None, "recipient": log.recipient, "subject": log.subject,
        "status": log.status.value, "attempt_count": log.attempt_count, "last_error": log.last_error,
        "sent_at": log.sent_at.isoformat() if log.sent_at else None, "created_at": log.created_at.isoformat(),
    }


@router.get("/templates")
def list_templates(
    ctx: TenantContext = Depends(require_permission("communications.manage")),
    _mod: TenantContext = Depends(require_module("communications")), db: Session = Depends(get_db),
) -> list[dict]:
    return [_template_to_dict(t) for t in communications_service.list_templates(db, ctx.tenant_id)]


@router.post("/templates", status_code=201)
def create_template(
    payload: CreateEmailTemplateRequest,
    ctx: TenantContext = Depends(require_permission("communications.manage")),
    _mod: TenantContext = Depends(require_module("communications")), db: Session = Depends(get_db),
) -> dict:
    template = communications_service.create_template(
        db, tenant_id=ctx.tenant_id, name=payload.name, trigger_event=payload.trigger_event,
        subject=payload.subject, body_text=payload.body_text, body_html=payload.body_html,
        trigger_stage_outcome=payload.trigger_stage_outcome,
    )
    return _template_to_dict(template)


@router.patch("/templates/{template_id}")
def update_template(
    template_id: uuid.UUID, payload: UpdateEmailTemplateRequest,
    ctx: TenantContext = Depends(require_permission("communications.manage")),
    _mod: TenantContext = Depends(require_module("communications")), db: Session = Depends(get_db),
) -> dict:
    template = communications_service.get_template_or_404(db, ctx.tenant_id, template_id)
    updated = communications_service.update_template(db, tenant_id=ctx.tenant_id, template=template, updates=payload.model_dump(exclude_unset=True))
    return _template_to_dict(updated)


@router.post("/templates/{template_id}/send-test")
def send_test(
    template_id: uuid.UUID, ctx: TenantContext = Depends(require_permission("communications.manage")),
    _mod: TenantContext = Depends(require_module("communications")), db: Session = Depends(get_db),
) -> dict:
    """Always targets the requesting admin's own email address — never a
    client-supplied recipient — so this endpoint carries no
    open-mail-relay / spam risk."""
    template = communications_service.get_template_or_404(db, ctx.tenant_id, template_id)
    user = UserRepository(db).get_by_id(ctx.user_id)
    if user is None:
        raise NotFoundError("User not found.")
    log = communications_service.send_test_email(db, tenant_id=ctx.tenant_id, template=template, recipient=user.email)
    return _log_to_dict(log)


@router.get("/logs")
def list_logs(
    lead_id: uuid.UUID | None = None, status: EmailDeliveryStatus | None = None,
    ctx: TenantContext = Depends(require_permission("communications.manage")),
    _mod: TenantContext = Depends(require_module("communications")), db: Session = Depends(get_db),
) -> list[dict]:
    return [_log_to_dict(log) for log in communications_service.list_delivery_logs(db, ctx.tenant_id, lead_id=lead_id, status=status)]
