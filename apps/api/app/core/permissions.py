"""Single source of truth for the global permission catalog.

Adding a permission here and re-running the seed script / migration sync
is the only supported way to introduce a new permission. See
docs/architecture/authorization-model.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDef:
    code: str
    description: str


PERMISSIONS: list[PermissionDef] = [
    PermissionDef("leads.view", "View leads"),
    PermissionDef("leads.create", "Create leads"),
    PermissionDef("leads.update", "Update leads"),
    PermissionDef("leads.delete", "Delete leads"),
    PermissionDef("leads.assign", "Assign leads to staff"),
    PermissionDef("conversations.view", "View conversations/messages"),
    PermissionDef("conversations.reply", "Reply to conversations"),
    PermissionDef("appointments.manage", "Create, reschedule and cancel appointments"),
    PermissionDef("workflows.manage", "Create and edit automation workflows"),
    PermissionDef("reports.view", "View reports and dashboards"),
    PermissionDef("users.manage", "Invite, update and deactivate tenant users"),
    PermissionDef("roles.manage", "Create and edit tenant roles and permission grants"),
    PermissionDef("settings.manage", "Update tenant settings, branding and configuration"),
    PermissionDef("exports.create", "Generate data exports"),
    PermissionDef("billing.view", "View subscription and billing information"),
]

PERMISSION_CODES: frozenset[str] = frozenset(p.code for p in PERMISSIONS)
