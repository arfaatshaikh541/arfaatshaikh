"""Rule-based, explainable lead scoring engine.

Deliberately not ML-based: every point awarded traces back to a named,
tenant-configurable rule, returned alongside the total score so the UI
can show exactly why a lead scored the way it did. See
docs/architecture/erd-summary-m3.md and the Module 7 requirement to
never use unexplained scoring.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.scoring import SCORING_RULE_TYPES, ScoringRule, TenantScoringSettings
from app.repositories.scoring import ScoringRuleRepository, TenantScoringSettingsRepository
from app.services.errors import NotFoundError, ValidationError


@dataclass
class ScoreResult:
    score: int
    priority: str
    reasons: list[dict] = field(default_factory=list)


def _rule_matches(rule_type: str, config: dict, lead: Lead) -> bool:
    if rule_type == "service_equals":
        return lead.service_id is not None and str(lead.service_id) == config.get("service_id")
    if rule_type == "source_equals":
        return lead.source == config.get("source")
    if rule_type == "estimated_value_at_least":
        min_value = config.get("min_value")
        return (
            lead.estimated_value is not None
            and min_value is not None
            and float(lead.estimated_value) >= float(min_value)
        )
    if rule_type == "consent_given":
        return bool(lead.consent_given)
    if rule_type == "complete_contact_info":
        return bool(lead.email) and bool(lead.phone)
    if rule_type == "repeat_enquiry":
        return bool(lead.is_possible_duplicate)
    if rule_type == "answer_equals":
        question_id = config.get("question_id")
        expected = config.get("value")
        if not question_id or expected is None:
            return False
        for answer in lead.answers:
            if str(answer.question_id) != question_id:
                continue
            value = answer.value
            if isinstance(value, list):
                return str(expected).lower() in [str(v).lower() for v in value]
            return str(value).lower() == str(expected).lower()
        return False
    return False


class ScoringService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.rules = ScoringRuleRepository(db)
        self.settings = TenantScoringSettingsRepository(db)

    def compute(self, tenant_id: uuid.UUID, lead: Lead) -> ScoreResult:
        active_rules = self.rules.list_for_tenant(tenant_id, active_only=True)
        total = 0
        reasons: list[dict] = []
        for rule in active_rules:
            if _rule_matches(rule.rule_type, rule.config, lead):
                total += rule.points
                reasons.append({"rule_id": str(rule.id), "name": rule.name, "points": rule.points})

        thresholds = self.settings.get_or_create(tenant_id)
        if total >= thresholds.hot_threshold:
            priority = "hot"
        elif total >= thresholds.warm_threshold:
            priority = "warm"
        elif total >= thresholds.standard_threshold:
            priority = "standard"
        else:
            priority = "low_priority"

        return ScoreResult(score=total, priority=priority, reasons=reasons)

    def apply(self, tenant_id: uuid.UUID, lead: Lead) -> Lead:
        result = self.compute(tenant_id, lead)
        lead.score = result.score
        lead.priority = result.priority
        lead.score_reasons = result.reasons
        self.db.flush()
        return lead

    # -- rule + threshold configuration ---------------------------------

    def list_rules(self, tenant_id: uuid.UUID) -> list[ScoringRule]:
        return self.rules.list_for_tenant(tenant_id)

    def create_rule(
        self,
        tenant_id: uuid.UUID,
        *,
        name: str,
        rule_type: str,
        config: dict,
        points: int,
        sort_order: int = 0,
    ) -> ScoringRule:
        if rule_type not in SCORING_RULE_TYPES:
            raise ValidationError(f"Unknown scoring rule type '{rule_type}'.")
        return self.rules.create(
            tenant_id=tenant_id,
            name=name,
            rule_type=rule_type,
            config=config,
            points=points,
            sort_order=sort_order,
        )

    def update_rule(
        self, tenant_id: uuid.UUID, rule_id: uuid.UUID, **fields: object
    ) -> ScoringRule:
        rule = self.rules.get_by_id_for_tenant(tenant_id, rule_id)
        if rule is None:
            raise NotFoundError("Scoring rule not found.")
        return self.rules.update(rule, **fields)

    def get_thresholds(self, tenant_id: uuid.UUID) -> TenantScoringSettings:
        return self.settings.get_or_create(tenant_id)

    def update_thresholds(self, tenant_id: uuid.UUID, **fields: object) -> TenantScoringSettings:
        settings = self.settings.get_or_create(tenant_id)
        return self.settings.update(settings, **fields)
