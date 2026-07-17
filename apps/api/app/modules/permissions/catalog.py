"""Canonical permission catalog and default role -> permission grants.

This is the single source of truth for both the seed script (which writes
these rows into the `permissions` / `roles` / `role_permissions` tables)
and any code that needs to reference a permission key by name. Enforcement
is table-driven at runtime (via role_permissions), not via hardcoded
role-name checks, so a tenant's custom roles work the same way.
"""

PERMISSIONS: list[tuple[str, str, str]] = [
    # (key, description, category)
    ("campaigns.view", "View campaigns", "campaigns"),
    ("campaigns.create", "Create campaigns", "campaigns"),
    ("campaigns.start", "Start/launch campaigns", "campaigns"),
    ("campaigns.pause", "Pause running campaigns", "campaigns"),
    ("campaigns.cancel", "Cancel campaigns", "campaigns"),
    ("campaigns.delete", "Delete campaigns", "campaigns"),
    ("leads.view", "View leads", "leads"),
    ("leads.edit", "Edit lead details", "leads"),
    ("leads.assign", "Assign leads to salespeople", "leads"),
    ("leads.export", "Export leads", "leads"),
    ("leads.delete", "Delete leads", "leads"),
    ("leads.change_status", "Change lead status", "leads"),
    ("integrations.view", "View integrations", "integrations"),
    ("integrations.manage", "Manage integrations", "integrations"),
    ("users.view", "View tenant users", "users"),
    ("users.manage", "Manage tenant users and invitations", "users"),
    ("roles.view", "View roles", "roles"),
    ("roles.manage", "Manage roles and permissions", "roles"),
    ("billing.view", "View billing", "billing"),
    ("billing.manage", "Manage billing and subscription", "billing"),
    ("usage.view", "View usage and credit history", "usage"),
    ("exports.view", "View exports", "exports"),
    ("exports.create", "Create exports", "exports"),
    ("audit.view", "View tenant audit log", "audit"),
    ("settings.manage", "Manage tenant settings", "settings"),
    ("platform.tenants.manage", "Manage tenants (platform)", "platform"),
    ("platform.jobs.manage", "Manage background jobs (platform)", "platform"),
    ("platform.audit.view", "View platform audit log (platform)", "platform"),
    ("platform.support_access", "Grant/use time-boxed support access (platform)", "platform"),
]

PERMISSION_KEYS = {p[0] for p in PERMISSIONS}

# Default tenant roles -> permission keys granted.
TENANT_ROLE_DEFAULTS: dict[str, list[str]] = {
    "Owner": [k for k in PERMISSION_KEYS if not k.startswith("platform.")],
    "Administrator": [
        "campaigns.view",
        "campaigns.create",
        "campaigns.start",
        "campaigns.pause",
        "campaigns.cancel",
        "campaigns.delete",
        "leads.view",
        "leads.edit",
        "leads.assign",
        "leads.export",
        "leads.delete",
        "leads.change_status",
        "integrations.view",
        "integrations.manage",
        "users.view",
        "users.manage",
        "roles.view",
        "roles.manage",
        "usage.view",
        "exports.view",
        "exports.create",
        "audit.view",
        "settings.manage",
    ],
    "Campaign Manager": [
        "campaigns.view",
        "campaigns.create",
        "campaigns.start",
        "campaigns.pause",
        "campaigns.cancel",
        "leads.view",
        "leads.edit",
        "leads.assign",
        "leads.export",
        "leads.change_status",
        "usage.view",
        "exports.view",
        "exports.create",
    ],
    "Sales Manager": [
        "leads.view",
        "leads.edit",
        "leads.assign",
        "leads.export",
        "leads.change_status",
        "exports.view",
        "exports.create",
    ],
    "Sales Representative": [
        "leads.view",
        "leads.edit",
        "leads.change_status",
    ],
    "Analyst": [
        "campaigns.view",
        "leads.view",
        "leads.export",
        "usage.view",
        "exports.view",
        "exports.create",
    ],
    "Billing Manager": [
        "billing.view",
        "billing.manage",
        "usage.view",
    ],
    "Read-Only Viewer": [
        "campaigns.view",
        "leads.view",
    ],
}

# Platform roles: tenant_id is NULL for all of these.
PLATFORM_ROLE_DEFAULTS: dict[str, list[str]] = {
    "Platform Super Admin": [
        "platform.tenants.manage",
        "platform.jobs.manage",
        "platform.audit.view",
        "platform.support_access",
    ],
    "Platform Support Engineer": [
        "platform.audit.view",
        "platform.support_access",
    ],
    "Platform Operations Manager": [
        "platform.tenants.manage",
        "platform.jobs.manage",
        "platform.audit.view",
    ],
    "Platform Auditor": [
        "platform.audit.view",
    ],
}
