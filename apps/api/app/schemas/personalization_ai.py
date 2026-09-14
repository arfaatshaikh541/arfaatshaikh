from pydantic import BaseModel, Field

class RecommendationRequest(BaseModel):
    candidate_key: str = Field(min_length=1, max_length=200)
    explicit_topic_match: bool = False
    prerequisite_met: bool = False
    language_available: bool = True
    previously_dismissed: bool = False
    completed: bool = False
    personalization_enabled: bool = True
    recommendation_mode: str = Field(default="standard", pattern="^(off|minimal|standard)$")
    signal_types: list[str] = Field(default_factory=list, max_length=20)
    inferred_attributes: list[str] = Field(default_factory=list, max_length=20)

class AccessibilityRequest(BaseModel):
    text_scale_percent: int = Field(ge=75, le=200)
    reduced_motion: bool = False
    high_contrast: bool = False
