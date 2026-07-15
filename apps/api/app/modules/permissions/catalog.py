"""The full tenant-assignable permission catalog plus the disjoint set of
platform-only permissions.

This is the single source of truth for what a permission code means and
whether it may ever be attached to a tenant-scoped role. Platform
permissions are structurally excluded from tenant role management (see
`app.modules.permissions.service.assign_permissions_to_role`) — a tenant
administrator cannot construct a role that contains one, because the
tenant-role-assignable list below never includes them.
"""

# code -> human description
TENANT_PERMISSIONS: dict[str, str] = {
    "leads.view": "View leads",
    "leads.create": "Create leads",
    "leads.update": "Update leads",
    "leads.delete": "Delete leads",
    "leads.assign": "Assign leads to staff",
    "leads.export": "Export lead data",
    "services.manage": "Manage services and qualification forms",
    "scoring.manage": "Manage lead scoring rules and thresholds",
    "assignment.manage": "Manage lead assignment rules",
    "communications.manage": "Manage email templates and delivery logs",
    "tasks.view": "View tasks",
    "tasks.manage": "Create, update, and complete tasks",
    "appointments.view": "View appointments",
    "appointments.manage": "Create, update, and cancel appointments",
    "availability.manage": "Manage appointment types and other staff members' availability",
    "workflows.view": "View workflow automations",
    "workflows.manage": "Create and edit workflow automations",
    "proposals.view": "View proposals",
    "proposals.manage": "Create and edit proposals",
    "documents.view": "View documents",
    "documents.upload": "Upload documents",
    "documents.manage": "Create and cancel document requests",
    "documents.approve": "Approve or reject documents",
    "onboarding.view": "View onboarding templates and cases",
    "onboarding.manage": "Create onboarding templates and start or cancel cases",
    "portal.manage": "Manage client portal content and access",
    "deadlines.manage": "Manage compliance and service deadlines",
    "reports.view": "View reports",
    "users.manage": "Invite, update, and remove tenant users",
    "roles.manage": "Create and edit tenant roles",
    "settings.manage": "Manage tenant settings and branding",
    "subscriptions.view": "View subscription plan and module access",
    "integrations.manage": "Configure third-party integrations",
}

PLATFORM_PERMISSIONS: dict[str, str] = {
    "platform.tenants.manage": "Create, activate, suspend, and archive tenants",
    "platform.plans.manage": "Manage subscription plans and features",
    "platform.overrides.manage": "Grant tenant feature overrides and add-ons",
    "platform.usage.view": "View tenant usage across the platform",
    "platform.audit.view": "View audit logs and support-access logs across tenants",

}

ALL_PERMISSIONS: dict[str, str] = {**TENANT_PERMISSIONS, **PLATFORM_PERMISSIONS}

# Default tenant roles and the permission codes each one grants.
# "Tenant Owner" implicitly gets every tenant permission (enforced in seed
# data, not hardcoded as a bypass in the authorization check itself).
DEFAULT_TENANT_ROLES: dict[str, list[str]] = {
    "Tenant Owner": list(TENANT_PERMISSIONS.keys()),
    "Administrator": [
        "leads.view", "leads.create", "leads.update", "leads.delete", "leads.assign", "leads.export",
        "services.manage", "scoring.manage", "assignment.manage", "communications.manage",
        "tasks.view", "tasks.manage",
        "appointments.view", "appointments.manage", "availability.manage",
        "workflows.view", "workflows.manage",
        "proposals.view", "proposals.manage",
        "documents.view", "documents.upload", "documents.manage", "documents.approve",
        "onboarding.view", "onboarding.manage",
        "portal.manage", "deadlines.manage",
        "reports.view",
        "users.manage", "roles.manage", "settings.manage",
        "subscriptions.view", "integrations.manage",
    ],
    "Manager": [
        "leads.view", "leads.create", "leads.update", "leads.assign", "leads.export",
        "services.manage", "scoring.manage", "assignment.manage",
        "tasks.view", "tasks.manage",
        "appointments.view", "appointments.manage", "availability.manage",
        "workflows.view",
        "proposals.view", "proposals.manage",
        "documents.view", "documents.approve", "documents.manage",
        "onboarding.view", "onboarding.manage",
        "deadlines.manage",
        "reports.view",
        "subscriptions.view",
    ],
    "Sales Agent": [
        "leads.view", "leads.create", "leads.update",
        "tasks.view", "tasks.manage",
        "appointments.view", "appointments.manage",
        "proposals.view",
        "documents.view", "documents.upload", "documents.manage",
        "onboarding.view",
        "reports.view",
    ],
    "Support Agent": [
        "leads.view",
        "tasks.view", "tasks.manage",
        "appointments.view",
        "documents.view", "documents.upload", "documents.manage",
        "onboarding.view",
        "portal.manage",
        "deadlines.manage",
    ],
    "Viewer": [
        "leads.view", "tasks.view", "appointments.view", "workflows.view",
        "proposals.view", "documents.view", "onboarding.view", "reports.view",
    ],
}

PLATFORM_SUPER_ADMIN_ROLE_NAME = "Platform Super Admin"
