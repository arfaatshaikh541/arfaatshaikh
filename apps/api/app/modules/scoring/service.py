import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.leads.models import Lead, LeadPriority
from app.modules.leads.repository import QualificationAnswerRepository
from app.modules.scoring.models import ScoringOperator, ScoringRule, ScoringSettings
from app.modules.scoring.repository import LeadScoreLogRepository, ScoringRuleRepository, ScoringSettingsRepository

MIN_SCORE = 0
MAX_SCORE = 100

_DIRECT_FIELDS = {
    "estimated_value",
    "company",
    "consent_status",
    "preferred_contact_method",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "service_id",
    "source_id",
}


def ensure_scoring_settings(db: Session, tenant_id: uuid.UUID) -> ScoringSettings:
    repo = ScoringSettingsRepository(db)
    settings = repo.get_for_tenant(tenant_id)
    if settings is None:
        settings = repo.create(tenant_id=tenant_id)
    return settings


def update_scoring_settings(db: Session, tenant_id: uuid.UUID, *, updates: dict) -> ScoringSettings:
    settings = ensure_scoring_settings(db, tenant_id)
    for field, value in updates.items():
        if value is not None:
            setattr(settings, field, value)
    db.add(settings)
    db.flush()
    return settings


def list_rules(db: Session, tenant_id: uuid.UUID) -> list[ScoringRule]:
    return ScoringRuleRepository(db).list_for_tenant(tenant_id)


def get_rule_or_404(db: Session, tenant_id: uuid.UUID, rule_id: uuid.UUID) -> ScoringRule:
    rule = ScoringRuleRepository(db).get(tenant_id, rule_id)
    if rule is None:
        raise NotFoundError("Scoring rule not found.")
    return rule


def create_rule(
    db: Session, *, tenant_id: uuid.UUID, name: str, field: str, operator: ScoringOperator, value: object, points: int
) -> ScoringRule:
    existing = ScoringRuleRepository(db).list_for_tenant(tenant_id)
    return ScoringRuleRepository(db).create(
        tenant_id=tenant_id, name=name, field=field, operator=operator, value={"value": value}, points=points,
        sort_order=len(existing),
    )


def update_rule(db: Session, *, tenant_id: uuid.UUID, rule: ScoringRule, updates: dict) -> ScoringRule:
    for field, val in updates.items():
        if val is None:
            continue
        if field == "value":
            rule.value = {"value": val}
        else:
            setattr(rule, field, val)
    db.add(rule)
    db.flush()
    return rule


def reorder_rules(db: Session, *, tenant_id: uuid.UUID, rule_ids_in_order: list[uuid.UUID]) -> None:
    repo = ScoringRuleRepository(db)
    existing = {rule.id: rule for rule in repo.list_for_tenant(tenant_id)}
    ordered = [existing[rid] for rid in rule_ids_in_order if rid in existing]
    repo.reorder(ordered)


def _resolve_field_value(lead: Lead, answers_by_question: dict[str, object], field: str) -> object | None:
    if field.startswith("answer:"):
        question_id = field.split(":", 1)[1]
        return answers_by_question.get(question_id)
    if field not in _DIRECT_FIELDS:
        return None
    raw = getattr(lead, field, None)
    if raw is None:
        return None
    if hasattr(raw, "value"):  # enum
        return raw.value
    if isinstance(raw, uuid.UUID):
        return str(raw)
    return raw


def _evaluate(operator: ScoringOperator, actual: object | None, expected: object) -> bool:
    if operator == ScoringOperator.IS_SET:
        return actual is not None and actual != ""
    if actual is None:
        return False
    if operator == ScoringOperator.EQUALS:
        return str(actual).lower() == str(expected).lower()
    if operator == ScoringOperator.NOT_EQUALS:
        return str(actual).lower() != str(expected).lower()
    if operator == ScoringOperator.CONTAINS:
        return str(expected).lower() in str(actual).lower()
    if operator == ScoringOperator.IN:
        options = expected if isinstance(expected, list) else [expected]
        return str(actual).lower() in {str(o).lower() for o in options}
    if operator in (ScoringOperator.GREATER_THAN, ScoringOperator.LESS_THAN):
        try:
            actual_num = float(actual)
            expected_num = float(expected)
        except (TypeError, ValueError):
            return False
        return actual_num > expected_num if operator == ScoringOperator.GREATER_THAN else actual_num < expected_num
    return False


def compute_score(lead: Lead, answers_by_question: dict[str, object], rules: list[ScoringRule]) -> tuple[int, list[dict]]:
    """Pure, deterministic: sums the points of every active rule whose
    condition matches, clamps to [0, 100], and returns the matched-rule
    breakdown that makes the result explainable."""
    total = 0
    breakdown: list[dict] = []
    for rule in rules:
        if not rule.is_active:
            continue
        actual = _resolve_field_value(lead, answers_by_question, rule.field)
        expected = rule.value.get("value")
        if _evaluate(rule.operator, actual, expected):
            total += rule.points
            breakdown.append({"rule_id": str(rule.id), "rule_name": rule.name, "points": rule.points})
    clamped = max(MIN_SCORE, min(MAX_SCORE, total))
    return clamped, breakdown


def _priority_from_score(score: int, settings: ScoringSettings) -> LeadPriority:
    if score >= settings.hot_threshold:
        return LeadPriority.HIGH
    if score >= settings.warm_threshold:
        return LeadPriority.MEDIUM
    return LeadPriority.LOW


def score_and_apply(db: Session, *, tenant_id: uuid.UUID, lead: Lead, actor_id: uuid.UUID | None = None) -> Lead:
    settings = ensure_scoring_settings(db, tenant_id)
    rules = ScoringRuleRepository(db).list_for_tenant(tenant_id, active_only=True)
    answers = QualificationAnswerRepository(db).list_for_lead(tenant_id, lead.id)
    answers_by_question = {str(a.question_id): a.answer_value.get("value") for a in answers}

    score, breakdown = compute_score(lead, answers_by_question, rules)
    lead.score = score
    if settings.auto_priority and not lead.priority_locked:
        lead.priority = _priority_from_score(score, settings)
    db.add(lead)
    db.flush()

    LeadScoreLogRepository(db).create(tenant_id=tenant_id, lead_id=lead.id, total_score=score, breakdown=breakdown)

    from app.modules.crm.service import record_activity

    record_activity(
        db, tenant_id=tenant_id, lead_id=lead.id, actor_id=actor_id, activity_type="lead.scored",
        summary=f"Lead scored: {score} ({len(breakdown)} rule(s) matched)", metadata_json={"score": score, "breakdown": breakdown},
    )
    return lead


def get_latest_score_log(db: Session, tenant_id: uuid.UUID, lead_id: uuid.UUID):
    return LeadScoreLogRepository(db).get_latest_for_lead(tenant_id, lead_id)
