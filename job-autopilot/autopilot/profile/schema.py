"""Editable career preferences and application rules (no hardcoded values)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SalaryPref(BaseModel):
    amount: float | None = None
    currency: str | None = None
    interval: Literal["year", "month", "hour"] = "month"


class Preferences(BaseModel):
    target_roles: list[str] = []
    target_industries: list[str] = []
    target_locations: list[str] = []
    workplace_types: list[Literal["remote", "hybrid", "onsite"]] = []
    min_salary: SalaryPref = SalaryPref()
    max_commute_km: float | None = None
    max_required_experience_years: float | None = None
    exclude_keywords: list[str] = []
    exclude_companies: list[str] = []
    employment_types: list[str] = []  # e.g. full-time, part-time, contract, internship
    keywords: list[str] = []
    required_skills: list[str] = []
    optional_skills: list[str] = []
    min_match_score: float = Field(60.0, ge=0, le=100)


class Rules(BaseModel):
    require_target_role: bool = True
    require_location_match: bool = True
    require_employment_type_match: bool = True
    require_min_score: bool = True
    skip_if_experience_exceeds: bool = True
    # What to do when an automatic-apply rule fails.
    on_rule_failure: Literal["SKIP", "REVIEW"] = "SKIP"
    # What to do when a mandatory question cannot be answered from verified data.
    on_unknown_mandatory_answer: Literal["SKIP", "REVIEW"] = "REVIEW"
    # INFERRED facts are never used for factual answers unless explicitly allowed.
    allow_inferred_answers: bool = False
    # If true, a skill absent from your verified skills is answered "No" rather than UNKNOWN.
    treat_unlisted_skills_as_no: bool = False
    # Voluntary EEO questions: choose a "decline to answer" option only if you allow it.
    eeo_decline_if_available: bool = False
    # Explicit consent to accept an employer's privacy notice / data processing checkbox.
    accept_privacy_notices: bool = False
    # Answer for "How did you hear about us?"; None = UNKNOWN.
    referral_source_answer: str | None = None
    generate_cover_letters: bool = False
