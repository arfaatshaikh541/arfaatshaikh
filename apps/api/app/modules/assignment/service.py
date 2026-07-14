import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.modules.assignment.models import AssignmentRule, AssignmentStrategy
from app.modules.assignment.repository import AssignmentRoundRobinStateRepository, AssignmentRuleRepository
from app.modules.identity.models import MembershipStatus
from app.modules.identity.repository import MembershipRepository
from app.modules.leads.models import Lead


def _validate_eligible_users(db: Session, tenant_id: uuid.UUID, user_ids: list[uuid.UUID]) -> None:
    active_member_ids = {
        m.user_id for m in MembershipRepository(db).list_for_tenant(tenant_id) if m.status == MembershipStatus.ACTIVE
    }
    invalid = [str(uid) for uid in user_ids if uid not in active_member_ids]
    if invalid:
        raise ValidationFailedError(f"Not active members of this tenant: {', '.join(invalid)}", code="invalid_eligible_users")


def list_rules(db: Session, tenant_id: uuid.UUID) -> list[AssignmentRule]:
    return AssignmentRuleRepository(db).list_for_tenant(tenant_id)


def get_rule_or_404(db: Session, tenant_id: uuid.UUID, rule_id: uuid.UUID) -> AssignmentRule:
    rule = AssignmentRuleRepository(db).get(tenant_id, rule_id)
    if rule is None:
        raise NotFoundError("Assignment rule not found.")
    return rule


def create_rule(
    db: Session, *, tenant_id: uuid.UUID, name: str, strategy: AssignmentStrategy, conditions: dict,
    eligible_user_ids: list[uuid.UUID],
) -> AssignmentRule:
    _validate_eligible_users(db, tenant_id, eligible_user_ids)
    existing = AssignmentRuleRepository(db).list_for_tenant(tenant_id)
    return AssignmentRuleRepository(db).create(
        tenant_id=tenant_id, name=name, strategy=strategy, conditions=conditions,
        eligible_user_ids=[str(uid) for uid in eligible_user_ids], sort_order=len(existing),
    )


def update_rule(db: Session, *, tenant_id: uuid.UUID, rule: AssignmentRule, updates: dict) -> AssignmentRule:
    if "eligible_user_ids" in updates and updates["eligible_user_ids"] is not None:
        _validate_eligible_users(db, tenant_id, updates["eligible_user_ids"])
        updates["eligible_user_ids"] = [str(uid) for uid in updates["eligible_user_ids"]]
    for field, val in updates.items():
        if val is not None:
            setattr(rule, field, val)
    db.add(rule)
    db.flush()
    return rule


def reorder_rules(db: Session, *, tenant_id: uuid.UUID, rule_ids_in_order: list[uuid.UUID]) -> None:
    repo = AssignmentRuleRepository(db)
    existing = {rule.id: rule for rule in repo.list_for_tenant(tenant_id)}
    ordered = [existing[rid] for rid in rule_ids_in_order if rid in existing]
    repo.reorder(ordered)


def _rule_matches(rule: AssignmentRule, lead: Lead) -> bool:
    if rule.strategy == AssignmentStrategy.ROUND_ROBIN:
        return True
    if rule.strategy == AssignmentStrategy.SERVICE_BASED:
        service_ids = set(rule.conditions.get("service_ids", []))
        return lead.service_id is not None and str(lead.service_id) in service_ids
    if rule.strategy == AssignmentStrategy.PRIORITY_BASED:
        priorities = {p.lower() for p in rule.conditions.get("priorities", [])}
        return lead.priority.value in priorities
    return False


def _pick_next_user(db: Session, tenant_id: uuid.UUID, rule: AssignmentRule) -> uuid.UUID | None:
    pool = rule.eligible_user_ids
    if not pool:
        return None
    state = AssignmentRoundRobinStateRepository(db).get_or_create_for_update(tenant_id, rule.id)
    next_index = (state.last_assigned_index + 1) % len(pool)
    state.last_assigned_index = next_index
    db.add(state)
    db.flush()
    return uuid.UUID(pool[next_index])


def assign_lead_automatically(db: Session, *, tenant_id: uuid.UUID, lead: Lead, actor_id: uuid.UUID | None = None) -> Lead:
    """Evaluates active assignment rules in order; the first match with a
    non-empty eligible pool wins and the lead is assigned via
    `leads.service.assign_lead` (which records its own activity/audit
    entries). No match leaves the lead unassigned — not an error."""
    rules = AssignmentRuleRepository(db).list_for_tenant(tenant_id, active_only=True)
    for rule in rules:
        if not _rule_matches(rule, lead):
            continue
        user_id = _pick_next_user(db, tenant_id, rule)
        if user_id is None:
            continue

        from app.modules.crm.service import record_activity
        from app.modules.leads.service import assign_lead

        assign_lead(db, tenant_id=tenant_id, lead=lead, assigned_user_id=user_id, actor_id=actor_id)
        record_activity(
            db, tenant_id=tenant_id, lead_id=lead.id, actor_id=actor_id, activity_type="lead.auto_assigned",
            summary=f"Auto-assigned via rule '{rule.name}'", metadata_json={"rule_id": str(rule.id), "rule_name": rule.name},
        )
        return lead
    return lead
