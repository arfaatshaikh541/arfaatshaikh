import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.scoring.models import LeadScoreLog, ScoringRule, ScoringSettings


class ScoringRuleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: uuid.UUID, rule_id: uuid.UUID) -> ScoringRule | None:
        return self.db.execute(
            select(ScoringRule).where(ScoringRule.tenant_id == tenant_id, ScoringRule.id == rule_id)
        ).scalar_one_or_none()

    def list_for_tenant(self, tenant_id: uuid.UUID, *, active_only: bool = False) -> list[ScoringRule]:
        stmt = select(ScoringRule).where(ScoringRule.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(ScoringRule.is_active.is_(True))
        return list(self.db.execute(stmt.order_by(ScoringRule.sort_order)).scalars().all())

    def create(
        self, *, tenant_id: uuid.UUID, name: str, field: str, operator, value: dict, points: int, sort_order: int = 0
    ) -> ScoringRule:
        rule = ScoringRule(
            tenant_id=tenant_id, name=name, field=field, operator=operator, value=value, points=points, sort_order=sort_order
        )
        self.db.add(rule)
        self.db.flush()
        return rule

    def reorder(self, rules_in_order: list[ScoringRule]) -> None:
        for index, rule in enumerate(rules_in_order):
            rule.sort_order = index
        self.db.flush()


class ScoringSettingsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_tenant(self, tenant_id: uuid.UUID) -> ScoringSettings | None:
        return self.db.execute(
            select(ScoringSettings).where(ScoringSettings.tenant_id == tenant_id)
        ).scalar_one_or_none()

    def create(self, *, tenant_id: uuid.UUID, **fields) -> ScoringSettings:
        settings = ScoringSettings(tenant_id=tenant_id, **fields)
        self.db.add(settings)
        self.db.flush()
        return settings


class LeadScoreLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, tenant_id: uuid.UUID, lead_id: uuid.UUID, total_score: int, breakdown: list) -> LeadScoreLog:
        log = LeadScoreLog(tenant_id=tenant_id, lead_id=lead_id, total_score=total_score, breakdown=breakdown)
        self.db.add(log)
        self.db.flush()
        return log

    def get_latest_for_lead(self, tenant_id: uuid.UUID, lead_id: uuid.UUID) -> LeadScoreLog | None:
        return self.db.execute(
            select(LeadScoreLog)
            .where(LeadScoreLog.tenant_id == tenant_id, LeadScoreLog.lead_id == lead_id)
            .order_by(LeadScoreLog.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
