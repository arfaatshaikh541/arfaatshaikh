from __future__ import annotations

from aura_core.diagnostics import collect_diagnostics
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.guardian import SecurityGuardian


def test_collect_diagnostics_reports_a_healthy_empty_system(tmp_path):
    db_url = f"sqlite:///{tmp_path}/diag.db"
    audit = AuditLog(db_url)
    policy = PolicyEngine(db_url)
    guardian = SecurityGuardian(audit, policy, db_url)

    report = collect_diagnostics(audit, guardian)

    assert report.audit_chain_valid is True
    assert report.audit_entries_checked == 0
    assert report.recent_guardian_events == []
    assert isinstance(report.capability_status, dict)
    assert "memory.store" in report.capability_status


def test_collect_diagnostics_surfaces_guardian_events(tmp_path):
    db_url = f"sqlite:///{tmp_path}/diag2.db"
    audit = AuditLog(db_url)
    policy = PolicyEngine(db_url)
    guardian = SecurityGuardian(audit, policy, db_url)
    guardian.freeze("test drill")

    report = collect_diagnostics(audit, guardian)

    assert len(report.recent_guardian_events) == 1
    assert report.recent_guardian_events[0]["rule_name"] == "manual"
