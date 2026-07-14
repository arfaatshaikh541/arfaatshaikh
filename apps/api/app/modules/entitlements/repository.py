import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.entitlements.models import TenantFeatureOverride, UsageMetric, UsageRecord


class FeatureOverrideRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_active_for_tenant(self, tenant_id: uuid.UUID, *, at) -> list[TenantFeatureOverride]:
        return list(
            self.db.execute(
                select(TenantFeatureOverride).where(
                    TenantFeatureOverride.tenant_id == tenant_id,
                    (TenantFeatureOverride.expires_at.is_(None) | (TenantFeatureOverride.expires_at > at)),
                )
            )
            .scalars()
            .all()
        )

    def create(
        self, *, tenant_id: uuid.UUID, feature_id: uuid.UUID, config: dict, granted_by: uuid.UUID | None,
        expires_at, reason: str,
    ) -> TenantFeatureOverride:
        override = TenantFeatureOverride(
            tenant_id=tenant_id, feature_id=feature_id, config=config, granted_by=granted_by,
            expires_at=expires_at, reason=reason,
        )
        self.db.add(override)
        self.db.flush()
        return override

    def list_expired(self, *, before) -> list[TenantFeatureOverride]:
        return list(
            self.db.execute(
                select(TenantFeatureOverride).where(
                    TenantFeatureOverride.expires_at.is_not(None), TenantFeatureOverride.expires_at < before
                )
            )
            .scalars()
            .all()
        )

    def delete(self, override: TenantFeatureOverride) -> None:
        self.db.delete(override)


class UsageMetricRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_code(self, code: str) -> UsageMetric | None:
        return self.db.execute(select(UsageMetric).where(UsageMetric.code == code)).scalar_one_or_none()

    def create(self, *, code: str, name: str, unit: str = "count") -> UsageMetric:
        metric = UsageMetric(code=code, name=name, unit=unit)
        self.db.add(metric)
        self.db.flush()
        return metric


class UsageRecordRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_update(self, tenant_id: uuid.UUID, metric_id: uuid.UUID, period: date) -> UsageRecord | None:
        """Locks the row (or would-be row) for the duration of the current
        transaction so concurrent requests cannot both read the same
        pre-increment value and both slip under a limit."""
        return self.db.execute(
            select(UsageRecord)
            .where(UsageRecord.tenant_id == tenant_id, UsageRecord.metric_id == metric_id, UsageRecord.period == period)
            .with_for_update()
        ).scalar_one_or_none()

    def get_or_create_for_update(self, tenant_id: uuid.UUID, metric_id: uuid.UUID, period: date) -> UsageRecord:
        record = self.get_for_update(tenant_id, metric_id, period)
        if record is not None:
            return record
        record = UsageRecord(tenant_id=tenant_id, metric_id=metric_id, period=period, value=0)
        self.db.add(record)
        self.db.flush()
        return record

    def get_current(self, tenant_id: uuid.UUID, metric_id: uuid.UUID, period: date) -> int:
        record = self.db.execute(
            select(UsageRecord).where(
                UsageRecord.tenant_id == tenant_id, UsageRecord.metric_id == metric_id, UsageRecord.period == period
            )
        ).scalar_one_or_none()
        return record.value if record else 0
