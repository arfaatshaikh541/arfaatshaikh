"""Assignment engine: evaluates active AssignmentRule rows in order and
picks a tenant member to own a new lead. Every decision - automatic or
manual - is recorded by the caller (LeadService) in the activity
timeline, so support staff can always see *why* a lead landed where it
did. See docs/architecture/erd-summary-m3.md."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.assignment import ASSIGNMENT_STRATEGIES, AssignmentRule
from app.models.lead import Lead
from app.repositories.assignment import AssignmentRuleRepository, AssignmentRuleStateRepository
from app.repositories.membership import MembershipRepository
from app.services.errors import NotFoundError, ValidationError


@dataclass
class AssignmentDecision:
    membership_id: uuid.UUID | None
    rule_id: uuid.UUID | None
    strategy: str | None


def _candidate_ids(rule: AssignmentRule, lead: Lead) -> list[str]:
    config = rule.config or {}
    membership_ids: list[str] = config.get("membership_ids", [])
    if not membership_ids:
        return []
    if rule.strategy == "round_robin":
        return membership_ids
    if rule.strategy == "service_based":
        return (
            membership_ids
            if lead.service_id and str(lead.service_id) == config.get("service_id")
            else []
        )
    if rule.strategy == "branch_based":
        return (
            membership_ids
            if lead.branch_id and str(lead.branch_id) == config.get("branch_id")
            else []
        )
    if rule.strategy == "priority_based":
        return membership_ids if lead.priority == config.get("priority") else []
    return []


class AssignmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.rules = AssignmentRuleRepository(db)
        self.state = AssignmentRuleStateRepository(db)
        self.memberships = MembershipRepository(db)

    def auto_assign(self, tenant_id: uuid.UUID, lead: Lead) -> AssignmentDecision:
        active_rules = self.rules.list_for_tenant(tenant_id, active_only=True)
        matching_rules = [r for r in active_rules if r.strategy != "manual_fallback"]

        for rule in matching_rules:
            candidates = self._active_candidates(tenant_id, _candidate_ids(rule, lead))
            if not candidates:
                continue
            rule_state = self.state.get_or_create(rule.id)
            index = self.state.advance(rule_state, candidate_count=len(candidates))
            membership_id = uuid.UUID(candidates[index])
            return AssignmentDecision(
                membership_id=membership_id, rule_id=rule.id, strategy=rule.strategy
            )

        fallback_rule = next((r for r in active_rules if r.strategy == "manual_fallback"), None)
        if fallback_rule and fallback_rule.fallback_membership_id:
            return AssignmentDecision(
                membership_id=fallback_rule.fallback_membership_id,
                rule_id=fallback_rule.id,
                strategy="manual_fallback",
            )

        return AssignmentDecision(membership_id=None, rule_id=None, strategy=None)

    def _active_candidates(self, tenant_id: uuid.UUID, membership_ids: list[str]) -> list[str]:
        active = []
        for membership_id in membership_ids:
            try:
                membership = self.memberships.get_by_id_for_tenant(
                    tenant_id, uuid.UUID(membership_id)
                )
            except ValueError:
                continue
            if membership is not None and membership.status == "active":
                active.append(membership_id)
        return active

    # -- rule configuration --------------------------------------------

    def list_rules(self, tenant_id: uuid.UUID) -> list[AssignmentRule]:
        return self.rules.list_for_tenant(tenant_id)

    def create_rule(
        self,
        tenant_id: uuid.UUID,
        *,
        name: str,
        strategy: str,
        config: dict,
        sort_order: int = 0,
        fallback_membership_id: uuid.UUID | None = None,
    ) -> AssignmentRule:
        if strategy not in ASSIGNMENT_STRATEGIES:
            raise ValidationError(f"Unknown assignment strategy '{strategy}'.")
        if fallback_membership_id is not None:
            if self.memberships.get_by_id_for_tenant(tenant_id, fallback_membership_id) is None:
                raise ValidationError("Fallback member does not belong to this tenant.")
        for membership_id in (config or {}).get("membership_ids", []):
            try:
                parsed = uuid.UUID(membership_id)
            except (ValueError, TypeError) as exc:
                raise ValidationError("membership_ids must be valid UUIDs.") from exc
            if self.memberships.get_by_id_for_tenant(tenant_id, parsed) is None:
                raise ValidationError("One or more assignees do not belong to this tenant.")
        return self.rules.create(
            tenant_id=tenant_id,
            name=name,
            strategy=strategy,
            config=config,
            sort_order=sort_order,
            fallback_membership_id=fallback_membership_id,
        )

    def update_rule(
        self, tenant_id: uuid.UUID, rule_id: uuid.UUID, **fields: object
    ) -> AssignmentRule:
        rule = self.rules.get_by_id_for_tenant(tenant_id, rule_id)
        if rule is None:
            raise NotFoundError("Assignment rule not found.")
        return self.rules.update(rule, **fields)
