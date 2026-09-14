import pytest
from app.services.multilingual_ai import TranslationAlignment, require_claim_count_alignment, sha256_text, validate_alignment, normalize_text

def item(**overrides):
    data = dict(source_language="en", target_language="ar", source_text="Allah is Merciful", target_text="الله رحيم", evidence_sha256=sha256_text("Allah is Merciful"), preserves_citations=True, alignment_confidence=.95)
    data.update(overrides)
    return TranslationAlignment(**data)

def test_arabic_normalization_removes_diacritics_and_alef_variants():
    assert normalize_text("إِنَّ ٱللَّهَ", "ar") == "ان الله"

def test_fingerprint_mismatch_blocks_translation():
    assert validate_alignment(item(evidence_sha256="0"*64)).reason_code == "source_evidence_fingerprint_mismatch"

def test_citations_must_survive_translation():
    assert validate_alignment(item(preserves_citations=False)).reason_code == "translation_lost_claim_citations"

def test_wrong_target_script_is_blocked():
    assert validate_alignment(item(target_text="plain english")).reason_code == "target_script_mismatch"

def test_low_confidence_requires_review():
    result = validate_alignment(item(alignment_confidence=.60))
    assert result.decision == "review" and result.requires_human_review

def test_urdu_hindi_and_transliteration_require_human_review():
    result = validate_alignment(item(target_language="ur", target_text="اللہ رحم کرنے والا ہے"))
    assert result.reason_code == "human_language_review_required"

def test_arabic_alignment_can_be_approved():
    assert validate_alignment(item()).decision == "approved"

def test_translated_claim_identity_and_order_are_immutable():
    require_claim_count_alignment(("c1","c2"), ("c1","c2"))
    with pytest.raises(ValueError):
        require_claim_count_alignment(("c1","c2"), ("c2","c1"))
