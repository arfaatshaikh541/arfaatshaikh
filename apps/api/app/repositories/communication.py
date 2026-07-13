import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.communication import MessageLog, MessageTemplate, Notification


class MessageTemplateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_tenant(self, tenant_id: uuid.UUID) -> list[MessageTemplate]:
        stmt = (
            select(MessageTemplate)
            .where(MessageTemplate.tenant_id == tenant_id)
            .order_by(MessageTemplate.key)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_key(self, tenant_id: uuid.UUID, key: str) -> MessageTemplate | None:
        stmt = select(MessageTemplate).where(
            MessageTemplate.tenant_id == tenant_id, MessageTemplate.key == key
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_id_for_tenant(
        self, tenant_id: uuid.UUID, template_id: uuid.UUID
    ) -> MessageTemplate | None:
        stmt = select(MessageTemplate).where(
            MessageTemplate.tenant_id == tenant_id, MessageTemplate.id == template_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, *, tenant_id: uuid.UUID, key: str, subject: str, body: str) -> MessageTemplate:
        template = MessageTemplate(tenant_id=tenant_id, key=key, subject=subject, body=body)
        self.db.add(template)
        self.db.flush()
        return template

    def update(self, template: MessageTemplate, **fields: object) -> MessageTemplate:
        for key, value in fields.items():
            if value is not None:
                setattr(template, key, value)
        self.db.flush()
        return template


class MessageLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        tenant_id: uuid.UUID,
        template_key: str,
        channel: str,
        recipient: str,
        status: str,
        lead_id: uuid.UUID | None = None,
        error_message: str | None = None,
    ) -> MessageLog:
        entry = MessageLog(
            tenant_id=tenant_id,
            template_key=template_key,
            channel=channel,
            recipient=recipient,
            lead_id=lead_id,
            status=status,
            error_message=error_message,
            created_at=utcnow(),
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_for_tenant(self, tenant_id: uuid.UUID, *, limit: int = 100) -> list[MessageLog]:
        stmt = (
            select(MessageLog)
            .where(MessageLog.tenant_id == tenant_id)
            .order_by(MessageLog.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())


class NotificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        body: str | None = None,
        related_entity_type: str | None = None,
        related_entity_id: str | None = None,
    ) -> Notification:
        notification = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            body=body,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            created_at=utcnow(),
        )
        self.db.add(notification)
        self.db.flush()
        return notification

    def list_for_user(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, *, limit: int = 50
    ) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.tenant_id == tenant_id, Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def unread_count(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        )
        return int(self.db.execute(stmt).scalar_one())

    def get_by_id_for_user(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification | None:
        stmt = select(Notification).where(
            Notification.tenant_id == tenant_id,
            Notification.user_id == user_id,
            Notification.id == notification_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def mark_read(self, notification: Notification) -> Notification:
        notification.is_read = True
        self.db.flush()
        return notification

    def mark_all_read(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
        for notification in self.list_for_user(tenant_id, user_id, limit=1000):
            if not notification.is_read:
                notification.is_read = True
        self.db.flush()
