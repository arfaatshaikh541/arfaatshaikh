from policy_engine.evaluate import evaluate
from policy_engine.schema import (
    ConfidentialComputingConstraint,
    CrossBorderConstraint,
    EncryptionConstraint,
    EvaluationCandidate,
    EvaluationResult,
    OperatorConstraint,
    PolicyDocument,
    ResidencyConstraint,
)
from policy_engine.schema import EvaluationRequest as Request


def base_candidate(**overrides: object) -> EvaluationCandidate:
    defaults: dict[str, object] = {
        "country": "AE",
        "operator_id": "op_gulf_horizon",
        "confidential_computing_available": True,
        "placement_role": "primary",
        "encryption_key_ownership": "customer_managed",
    }
    defaults.update(overrides)
    return EvaluationCandidate.model_validate(defaults)


def run(
    policy: PolicyDocument, version: int = 1, **candidate_overrides: object
) -> EvaluationResult:
    candidate = base_candidate(**candidate_overrides)
    request = Request(policy_id="p1", policy_version=version, policy=policy, candidate=candidate)
    return evaluate(request)


def test_empty_policy_allows_anything() -> None:
    result = run(PolicyDocument())
    assert result.decision == "allow"
    assert result.reason_codes == []


def test_residency_denied_country_blocks() -> None:
    policy = PolicyDocument(residency=ResidencyConstraint(denied_countries=["AE"]))
    result = run(policy)
    assert result.decision == "deny"
    assert "RESIDENCY_DENIED_COUNTRY" in result.reason_codes


def test_residency_not_in_allowed_list_blocks() -> None:
    policy = PolicyDocument(residency=ResidencyConstraint(allowed_countries=["DE", "NL"]))
    result = run(policy, country="AE")
    assert result.decision == "deny"
    assert "RESIDENCY_NOT_IN_ALLOWED_COUNTRIES" in result.reason_codes


def test_residency_in_allowed_list_passes() -> None:
    policy = PolicyDocument(residency=ResidencyConstraint(allowed_countries=["AE", "DE"]))
    result = run(policy, country="AE")
    assert result.decision == "allow"


def test_operator_denied_blocks() -> None:
    policy = PolicyDocument(operators=OperatorConstraint(denied=["op_gulf_horizon"]))
    result = run(policy)
    assert result.decision == "deny"
    assert "OPERATOR_DENIED" in result.reason_codes


def test_operator_not_in_allowed_list_blocks() -> None:
    policy = PolicyDocument(operators=OperatorConstraint(allowed=["op_euronorth"]))
    result = run(policy)
    assert result.decision == "deny"
    assert "OPERATOR_NOT_IN_ALLOWED_LIST" in result.reason_codes


def test_confidential_computing_required_but_unavailable_blocks() -> None:
    policy = PolicyDocument(confidential_computing=ConfidentialComputingConstraint(required=True))
    result = run(policy, confidential_computing_available=False)
    assert result.decision == "deny"
    assert "CONFIDENTIAL_COMPUTING_REQUIRED_BUT_UNAVAILABLE" in result.reason_codes


def test_confidential_computing_required_and_available_passes() -> None:
    policy = PolicyDocument(confidential_computing=ConfidentialComputingConstraint(required=True))
    result = run(policy, confidential_computing_available=True)
    assert result.decision == "allow"


def test_cross_border_backup_not_allowed_blocks() -> None:
    policy = PolicyDocument(cross_border=CrossBorderConstraint(backup_allowed_countries=["AE"]))
    result = run(policy, country="DE", placement_role="backup")
    assert result.decision == "deny"
    assert "CROSS_BORDER_BACKUP_NOT_ALLOWED" in result.reason_codes


def test_cross_border_does_not_apply_to_primary_placement() -> None:
    policy = PolicyDocument(cross_border=CrossBorderConstraint(backup_allowed_countries=["AE"]))
    result = run(policy, country="DE", placement_role="primary")
    assert result.decision == "allow"


def test_cross_border_failover_not_allowed_blocks() -> None:
    policy = PolicyDocument(cross_border=CrossBorderConstraint(failover_allowed_countries=["AE"]))
    result = run(policy, country="NL", placement_role="failover")
    assert result.decision == "deny"
    assert "CROSS_BORDER_FAILOVER_NOT_ALLOWED" in result.reason_codes


def test_encryption_key_ownership_mismatch_blocks() -> None:
    policy = PolicyDocument(encryption=EncryptionConstraint(key_ownership="customer_managed"))
    result = run(policy, encryption_key_ownership="provider_managed")
    assert result.decision == "deny"
    assert "ENCRYPTION_KEY_OWNERSHIP_MISMATCH" in result.reason_codes


def test_encryption_missing_candidate_declaration_fails_closed() -> None:
    policy = PolicyDocument(encryption=EncryptionConstraint(key_ownership="customer_managed"))
    result = run(policy, encryption_key_ownership=None)
    assert result.decision == "deny"
    assert "ENCRYPTION_KEY_OWNERSHIP_MISMATCH" in result.reason_codes


def test_multiple_failing_constraints_all_reported() -> None:
    policy = PolicyDocument(
        residency=ResidencyConstraint(denied_countries=["AE"]),
        operators=OperatorConstraint(denied=["op_gulf_horizon"]),
    )
    result = run(policy)
    assert result.decision == "deny"
    assert set(result.reason_codes) == {"RESIDENCY_DENIED_COUNTRY", "OPERATOR_DENIED"}


def test_evaluation_is_deterministic_and_hashes_inputs() -> None:
    policy = PolicyDocument(residency=ResidencyConstraint(allowed_countries=["AE"]))
    request = Request(policy_id="p1", policy_version=2, policy=policy, candidate=base_candidate())
    result1 = evaluate(request)
    result2 = evaluate(request)
    assert result1.decision == result2.decision == "allow"
    assert result1.inputs_hash == result2.inputs_hash
    assert result1.policy_id == "p1"
    assert result1.policy_version == 2


def test_different_inputs_produce_different_hash() -> None:
    policy = PolicyDocument()
    hash_a = run(policy, country="AE").inputs_hash
    hash_b = run(policy, country="DE").inputs_hash
    assert hash_a != hash_b
