"""Source of truth for permission keys, module keys, role sets and enums.

These literal values MUST stay identical to
packages/security-contracts/src/index.ts. A contract test
(tests/test_security_contracts_sync.py) fails CI if they drift.
"""

from __future__ import annotations

PERMISSIONS: tuple[str, ...] = (
    "assets.view",
    "assets.manage",
    "integrations.view",
    "integrations.manage",
    "findings.view",
    "findings.assign",
    "findings.accept_risk",
    "findings.remediate",
    "actions.view",
    "actions.execute_safe",
    "actions.approve_disruptive",
    "incidents.view",
    "incidents.manage",
    "incidents.declare",
    "incidents.close",
    "evidence.view",
    "evidence.export",
    "playbooks.view",
    "playbooks.manage",
    "automations.manage",
    "compliance.view",
    "compliance.manage",
    "reports.view",
    "trust_passport.manage",
    "users.manage",
    "roles.manage",
    "settings.manage",
    "subscriptions.view",
    "platform.tenants.manage",
    "platform.support_access",
    "platform.audit.view",
)

TENANT_ROLES: tuple[str, ...] = (
    "tenant_owner",
    "security_administrator",
    "security_analyst",
    "it_administrator",
    "compliance_manager",
    "incident_responder",
    "executive_viewer",
    "read_only_auditor",
)

PLATFORM_ROLES: tuple[str, ...] = (
    "platform_super_admin",
    "platform_security_operator",
    "platform_support_engineer",
    "platform_auditor",
)

TENANT_STATUSES: tuple[str, ...] = ("trial", "active", "read_only", "suspended", "archived")

MODULES: tuple[str, ...] = (
    "asset_inventory",
    "attack_surface",
    "identity_security",
    "email_security",
    "endpoint_security",
    "network_security",
    "cloud_security",
    "application_security",
    "data_security",
    "vulnerability_management",
    "threat_intelligence",
    "detection_correlation",
    "cyber_autopilot",
    "incident_response",
    "backup_resilience",
    "employee_security",
    "compliance",
    "third_party_risk",
    "trust_passport",
    "executive_reporting",
    "managed_soc",
)

AUTOMATION_MODES: tuple[str, ...] = ("observe", "guided", "balanced", "autopilot", "lockdown")

ACTION_SAFETY_CLASSES: tuple[int, ...] = (0, 1, 2, 3, 4)

# Milestone 1 baseline tenant-role -> permission mapping.
DEFAULT_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "tenant_owner": tuple(p for p in PERMISSIONS if not p.startswith("platform.")),
    "security_administrator": (
        "assets.view", "assets.manage",
        "integrations.view", "integrations.manage",
        "findings.view", "findings.assign", "findings.accept_risk", "findings.remediate",
        "actions.view", "actions.execute_safe", "actions.approve_disruptive",
        "incidents.view", "incidents.manage", "incidents.declare", "incidents.close",
        "evidence.view", "evidence.export",
        "playbooks.view", "playbooks.manage", "automations.manage",
        "trust_passport.manage",
        "users.manage",
        "reports.view", "subscriptions.view",
    ),
    "security_analyst": (
        "assets.view", "integrations.view",
        "findings.view", "findings.assign", "findings.remediate",
        "actions.view", "actions.execute_safe",
        "incidents.view", "incidents.declare",
        "evidence.view",
        "playbooks.view",
        "reports.view",
    ),
    "it_administrator": (
        "assets.view", "assets.manage",
        "integrations.view", "integrations.manage",
        "findings.view", "findings.remediate",
        "actions.view",
        "reports.view",
    ),
    "compliance_manager": (
        "assets.view", "findings.view", "findings.accept_risk",
        "evidence.view", "evidence.export",
        "compliance.view", "compliance.manage",
        "trust_passport.manage",
        "reports.view",
    ),
    "incident_responder": (
        "assets.view", "findings.view",
        "actions.view", "actions.execute_safe",
        "incidents.view", "incidents.manage", "incidents.declare", "incidents.close",
        "evidence.view", "evidence.export",
        "reports.view",
    ),
    "executive_viewer": (
        "assets.view", "findings.view", "incidents.view",
        "reports.view", "subscriptions.view",
    ),
    "read_only_auditor": (
        "assets.view", "integrations.view", "findings.view",
        "actions.view", "incidents.view", "evidence.view",
        "playbooks.view", "compliance.view", "reports.view",
    ),
}

# Platform roles get an entirely separate permission set — never merged with
# tenant permissions, and never evaluated against a tenant-scoped check.
DEFAULT_PLATFORM_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "platform_super_admin": (
        "platform.tenants.manage", "platform.support_access", "platform.audit.view",
    ),
    "platform_security_operator": ("platform.support_access", "platform.audit.view"),
    "platform_support_engineer": ("platform.support_access",),
    "platform_auditor": ("platform.audit.view",),
}
