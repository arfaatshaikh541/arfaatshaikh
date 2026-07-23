"""Policy-as-code schema (approved architecture §23): a structured, versioned
document -- never free-text or ad hoc rules interpreted loosely. control-api
owns policy_id/version/status/lifecycle; this service only ever receives the
constraint content plus enough identifying metadata to stamp an evaluation
record.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ResidencyConstraint(BaseModel):
    allowed_countries: list[str] = Field(default_factory=list)
    denied_countries: list[str] = Field(default_factory=list)


class OperatorConstraint(BaseModel):
    allowed: list[str] = Field(default_factory=list)
    denied: list[str] = Field(default_factory=list)


class ConfidentialComputingConstraint(BaseModel):
    required: bool = False


class CrossBorderConstraint(BaseModel):
    backup_allowed_countries: list[str] = Field(default_factory=list)
    failover_allowed_countries: list[str] = Field(default_factory=list)


EncryptionKeyOwnership = Literal["customer_managed", "provider_managed"]


class EncryptionConstraint(BaseModel):
    key_ownership: EncryptionKeyOwnership | None = None


class PolicyDocument(BaseModel):
    """The evaluatable content of one sovereignty policy version. Every
    field is optional at this layer (an absent constraint block imposes no
    restriction) -- deny-by-default is enforced by how each constraint is
    evaluated (see evaluate.py), not by requiring every field be present.
    """

    residency: ResidencyConstraint = Field(default_factory=ResidencyConstraint)
    operators: OperatorConstraint = Field(default_factory=OperatorConstraint)
    confidential_computing: ConfidentialComputingConstraint = Field(
        default_factory=ConfidentialComputingConstraint
    )
    cross_border: CrossBorderConstraint = Field(default_factory=CrossBorderConstraint)
    encryption: EncryptionConstraint = Field(default_factory=EncryptionConstraint)


PlacementRole = Literal["primary", "backup", "failover"]


class EvaluationCandidate(BaseModel):
    """The workload + candidate-location facts a placement decision is being
    evaluated against. Every field the policy engine actually checks is
    required and has no permissive default -- an evaluator that silently
    assumed "unknown" satisfies a hard constraint would violate deny-by-default.
    """

    country: str = Field(
        min_length=2, max_length=2, description="ISO 3166-1 alpha-2 of the candidate location"
    )
    operator_id: str
    confidential_computing_available: bool
    placement_role: PlacementRole = "primary"
    encryption_key_ownership: EncryptionKeyOwnership | None = None


class EvaluationRequest(BaseModel):
    policy_id: str
    policy_version: int
    policy: PolicyDocument
    candidate: EvaluationCandidate


Decision = Literal["allow", "deny"]


class EvaluationResult(BaseModel):
    decision: Decision
    reason_codes: list[str]
    policy_id: str
    policy_version: int
    inputs_hash: str
    evaluated_at: str
