"""Aggregate diagnostic snapshot — one function pulling together
everything an owner or a support bundle would want to see at a glance:
capability status, audit chain integrity, and recent Security Guardian
activity. Real data from the real stores, not a canned response.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..governance.audit_log import AuditLog
from ..guardian import SecurityGuardian
from ..status import registry as status_registry


@dataclass
class DiagnosticReport:
    capability_status: dict
    audit_chain_valid: bool
    audit_entries_checked: int
    recent_guardian_events: list[dict]


def collect_diagnostics(audit: AuditLog, guardian: SecurityGuardian) -> DiagnosticReport:
    verification = audit.verify_chain()
    events = [
        {
            "detected_at": e.detected_at.isoformat(), "rule_name": e.rule_name,
            "detail": e.detail, "action_taken": e.action_taken,
        }
        for e in guardian.recent_events(limit=10)
    ]
    return DiagnosticReport(
        capability_status=status_registry.snapshot(),
        audit_chain_valid=verification.valid,
        audit_entries_checked=verification.entries_checked,
        recent_guardian_events=events,
    )
