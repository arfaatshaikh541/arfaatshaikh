"""Default tenant roles and their permission grants, seeded per-tenant.

See docs/architecture/authorization-model.md for the rationale.
"""

from __future__ import annotations

from dataclasses import dataclass

_ALL = [
    "leads.view",
    "leads.create",
    "leads.update",
    "leads.delete",
    "leads.assign",
    "conversations.view",
    "conversations.reply",
    "appointments.manage",
    "workflows.manage",
    "reports.view",
    "users.manage",
    "roles.manage",
    "settings.manage",
    "exports.create",
    "billing.view",
]


@dataclass(frozen=True)
class DefaultRoleDef:
    slug: str
    name: str
    permissions: tuple[str, ...]


DEFAULT_ROLES: list[DefaultRoleDef] = [
    DefaultRoleDef("owner", "Tenant Owner", tuple(_ALL)),
    DefaultRoleDef(
        "administrator",
        "Administrator",
        tuple(p for p in _ALL if p != "billing.view"),
    ),
    DefaultRoleDef(
        "manager",
        "Manager",
        (
            "leads.view",
            "leads.create",
            "leads.update",
            "leads.delete",
            "leads.assign",
            "conversations.view",
            "conversations.reply",
            "appointments.manage",
            "reports.view",
            "exports.create",
            "workflows.manage",
        ),
    ),
    DefaultRoleDef(
        "sales_agent",
        "Sales Agent",
        (
            "leads.view",
            "leads.create",
            "leads.update",
            "leads.assign",
            "conversations.view",
            "conversations.reply",
            "appointments.manage",
        ),
    ),
    DefaultRoleDef(
        "support_agent",
        "Support Agent",
        (
            "leads.view",
            "conversations.view",
            "conversations.reply",
            "appointments.manage",
        ),
    ),
    DefaultRoleDef(
        "viewer",
        "Viewer",
        (
            "leads.view",
            "conversations.view",
            "reports.view",
        ),
    ),
]

DEFAULT_ROLE_BY_SLUG: dict[str, DefaultRoleDef] = {r.slug: r for r in DEFAULT_ROLES}
