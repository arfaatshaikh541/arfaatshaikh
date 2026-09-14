from app.services.knowledge_sync_governance import (
    evaluate_federation_acceptance,
    evaluate_peer_attestation,
    evaluate_policy_change,
    evaluate_quarantine_release,
    evaluate_security_incident,
)


def test_peer_attestation_requires_independent_fresh_evidence():
    allowed = evaluate_peer_attestation(node_status="trusted", evidence_sha256="a"*64, independent_reviewer=True, expires_in_days=180, organisation_active=True)
    blocked = evaluate_peer_attestation(node_status="trusted", evidence_sha256="x", independent_reviewer=False, expires_in_days=500, organisation_active=True)
    assert allowed["allowed"] is True
    assert blocked["allowed"] is False


def test_sensitive_policy_expansion_requires_separate_approver():
    blocked = evaluate_policy_change(content_types={"quran"}, expands_access=True, requestor_is_approver=True, change_ticket="SYNC-42", evidence_sha256="b"*64, rollback_defined=True)
    allowed = evaluate_policy_change(content_types={"quran"}, expands_access=True, requestor_is_approver=False, change_ticket="SYNC-43", evidence_sha256="b"*64, rollback_defined=True)
    assert blocked["risk_level"] == "critical"
    assert blocked["allowed"] is False
    assert allowed["allowed"] is True


def test_policy_change_requires_rollback_and_evidence():
    result = evaluate_policy_change(content_types={"research"}, expands_access=False, requestor_is_approver=False, change_ticket="", evidence_sha256="x", rollback_defined=False)
    assert result["allowed"] is False
    assert "rollback_plan_required" in result["reason_codes"]


def test_high_incident_requires_full_containment():
    blocked = evaluate_security_incident(severity="high", status="open", evidence_sha256="c"*64, node_suspended=True, credentials_revoked=False, transfers_cancelled=False)
    contained = evaluate_security_incident(severity="high", status="contained", evidence_sha256="c"*64, node_suspended=True, credentials_revoked=True, transfers_cancelled=True)
    assert blocked["contained"] is False
    assert contained["contained"] is True


def test_critical_incident_cannot_be_dismissed():
    result = evaluate_security_incident(severity="critical", status="dismissed", evidence_sha256="d"*64, node_suspended=True, credentials_revoked=True, transfers_cancelled=True)
    assert result["contained"] is False
    assert "critical_incident_cannot_be_dismissed" in result["reason_codes"]


def test_quarantine_release_requires_clean_recovery():
    blocked = evaluate_quarantine_release(incident_status="resolved", release_evidence_sha256="e"*64, integrity_verification_passed=True, credentials_rotated=True, independent_approval=True, unresolved_drift=1)
    allowed = evaluate_quarantine_release(incident_status="resolved", release_evidence_sha256="e"*64, integrity_verification_passed=True, credentials_rotated=True, independent_approval=True, unresolved_drift=0)
    assert blocked["allowed"] is False
    assert allowed["allowed"] is True


def test_acceptance_distinguishes_portable_from_production_readiness():
    portable = evaluate_federation_acceptance(open_high_incidents=0, open_critical_incidents=0, integrity_gate_passed=True, replay_protection_tested=True, recovery_rehearsal_passed=True, audit_chain_verified=True, scholarly_governance_verified=True, live_network_tested=False)
    production = evaluate_federation_acceptance(open_high_incidents=0, open_critical_incidents=0, integrity_gate_passed=True, replay_protection_tested=True, recovery_rehearsal_passed=True, audit_chain_verified=True, scholarly_governance_verified=True, live_network_tested=True)
    assert portable["outcome"] == "conditional"
    assert portable["portable_ready"] is True
    assert production["outcome"] == "passed"


def test_open_serious_incidents_fail_acceptance():
    result = evaluate_federation_acceptance(open_high_incidents=1, open_critical_incidents=0, integrity_gate_passed=True, replay_protection_tested=True, recovery_rehearsal_passed=True, audit_chain_verified=True, scholarly_governance_verified=True, live_network_tested=True)
    assert result["outcome"] == "failed"
    assert result["production_ready"] is False
