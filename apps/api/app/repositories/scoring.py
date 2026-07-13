import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scoring import ScoringRule, TenantScoringSettings


class ScoringRuleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_tenant(
        self, tenant_id: uuid.UUID, *, active_only: bool = False
    ) -> list[ScoringRule]:
        stmt = select(ScoringRule).where(ScoringRule.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(ScoringRule.is_active.is_(True))
        stmt = stmt.order_by(ScoringRule.sort_order)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id_for_tenant(self, tenant_id: uuid.UUID, rule_id: uuid.UUID) -> ScoringRule | None:
        stmt = select(ScoringRule).where(
            ScoringRule.tenant_id == tenant_id, ScoringRule.id == rule_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        rule_type: str,
        config: dict,
        points: int,
        sort_order: int = 0,
    ) -> ScoringRule:
        rule = ScoringRule(
            tenant_id=tenant_id,
            name=name,
            rule_type=rule_type,
            config=config,
            points=points,
            sort_order=sort_order,
        )
        self.db.add(rule)
        self.db.flush()
        return rule

    def update(self, rule: ScoringRule, **fields: object) -> ScoringRule:
        for key, value in fields.items():
            if value is not None:
                setattr(rule, key, value)
        self.db.flush()
        return rule


class TenantScoringSettingsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_tenant(self, tenant_id: uuid.UUID) -> TenantScoringSettings | None:
        stmt = select(TenantScoringSettings).where(TenantScoringSettings.tenant_id == tenant_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_or_create(self, tenant_id: uuid.UUID) -> TenantScoringSettings:
        settings = self.get_for_tenant(tenant_id)
        if settings is None:
            settings = TenantScoringSettings(tenant_id=tenant_id)
            self.db.add(settings)
            self.db.flush()
        return settings

    def update(self, settings: TenantScoringSettings, **fields: object) -> TenantScoringSettings:
        for key, value in fields.items():
            if value is not None:
                setattr(settings, key, value)
        self.db.flush()
        return settings
