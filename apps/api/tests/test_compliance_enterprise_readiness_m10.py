from app.db.base import Base
import app.models  # noqa: F401
from app.services.compliance import EvidenceInput, evaluate_control, evaluate_disaster_recovery, evaluate_enterprise_readiness, evaluate_risk, validate_evidence

def test_compliance_tables_registered():
    expected = {"compliance_frameworks", "compliance_controls", "compliance_evidence", "enterprise_risks", "disaster_recovery_plans"}
    assert expected.issubset(Base.metadata.tables)

def test_evidence_rejects_unsafe_uri_and_bad_digest():
    result = validate_evidence(EvidenceInput("file:///tmp/evidence", "bad", "internal", 365, False))
    assert result["valid"] is False
    assert {"unsafe_evidence_uri", "invalid_evidence_fingerprint"}.issubset(result["reason_codes"])

def test_control_requires_owner_independent_test_and_verified_evidence():
    result = evaluate_control(framework_code="ISO27001", implemented=True, independently_tested=False, evidence_verified=False, owner_assigned=False)
    assert result["control_effective"] is False
    assert {"control_owner_required", "independent_test_required", "verified_evidence_required"}.issubset(result["reason_codes"])

def test_high_risk_requires_treatment_or_authorised_acceptance():
    result = evaluate_risk(likelihood=4, impact=4, treatment_plan_present=False, owner_assigned=True, accepted_by_authority=False)
    assert result["acceptable"] is False
    assert result["score"] == 16
    assert "high_risk_treatment_required" in result["reason_codes"]

def test_critical_risk_cannot_be_silently_accepted():
    result = evaluate_risk(likelihood=5, impact=5, treatment_plan_present=False, owner_assigned=True, accepted_by_authority=True)
    assert result["acceptable"] is False
    assert "critical_risk_cannot_be_silently_accepted" in result["reason_codes"]

def test_disaster_recovery_fails_without_restore_rollback_and_verified_evidence():
    result = evaluate_disaster_recovery(rpo_minutes=15, rto_minutes=60, encrypted_backups=True, restore_test_passed=False, rollback_test_passed=False, evidence_verified=False, multi_region_required=True, multi_region_ready=False)
    assert result["recovery_ready"] is False
    assert {"restore_test_required", "rollback_test_required", "verified_recovery_evidence_required", "multi_region_readiness_required"}.issubset(result["reason_codes"])

def test_enterprise_readiness_fails_closed():
    result = evaluate_enterprise_readiness(control_failures=1, open_high_risks=1, overdue_evidence=1, disaster_recovery_ready=False, data_export_tested=False, data_deletion_tested=False, key_rotation_verified=False, secret_rotation_verified=False)
    assert result["enterprise_ready"] is False
    assert len(result["reason_codes"]) == 8

def test_enterprise_readiness_passes_with_complete_evidence():
    result = evaluate_enterprise_readiness(control_failures=0, open_high_risks=0, overdue_evidence=0, disaster_recovery_ready=True, data_export_tested=True, data_deletion_tested=True, key_rotation_verified=True, secret_rotation_verified=True)
    assert result["enterprise_ready"] is True
