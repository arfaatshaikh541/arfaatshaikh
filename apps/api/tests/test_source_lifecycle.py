from app.services.source_lifecycle import RetrievalEligibility, ingestion_transition_allowed


def test_retrieval_eligibility_fails_closed_when_one_gate_fails() -> None:
    result = RetrievalEligibility(
        source_approved=True,
        licence_approved=True,
        redistribution_allowed=True,
        acquisition_recorded=True,
        integrity_verified=False,
        ingestion_ready=True,
        review_approved=True,
        attribution_present=True,
        policy_present=True,
        policy_reviewers_met=True,
        policy_domains_met=True,
    )
    assert result.eligible is False
    assert result.failed_gates() == ["integrity_verified"]


def test_retrieval_eligibility_requires_every_gate() -> None:
    result = RetrievalEligibility(True, True, True, True, True, True, True, True, True, True, True)
    assert result.eligible is True
    assert result.failed_gates() == []


def test_ingestion_state_machine_rejects_skips_and_retired_reactivation() -> None:
    assert ingestion_transition_allowed("registered", "ready") is False
    assert ingestion_transition_allowed("registered", "validating") is True
    assert ingestion_transition_allowed("validating", "ready") is True
    assert ingestion_transition_allowed("retired", "validating") is False
