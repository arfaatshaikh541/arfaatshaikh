from policy_engine.conflicts import ConflictCheckRequest, ConflictCheckResult, find_conflicts
from policy_engine.schema import (
    CrossBorderConstraint,
    EncryptionConstraint,
    OperatorConstraint,
    PolicyDocument,
    ResidencyConstraint,
)


def check(a: PolicyDocument, b: PolicyDocument) -> ConflictCheckResult:
    request = ConflictCheckRequest(policy_a_id="a", policy_a=a, policy_b_id="b", policy_b=b)
    return find_conflicts(request)


def test_no_conflicts_between_compatible_policies() -> None:
    a = PolicyDocument(residency=ResidencyConstraint(allowed_countries=["AE", "DE"]))
    b = PolicyDocument(residency=ResidencyConstraint(allowed_countries=["DE", "NL"]))
    result = check(a, b)
    assert result.has_conflicts is False
    assert result.conflicts == []


def test_disjoint_residency_allowed_sets_conflict() -> None:
    a = PolicyDocument(residency=ResidencyConstraint(allowed_countries=["AE"]))
    b = PolicyDocument(residency=ResidencyConstraint(allowed_countries=["DE"]))
    result = check(a, b)
    assert result.has_conflicts is True
    assert any(c.code == "CONTRADICTORY_RESIDENCY_ALLOWED_SETS" for c in result.conflicts)


def test_country_allowed_by_one_and_denied_by_other_conflicts() -> None:
    a = PolicyDocument(residency=ResidencyConstraint(allowed_countries=["AE", "DE"]))
    b = PolicyDocument(residency=ResidencyConstraint(denied_countries=["AE"]))
    result = check(a, b)
    assert result.has_conflicts is True
    codes = [c.code for c in result.conflicts]
    assert "CONTRADICTORY_RESIDENCY_COUNTRY" in codes


def test_disjoint_operator_allowed_sets_conflict() -> None:
    a = PolicyDocument(operators=OperatorConstraint(allowed=["op_gulf_horizon"]))
    b = PolicyDocument(operators=OperatorConstraint(allowed=["op_euronorth"]))
    result = check(a, b)
    assert result.has_conflicts is True
    assert any(c.code == "CONTRADICTORY_OPERATOR_ALLOWED_SETS" for c in result.conflicts)


def test_operator_allowed_by_one_denied_by_other_conflicts() -> None:
    a = PolicyDocument(operators=OperatorConstraint(allowed=["op_gulf_horizon"]))
    b = PolicyDocument(operators=OperatorConstraint(denied=["op_gulf_horizon"]))
    result = check(a, b)
    assert result.has_conflicts is True
    assert any(c.code == "CONTRADICTORY_OPERATOR" for c in result.conflicts)


def test_disjoint_cross_border_backup_countries_conflict() -> None:
    a = PolicyDocument(cross_border=CrossBorderConstraint(backup_allowed_countries=["AE"]))
    b = PolicyDocument(cross_border=CrossBorderConstraint(backup_allowed_countries=["DE"]))
    result = check(a, b)
    assert result.has_conflicts is True
    assert any(c.code == "CONTRADICTORY_CROSS_BORDER_BACKUP" for c in result.conflicts)


def test_disjoint_cross_border_failover_countries_conflict() -> None:
    a = PolicyDocument(cross_border=CrossBorderConstraint(failover_allowed_countries=["AE"]))
    b = PolicyDocument(cross_border=CrossBorderConstraint(failover_allowed_countries=["DE"]))
    result = check(a, b)
    assert result.has_conflicts is True
    assert any(c.code == "CONTRADICTORY_CROSS_BORDER_FAILOVER" for c in result.conflicts)


def test_mismatched_encryption_key_ownership_conflicts() -> None:
    a = PolicyDocument(encryption=EncryptionConstraint(key_ownership="customer_managed"))
    b = PolicyDocument(encryption=EncryptionConstraint(key_ownership="provider_managed"))
    result = check(a, b)
    assert result.has_conflicts is True
    assert any(c.code == "CONTRADICTORY_ENCRYPTION_KEY_OWNERSHIP" for c in result.conflicts)


def test_matching_encryption_key_ownership_does_not_conflict() -> None:
    a = PolicyDocument(encryption=EncryptionConstraint(key_ownership="customer_managed"))
    b = PolicyDocument(encryption=EncryptionConstraint(key_ownership="customer_managed"))
    result = check(a, b)
    assert result.has_conflicts is False


def test_one_sided_encryption_requirement_does_not_conflict() -> None:
    a = PolicyDocument(encryption=EncryptionConstraint(key_ownership="customer_managed"))
    b = PolicyDocument()
    result = check(a, b)
    assert result.has_conflicts is False


def test_confidential_computing_mismatch_is_not_a_conflict() -> None:
    # required=True in one and unspecified in the other is not a
    # contradiction -- both can be simultaneously satisfied (the stricter
    # requirement just wins), unlike disjoint allow-lists.
    from policy_engine.schema import ConfidentialComputingConstraint

    a = PolicyDocument(confidential_computing=ConfidentialComputingConstraint(required=True))
    b = PolicyDocument(confidential_computing=ConfidentialComputingConstraint(required=False))
    result = check(a, b)
    assert result.has_conflicts is False
