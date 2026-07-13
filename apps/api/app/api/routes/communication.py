from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import MembershipContext, get_current_membership, require_permission
from app.db.session import get_db
from app.schemas.common import MessageResponse
from app.schemas.communication import (
    MessageTemplateCreate,
    MessageTemplateOut,
    MessageTemplateUpdate,
    NotificationOut,
)
from app.services.message_template_service import MessageTemplateService
from app.services.notification_service import NotificationService

templates_router = APIRouter(prefix="/tenants/me/message-templates", tags=["communications"])
notifications_router = APIRouter(prefix="/tenants/me/notifications", tags=["communications"])


@templates_router.get("", response_model=list[MessageTemplateOut])
def list_message_templates(
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("templates.manage")),
) -> list[MessageTemplateOut]:
    templates = MessageTemplateService(db).list_templates(ctx.tenant_id)
    return [MessageTemplateOut.model_validate(t) for t in templates]


@templates_router.post("", response_model=MessageTemplateOut, status_code=201)
def create_message_template(
    payload: MessageTemplateCreate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("templates.manage")),
) -> MessageTemplateOut:
    template = MessageTemplateService(db).create(
        ctx.tenant_id, key=payload.key, subject=payload.subject, body=payload.body
    )
    db.commit()
    return MessageTemplateOut.model_validate(template)


@templates_router.patch("/{template_id}", response_model=MessageTemplateOut)
def update_message_template(
    template_id: uuid.UUID,
    payload: MessageTemplateUpdate,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("templates.manage")),
) -> MessageTemplateOut:
    template = MessageTemplateService(db).update(
        ctx.tenant_id, template_id, **payload.model_dump(exclude_unset=True)
    )
    db.commit()
    return MessageTemplateOut.model_validate(template)


@notifications_router.get("", response_model=list[NotificationOut])
def list_notifications(
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(get_current_membership),
) -> list[NotificationOut]:
    notifications = NotificationService(db).list_for_user(ctx.tenant_id, ctx.user.id)
    return [NotificationOut.model_validate(n) for n in notifications]


@notifications_router.get("/unread-count")
def get_unread_notification_count(
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(get_current_membership),
) -> dict[str, int]:
    return {"count": NotificationService(db).unread_count(ctx.tenant_id, ctx.user.id)}


@notifications_router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(get_current_membership),
) -> NotificationOut:
    notification = NotificationService(db).mark_read(ctx.tenant_id, ctx.user.id, notification_id)
    db.commit()
    return NotificationOut.model_validate(notification)


@notifications_router.post("/read-all", response_model=MessageResponse)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(get_current_membership),
) -> MessageResponse:
    NotificationService(db).mark_all_read(ctx.tenant_id, ctx.user.id)
    db.commit()
    return MessageResponse(message="All notifications marked as read.")
