# Authorization Model

## Permission Catalog (global, versioned in code + seed migration)

```
leads.view          leads.create        leads.update        leads.delete
leads.assign         conversations.view  conversations.reply appointments.manage
workflows.manage     reports.view        users.manage        settings.manage
exports.create
```

Additional Milestone-1-relevant permissions used by settings/users screens:
`roles.manage`, `billing.view`.

The catalog lives in `app/core/permissions.py` as the single source of
truth and is synced into the `permissions` table by a migration + is
idempotently re-synced by the seed script, so new permissions added in
later milestones (e.g. `workflows.manage` is already reserved above) don't
require a manual SQL step.

## Default Tenant Roles → Permission Grants

| Role            | Grants |
|-----------------|--------|
| Tenant Owner    | all permissions, plus implicit ability to manage billing and delete the tenant |
| Administrator   | all except tenant deletion/billing |
| Manager         | leads.*, conversations.*, appointments.manage, reports.view, exports.create, workflows.manage |
| Sales Agent     | leads.view, leads.create, leads.update, leads.assign (self only, enforced in service layer), conversations.*, appointments.manage |
| Support Agent   | leads.view, conversations.*, appointments.manage |
| Viewer          | leads.view, conversations.view, reports.view |

These are seeded per-tenant as real `roles` rows (`is_system=true`) when a
tenant is created, so a tenant admin can later add custom roles alongside
them without affecting the defaults, and can adjust a *copy* without
mutating another tenant.

## Platform Role

`Platform Super Admin` is not a tenant role. It is the boolean
`users.is_platform_super_admin`, checked by the `get_platform_admin`
dependency, used exclusively under `/api/platform/*`. It carries no
implicit tenant permissions — a super admin does not automatically gain
`leads.view` inside a tenant; any tenant-data access goes through the
explicit, audited support-access path described in the tenant isolation
strategy (full support-access/impersonation UI is a Milestone 6 item;
Milestone 1 ships the audit-logging primitive and the super-admin flag/
dependency it depends on).

## Enforcement

- `require_permission("leads.view")` is a FastAPI dependency factory that:
  1. Depends on `get_current_membership` (which already verified tenant
     membership — see tenant isolation strategy).
  2. Loads the permission codes for the membership's `role_id` (joined
     query, cached per-request only, never cached across requests).
  3. Raises `403` if the required code is absent.
- Permissions are checked **per-endpoint**, not per-UI-element. The
  frontend also hides/disables actions the user can't perform, but this is
  a UX affordance only — it is never the security boundary.
- Bulk actions (Module 5) re-check the permission for every item in the
  batch inside the service layer, not just once for the batch request, so
  a permission check can't be bypassed by batching.

## Testing

`apps/api/tests/test_authorization.py` parametrizes every protected route
against each default role, asserting the expected `200`/`403` outcome, so
a future contributor who forgets a `require_permission(...)` dependency on
a new route gets a failing test rather than a silent hole.
