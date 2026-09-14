from __future__ import annotations
from dataclasses import dataclass

PERSONALIZATION_POLICY_VERSION = "personalization-safety-v1"
ALLOWED_SIGNALS = {"explicit_preference", "course_progress", "bookmark", "dismissal", "language_choice", "accessibility_change"}
FORBIDDEN_INFERENCES = {"piety", "sect", "madhhab", "morality", "spiritual_rank", "religious_worth", "ethnicity", "politics", "health", "disability"}

@dataclass(frozen=True)
class RecommendationInput:
    candidate_key: str
    explicit_topic_match: bool = False
    prerequisite_met: bool = False
    language_available: bool = True
    previously_dismissed: bool = False
    completed: bool = False
    personalization_enabled: bool = True
    recommendation_mode: str = "standard"
    signal_types: tuple[str, ...] = ()
    inferred_attributes: tuple[str, ...] = ()

@dataclass(frozen=True)
class RecommendationResult:
    decision: str
    score: int
    reason_codes: tuple[str, ...]
    explanation: str


def validate_signal_types(signal_types: tuple[str, ...]) -> None:
    unknown = set(signal_types) - ALLOWED_SIGNALS
    if unknown:
        raise ValueError(f"unsupported personalization signals: {', '.join(sorted(unknown))}")


def evaluate_recommendation(item: RecommendationInput) -> RecommendationResult:
    validate_signal_types(item.signal_types)
    forbidden = set(item.inferred_attributes) & FORBIDDEN_INFERENCES
    if forbidden:
        return RecommendationResult("blocked", 0, ("forbidden_sensitive_inference",), "Recommendation blocked because it attempted to infer protected or religiously sensitive attributes.")
    if not item.personalization_enabled or item.recommendation_mode == "off":
        return RecommendationResult("suppressed", 0, ("personalization_disabled",), "Personalized recommendations are disabled.")
    if item.previously_dismissed:
        return RecommendationResult("suppressed", 0, ("user_dismissed_candidate",), "The user previously dismissed this item.")
    if item.completed:
        return RecommendationResult("suppressed", 0, ("candidate_already_completed",), "The item has already been completed.")
    if not item.language_available:
        return RecommendationResult("suppressed", 0, ("preferred_language_unavailable",), "The item is unavailable in the user's selected language.")
    if not item.prerequisite_met:
        return RecommendationResult("suppressed", 0, ("prerequisite_not_met",), "A required prerequisite has not been completed.")
    score = 50
    reasons = ["prerequisite_met", "preferred_language_available"]
    if item.explicit_topic_match:
        score += 35
        reasons.append("explicit_topic_preference")
    if "bookmark" in item.signal_types:
        score += 10
        reasons.append("related_to_bookmark")
    score = min(score, 100)
    if item.recommendation_mode == "minimal" and score < 80:
        return RecommendationResult("suppressed", score, tuple(reasons + ["minimal_mode_threshold"]), "The candidate did not meet the minimal-mode threshold.")
    return RecommendationResult("recommended", score, tuple(reasons), "Recommended using explicit educational preferences and progress only.")


def validate_accessibility_profile(text_scale_percent: int, *, reduced_motion: bool, high_contrast: bool) -> dict[str, object]:
    if not 75 <= text_scale_percent <= 200:
        raise ValueError("text scale must be between 75 and 200 percent")
    return {"text_scale_percent": text_scale_percent, "reduced_motion": reduced_motion, "high_contrast": high_contrast, "policy_version": PERSONALIZATION_POLICY_VERSION}
