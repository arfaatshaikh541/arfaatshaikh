/**
 * GRIDKEEP security contracts — shared, versioned source of truth for
 * permission keys, module keys, tenant states and automation enums.
 *
 * These literal string values MUST stay identical to
 * apps/api/core/security_contracts.py. A contract test
 * (apps/api/tests/test_security_contracts_sync.py) fails CI if they drift.
 */

export const PERMISSIONS = [
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
] as const;

export type Permission = (typeof PERMISSIONS)[number];

export const TENANT_ROLES = [
  "tenant_owner",
  "security_administrator",
  "security_analyst",
  "it_administrator",
  "compliance_manager",
  "incident_responder",
  "executive_viewer",
  "read_only_auditor",
] as const;

export type TenantRole = (typeof TENANT_ROLES)[number];

export const PLATFORM_ROLES = [
  "platform_super_admin",
  "platform_security_operator",
  "platform_support_engineer",
  "platform_auditor",
] as const;

export type PlatformRole = (typeof PLATFORM_ROLES)[number];

export const TENANT_STATUSES = [
  "trial",
  "active",
  "read_only",
  "suspended",
  "archived",
] as const;

export type TenantStatus = (typeof TENANT_STATUSES)[number];

export const MODULES = [
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
] as const;

export type ModuleKey = (typeof MODULES)[number];

export const AUTOMATION_MODES = [
  "observe",
  "guided",
  "balanced",
  "autopilot",
  "lockdown",
] as const;

export type AutomationMode = (typeof AUTOMATION_MODES)[number];

export const ACTION_SAFETY_CLASSES = [0, 1, 2, 3, 4] as const;
export type ActionSafetyClass = (typeof ACTION_SAFETY_CLASSES)[number];

/** Default tenant-role -> permission mapping (Milestone 1 baseline). */
export const DEFAULT_ROLE_PERMISSIONS: Record<TenantRole, Permission[]> = {
  tenant_owner: [...PERMISSIONS].filter((p) => !p.startsWith("platform.")) as Permission[],
  security_administrator: [
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
  ],
  security_analyst: [
    "assets.view", "integrations.view",
    "findings.view", "findings.assign", "findings.remediate",
    "actions.view", "actions.execute_safe",
    "incidents.view", "incidents.declare",
    "evidence.view",
    "playbooks.view",
    "reports.view",
  ],
  it_administrator: [
    "assets.view", "assets.manage",
    "integrations.view", "integrations.manage",
    "findings.view", "findings.remediate",
    "actions.view",
    "reports.view",
  ],
  compliance_manager: [
    "assets.view", "findings.view", "findings.accept_risk",
    "evidence.view", "evidence.export",
    "compliance.view", "compliance.manage",
    "trust_passport.manage",
    "reports.view",
  ],
  incident_responder: [
    "assets.view", "findings.view",
    "actions.view", "actions.execute_safe",
    "incidents.view", "incidents.manage", "incidents.declare", "incidents.close",
    "evidence.view", "evidence.export",
    "reports.view",
  ],
  executive_viewer: [
    "assets.view", "findings.view", "incidents.view",
    "reports.view", "subscriptions.view",
  ],
  read_only_auditor: [
    "assets.view", "integrations.view", "findings.view",
    "actions.view", "incidents.view", "evidence.view",
    "playbooks.view", "compliance.view", "reports.view",
  ],
};

/** Default platform-role -> permission mapping (Milestone 1 baseline). */
export const DEFAULT_PLATFORM_ROLE_PERMISSIONS: Record<PlatformRole, Permission[]> = {
  platform_super_admin: ["platform.tenants.manage", "platform.support_access", "platform.audit.view"],
  platform_security_operator: ["platform.support_access", "platform.audit.view"],
  platform_support_engineer: ["platform.support_access"],
  platform_auditor: ["platform.audit.view"],
};
