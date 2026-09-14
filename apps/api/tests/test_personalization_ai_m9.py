import pytest
from app.services.personalization_ai import RecommendationInput, evaluate_recommendation, validate_accessibility_profile, validate_signal_types

def test_explicit_preference_and_progress_can_recommend():
    result = evaluate_recommendation(RecommendationInput(candidate_key="course:sabr", explicit_topic_match=True, prerequisite_met=True, signal_types=("explicit_preference",)))
    assert result.decision == "recommended" and result.score == 85

def test_forbidden_religious_inference_is_blocked():
    result = evaluate_recommendation(RecommendationInput(candidate_key="x", prerequisite_met=True, inferred_attributes=("piety",)))
    assert result.decision == "blocked"

def test_sect_and_spiritual_rank_are_never_personalization_signals():
    for value in ("sect", "madhhab", "spiritual_rank", "religious_worth"):
        assert evaluate_recommendation(RecommendationInput(candidate_key="x", prerequisite_met=True, inferred_attributes=(value,))).decision == "blocked"

def test_user_can_disable_personalization():
    assert evaluate_recommendation(RecommendationInput(candidate_key="x", prerequisite_met=True, personalization_enabled=False)).decision == "suppressed"

def test_dismissed_or_completed_items_are_suppressed():
    assert evaluate_recommendation(RecommendationInput(candidate_key="x", prerequisite_met=True, previously_dismissed=True)).decision == "suppressed"
    assert evaluate_recommendation(RecommendationInput(candidate_key="x", prerequisite_met=True, completed=True)).decision == "suppressed"

def test_language_and_prerequisites_fail_closed():
    assert evaluate_recommendation(RecommendationInput(candidate_key="x", prerequisite_met=False)).reason_codes == ("prerequisite_not_met",)
    assert evaluate_recommendation(RecommendationInput(candidate_key="x", prerequisite_met=True, language_available=False)).reason_codes == ("preferred_language_unavailable",)

def test_unknown_behavioral_signal_is_rejected():
    with pytest.raises(ValueError):
        validate_signal_types(("secret_profile",))

def test_accessibility_preferences_are_validated_not_ranked():
    data = validate_accessibility_profile(150, reduced_motion=True, high_contrast=True)
    assert data["text_scale_percent"] == 150
    with pytest.raises(ValueError):
        validate_accessibility_profile(250, reduced_motion=False, high_contrast=False)
