from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.communication import Notification
from app.repositories.communication import NotificationRepository
from app.services.errors import NotFoundError


class NotificationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.notifications = NotificationRepository(db)

    def create(
        self,
        tenant_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        title: str,
        body: str | None = None,
        related_entity_type: str | None = None,
        related_entity_id: str | None = None,
    ) -> Notification:
        return self.notifications.create(
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            body=body,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )

    def list_for_user(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, *, limit: int = 50
    ) -> list[Notification]:
        return self.notifications.list_for_user(tenant_id, user_id, limit=limit)

    def unread_count(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> int:
        return self.notifications.unread_count(tenant_id, user_id)

    def mark_read(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification:
        notification = self.notifications.get_by_id_for_user(tenant_id, user_id, notification_id)
        if notification is None:
            raise NotFoundError("Notification not found.")
        return self.notifications.mark_read(notification)

    def mark_all_read(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.notifications.mark_all_read(tenant_id, user_id)
