import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel


class LeadResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    status: str
    created_at: datetime

    @classmethod
    def from_model(cls, lead) -> Self:
        return cls(
            id=lead.id, business_id=lead.business_id, status=lead.status, created_at=lead.created_at
        )


class ScoreFactorResponse(BaseModel):
    key: str
    label: str
    score: float
    max_score: float
    explanation: str
    evidence: dict


class LeadScoreResponse(BaseModel):
    id: uuid.UUID
    algorithm_version: str
    total_score: float
    max_score: float
    factors: list[ScoreFactorResponse]
    calculated_at: datetime


class LeadOpportunityResponse(BaseModel):
    id: uuid.UUID
    opportunity_type: str
    confidence: float
    evidence_reference: dict
    detected_at: datetime

    @classmethod
    def from_model(cls, opportunity) -> Self:
        return cls(
            id=opportunity.id,
            opportunity_type=opportunity.opportunity_type,
            confidence=float(opportunity.confidence),
            evidence_reference=opportunity.evidence_reference,
            detected_at=opportunity.detected_at,
        )


class LeadRecommendationResponse(BaseModel):
    id: uuid.UUID
    recommendation_type: str
    confidence: float
    supporting_opportunity_ids: list[str]
    recommended_at: datetime


class ScoreLeadResponse(BaseModel):
    lead: LeadResponse
    score: LeadScoreResponse
    opportunities: list[LeadOpportunityResponse]
    recommendations: list[LeadRecommendationResponse]


class DuplicateCandidateResponse(BaseModel):
    id: uuid.UUID
    business_id_a: uuid.UUID
    business_id_b: uuid.UUID
    match_type: str
    confidence: float
    matched_fields: dict
    status: str
    reviewed_at: datetime | None

    @classmethod
    def from_model(cls, candidate) -> Self:
        return cls(
            id=candidate.id,
            business_id_a=candidate.business_id_a,
            business_id_b=candidate.business_id_b,
            match_type=candidate.match_type,
            confidence=float(candidate.confidence),
            matched_fields=candidate.matched_fields,
            status=candidate.status,
            reviewed_at=candidate.reviewed_at,
        )


class MergeHistoryResponse(BaseModel):
    id: uuid.UUID
    winner_business_id: uuid.UUID
    loser_business_id: uuid.UUID
    match_type: str
    confidence: float
    moved_records: dict
    undone_at: datetime | None

    @classmethod
    def from_model(cls, merge_history) -> Self:
        return cls(
            id=merge_history.id,
            winner_business_id=merge_history.winner_business_id,
            loser_business_id=merge_history.loser_business_id,
            match_type=merge_history.match_type,
            confidence=float(merge_history.confidence),
            moved_records=merge_history.moved_records,
            undone_at=merge_history.undone_at,
        )
