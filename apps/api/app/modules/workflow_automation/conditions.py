"""Field/operator/value condition evaluation for workflow triggers.

Deliberately independent from `app.modules.scoring.service`'s near-
identical evaluator rather than sharing it — the two were built a
milestone apart, scoring's version is already shipped and tested, and
extracting a shared utility for two callers isn't worth the risk of
touching working code for this milestone. Revisit if a third caller
appears (rule of three).
"""
import enum
import uuid


class ConditionOperator(str, enum.Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    IS_SET = "is_set"
    IN = "in"


_DIRECT_FIELDS = {
    "estimated_value",
    "company",
    "consent_status",
    "preferred_contact_method",
    "priority",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "service_id",
    "source_id",
    "score",
}


def resolve_field_value(lead, field: str) -> object | None:
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


def evaluate(operator: ConditionOperator, actual: object | None, expected: object) -> bool:
    if operator == ConditionOperator.IS_SET:
        return actual is not None and actual != ""
    if actual is None:
        return False
    if operator == ConditionOperator.EQUALS:
        return str(actual).lower() == str(expected).lower()
    if operator == ConditionOperator.NOT_EQUALS:
        return str(actual).lower() != str(expected).lower()
    if operator == ConditionOperator.CONTAINS:
        return str(expected).lower() in str(actual).lower()
    if operator == ConditionOperator.IN:
        options = expected if isinstance(expected, list) else [expected]
        return str(actual).lower() in {str(o).lower() for o in options}
    if operator in (ConditionOperator.GREATER_THAN, ConditionOperator.LESS_THAN):
        try:
            actual_num = float(actual)
            expected_num = float(expected)
        except (TypeError, ValueError):
            return False
        return actual_num > expected_num if operator == ConditionOperator.GREATER_THAN else actual_num < expected_num
    return False


def evaluate_all(lead, conditions: list[dict]) -> bool:
    """All conditions must match (AND semantics) — an empty list always
    matches, meaning "no extra filter beyond the trigger event itself"."""
    for condition in conditions:
        operator = ConditionOperator(condition["operator"])
        actual = resolve_field_value(lead, condition["field"])
        if not evaluate(operator, actual, condition.get("value")):
            return False
    return True
