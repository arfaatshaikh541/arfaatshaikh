from app.services.ai_orchestration import CitationEvidence, ClaimCandidate, orchestrate_claims, sha256_text


def evidence(text="Approved source wording", corpus="quran", attribution="Approved edition"):
    return CitationEvidence("passage-1", corpus, text, attribution, sha256_text(text))


def test_claim_without_governed_evidence_fails_closed():
    result = orchestrate_claims([ClaimCandidate("source_summary", "Summary", (0,))], [], risk_level="standard")
    assert result.status == "blocked"
    assert result.terminal_reason == "no_governed_evidence"


def test_each_claim_requires_citation():
    result = orchestrate_claims([ClaimCandidate("source_summary", "Summary", ())], [evidence()], risk_level="standard")
    assert result.status == "blocked"
    assert result.claims[0].reason_code == "claim_has_no_citation"


def test_direct_quote_must_be_verbatim():
    result = orchestrate_claims([ClaimCandidate("direct_quote", "Invented wording", (0,))], [evidence()], risk_level="standard")
    assert result.status == "blocked"
    assert result.claims[0].reason_code == "quote_not_verbatim_in_evidence"


def test_tafsir_is_required_for_scholarly_interpretation():
    result = orchestrate_claims([ClaimCandidate("scholarly_interpretation", "Interpretation", (0,))], [evidence(corpus="quran")], risk_level="standard")
    assert result.status == "blocked"
    assert result.claims[0].reason_code == "interpretation_requires_tafsir"


def test_difference_requires_distinct_attributions():
    items = [evidence(attribution="Scholar A"), CitationEvidence("passage-2", "tafsir", "Other", "Scholar A", sha256_text("Other"))]
    result = orchestrate_claims([ClaimCandidate("difference_of_opinion", "Two views", (0, 1))], items, risk_level="standard")
    assert result.status == "blocked"
    assert result.claims[0].reason_code == "difference_requires_distinct_attributions"


def test_high_risk_and_rulings_escalate_to_scholar():
    result = orchestrate_claims([ClaimCandidate("source_summary", "General guidance", (0,))], [evidence()], risk_level="high_risk")
    assert result.status == "escalated"
    assert result.requires_scholar is True


def test_supported_claim_completes_with_citation_label():
    result = orchestrate_claims([ClaimCandidate("direct_quote", "Approved source wording", (0,))], [evidence()], risk_level="standard")
    assert result.status == "completed"
    assert result.claims[0].citation_labels == ("[1]",)


def test_fingerprint_mismatch_blocks_claim():
    bad = CitationEvidence("passage-1", "quran", "Text", "Edition", "0" * 64)
    result = orchestrate_claims([ClaimCandidate("source_summary", "Summary", (0,))], [bad], risk_level="standard")
    assert result.status == "blocked"
    assert "fingerprint" in result.claims[0].reason_code
