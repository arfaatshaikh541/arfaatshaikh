from app.services.assistant import ClaimDraft, QuestionClass, assemble_grounded_answer, classify_question
from app.services.retrieval import EvidenceContract, sha256_text


def evidence(text="Approved exact source text", corpus="quran", attribution="Approved edition"):
    return EvidenceContract("c1", "d1", corpus, "canonical:1", "e1", "p1", text, sha256_text(text), attribution, "licensed")


def test_classifier_marks_high_risk_fatwa_for_escalation():
    result = classify_question("Is my divorce valid?")
    assert result.classification == QuestionClass.HIGH_RISK_FATWA
    assert result.risk_level == "high_risk"
    assert result.requires_escalation is True


def test_classifier_selects_quran_and_tafsir():
    result = classify_question("Explain this Quran verse")
    assert result.classification == QuestionClass.QURAN_EXPLANATION
    assert result.required_corpora == ("quran", "tafsir")


def test_direct_quote_must_exist_in_evidence():
    result = assemble_grounded_answer("Explain this Quran verse", [evidence()], [ClaimDraft("direct_quote", "invented quotation", (0,))])
    assert result.status == "insufficient"
    assert "verbatim" in result.insufficiency_reason


def test_scholarly_interpretation_requires_tafsir():
    result = assemble_grounded_answer("Explain this Quran verse", [evidence(corpus="quran")], [ClaimDraft("scholarly_interpretation", "A scholarly interpretation", (0,))])
    assert result.status == "insufficient"
    assert result.insufficiency_reason == "scholarly interpretation requires tafsir evidence"


def test_difference_of_opinion_requires_distinct_attributions():
    items = [evidence(attribution="Same scholar"), EvidenceContract("c2","d2","tafsir","canonical:2","e2","p2","Other text",sha256_text("Other text"),"Same scholar","licensed")]
    result = assemble_grounded_answer("Do scholars differ on this?", items, [ClaimDraft("difference_of_opinion", "There are two views", (0,1))])
    assert result.status == "insufficient"


def test_valid_answer_has_numbered_citations():
    item = evidence(text="Exact approved wording")
    result = assemble_grounded_answer("Explain this Quran verse", [item], [ClaimDraft("direct_quote", "Exact approved wording", (0,))])
    assert result.status == "assembled"
    assert result.response_text == "Exact approved wording [1]"


def test_high_risk_answer_adds_non_fatwa_boundary():
    item = evidence(corpus="tafsir")
    result = assemble_grounded_answer("Is my marriage valid?", [item], [ClaimDraft("source_summary", "The approved source gives general guidance.", (0,))])
    assert result.status == "assembled"
    assert "not a personal fatwa" in result.response_text


def test_unsupported_question_fails_closed():
    result = assemble_grounded_answer("How do I repair a bicycle?", [evidence()], [ClaimDraft("source_summary", "Text", (0,))])
    assert result.status == "insufficient"
    assert result.insufficiency_reason == "question_outside_supported_islamic_scope"
