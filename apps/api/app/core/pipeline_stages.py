"""Default pipeline stage template, seeded per-tenant. Tenants may add,
rename or reorder stages afterward - these are just the starting set from
the Professional Services template. Never hardcode this list in the
frontend; it exists here only to seed real, editable `pipeline_stages`
rows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DefaultStageDef:
    slug: str
    name: str
    is_won: bool = False
    is_lost: bool = False


DEFAULT_PIPELINE_STAGES: list[DefaultStageDef] = [
    DefaultStageDef("new", "New"),
    DefaultStageDef("contacted", "Contacted"),
    DefaultStageDef("qualified", "Qualified"),
    DefaultStageDef("consultation_booked", "Consultation Booked"),
    DefaultStageDef("proposal_sent", "Proposal Sent"),
    DefaultStageDef("follow_up", "Follow-Up"),
    DefaultStageDef("won", "Won", is_won=True),
    DefaultStageDef("lost", "Lost", is_lost=True),
    DefaultStageDef("nurture", "Nurture"),
    DefaultStageDef("archived", "Archived"),
]

DEFAULT_SERVICES: list[str] = [
    "External Audit",
    "Internal Audit",
    "Corporate Tax",
    "VAT",
    "Accounting and Bookkeeping",
    "Financial Advisory",
    "Business Setup",
    "Company Liquidation",
    "Compliance Consultation",
]
