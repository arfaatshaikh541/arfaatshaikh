"""The Capability contract: a self-describing wrapper around an
action_type that already has a real, tested handler somewhere in this
codebase (a connector, or a built-in deterministic action). This module
never introduces a new execution path -- every Capability's
`action_type` is submitted through the existing, single-choke-point
`ActionBroker`, exactly like every other caller in this codebase. What's
new here is the metadata: domain, a human description, and enough about
how the underlying action verifies and reports itself that a planner
(human or model) can reason about what's available without reading
source code.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Capability:
    name: str  # matches an action_type registered with the ActionBroker
    description: str
    domain: str  # "sales" | "marketing" | "social" | "email" | ... -- a tag, not a hardcoded module
    tools: tuple[str, ...] = ()  # human-readable tool/provider names this relies on
    verification: str = ""  # what proves this action really happened, in plain language
    evidence_kind: str = ""  # what the outcome message is expected to contain as proof
    inputs: tuple[str, ...] = field(default_factory=tuple)  # expected request.params keys
