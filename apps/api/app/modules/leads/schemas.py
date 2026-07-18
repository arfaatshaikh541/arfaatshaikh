import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field


class LeadResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    status: str
    assigned_to_user_id: uuid.UUID | None
    created_at: datetime

    @classmethod
    def from_model(cls, lead) -> Self:
        return cls(
            id=lead.id,
            business_id=lead.business_id,
            status=lead.status,
            assigned_to_user_id=lead.assigned_to_user_id,
            created_at=lead.created_at,
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


# ---------------------------------------------------------------------------
# Lead Workspace (Milestone 6)
# ---------------------------------------------------------------------------


class LeadListItemResponse(BaseModel):
    """One row of the lead list - Lead + the Business fields the list
    view needs to display without a second round-trip per row."""

    lead_id: uuid.UUID
    business_id: uuid.UUID
    business_name: str
    category: str | None
    city: str | None
    country: str | None
    area: str | None
    phone: str | None
    email: str | None
    website: str | None
    rating: float | None
    review_count: int | None
    business_status: str | None
    status: str
    assigned_to_user_id: uuid.UUID | None
    score: float | None
    tags: list[str]
    created_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadListItemResponse]
    total: int
    page: int
    page_size: int


class NoteResponse(BaseModel):
    id: uuid.UUID
    author_user_id: uuid.UUID | None
    body: str
    created_at: datetime

    @classmethod
    def from_model(cls, note) -> Self:
        return cls(
            id=note.id,
            author_user_id=note.author_user_id,
            body=note.body,
            created_at=note.created_at,
        )


class AddNoteRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class AddTagRequest(BaseModel):
    tag: str = Field(min_length=1, max_length=50)


class TagResponse(BaseModel):
    tag: str


class ChangeStatusRequest(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=1000)


class StatusHistoryResponse(BaseModel):
    id: uuid.UUID
    from_status: str
    to_status: str
    changed_by_user_id: uuid.UUID | None
    changed_at: datetime
    note: str | None

    @classmethod
    def from_model(cls, entry) -> Self:
        return cls(
            id=entry.id,
            from_status=entry.from_status,
            to_status=entry.to_status,
            changed_by_user_id=entry.changed_by_user_id,
            changed_at=entry.changed_at,
            note=entry.note,
        )


class AssignRequest(BaseModel):
    assigned_to_user_id: uuid.UUID


class AssignmentResponse(BaseModel):
    id: uuid.UUID
    assigned_to_user_id: uuid.UUID
    assigned_by_user_id: uuid.UUID | None
    assigned_at: datetime
    unassigned_at: datetime | None

    @classmethod
    def from_model(cls, entry) -> Self:
        return cls(
            id=entry.id,
            assigned_to_user_id=entry.assigned_to_user_id,
            assigned_by_user_id=entry.assigned_by_user_id,
            assigned_at=entry.assigned_at,
            unassigned_at=entry.unassigned_at,
        )


class BulkLeadIdsRequest(BaseModel):
    lead_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class BulkStatusRequest(BulkLeadIdsRequest):
    status: str


class BulkAssignRequest(BulkLeadIdsRequest):
    assigned_to_user_id: uuid.UUID


class BulkTagRequest(BulkLeadIdsRequest):
    tag: str = Field(min_length=1, max_length=50)


class LeadDetailResponse(BaseModel):
    lead: LeadResponse
    business_id: uuid.UUID
    latest_score: LeadScoreResponse | None
    opportunities: list[LeadOpportunityResponse]
    recommendations: list[LeadRecommendationResponse]
    notes: list[NoteResponse]
    tags: list[str]
    status_history: list[StatusHistoryResponse]
    assignment_history: list[AssignmentResponse]
    duplicate_candidates: list[DuplicateCandidateResponse]


class SavedViewCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    filters: dict


class SavedViewResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_by_user_id: uuid.UUID | None
    filters: dict
    created_at: datetime

    @classmethod
    def from_model(cls, view) -> Self:
        return cls(
            id=view.id,
            name=view.name,
            created_by_user_id=view.created_by_user_id,
            filters=view.filters,
            created_at=view.created_at,
        )
