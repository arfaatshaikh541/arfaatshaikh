import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.public_submission import IdempotencyKey, PublicFormAttempt


class IdempotencyKeyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, tenant_id: uuid.UUID, key: str) -> IdempotencyKey | None:
        stmt = select(IdempotencyKey).where(
            IdempotencyKey.tenant_id == tenant_id, IdempotencyKey.key == key
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self, *, tenant_id: uuid.UUID, key: str, request_hash: str, lead_id: uuid.UUID
    ) -> IdempotencyKey:
        entry = IdempotencyKey(
            tenant_id=tenant_id,
            key=key,
            request_hash=request_hash,
            lead_id=lead_id,
            created_at=utcnow(),
        )
        self.db.add(entry)
        self.db.flush()
        return entry


class PublicFormAttemptRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(self, *, tenant_id: uuid.UUID, ip_address: str) -> None:
        self.db.add(
            PublicFormAttempt(tenant_id=tenant_id, ip_address=ip_address, created_at=utcnow())
        )
        self.db.flush()

    def count_recent(self, *, tenant_id: uuid.UUID, ip_address: str, window_minutes: int) -> int:
        since = utcnow() - timedelta(minutes=window_minutes)
        stmt = (
            select(func.count())
            .select_from(PublicFormAttempt)
            .where(
                PublicFormAttempt.tenant_id == tenant_id,
                PublicFormAttempt.ip_address == ip_address,
                PublicFormAttempt.created_at >= since,
            )
        )
        return int(self.db.execute(stmt).scalar_one())
