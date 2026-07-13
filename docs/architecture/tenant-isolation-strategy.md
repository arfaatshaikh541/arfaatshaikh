# Tenant Isolation Strategy

## Principle

**The backend, not the browser, decides which tenant a request operates
on.** A client may *indicate* which tenant it wants (e.g. because a user
belongs to three tenants and picked one in the UI), but that indication is
always re-verified against the database before it is trusted, on every
request, for every tenant-scoped operation.

## Mechanism

1. Every authenticated request carries a session (see
   `authentication-strategy.md`) that resolves to a `user_id`.
2. The client also sends an `X-Tenant-Id` header (the frontend stores the
   "active tenant" and attaches it to every API call).
3. A FastAPI dependency, `get_current_membership`, does the following on
   *every* protected request:
   - Loads the `Membership` row for `(user_id, tenant_id)` from the
     database (not from any cached token claim).
   - Rejects with `403` if no such membership exists, if the membership
     status is not `active`, or if the tenant status is `suspended` or
     `archived`.
   - Returns a `MembershipContext(tenant_id, user_id, role, permissions)`
     object that is the **only** source of tenant identity used downstream.
4. Routers never read `tenant_id` from the request body, query string, or
   path for the purpose of scoping a query. Any `tenant_id`-shaped field
   in a request payload is ignored/rejected if present — the verified
   context is what's used.
5. Every repository method that touches a tenant-owned table takes the
   verified `tenant_id` as a mandatory first argument and includes it in
   the `WHERE` clause (`WHERE tenant_id = :tenant_id AND id = :id`), so a
   lookup for another tenant's row returns "not found," not "forbidden" —
   this avoids leaking existence of other tenants' data.
6. Foreign keys that cross entities *within* a tenant (e.g. a future
   `Lead.assigned_user_id` pointing at a `Membership`) are validated at the
   service layer to belong to the same `tenant_id` before being persisted,
   preventing cross-tenant object references even when both IDs are
   syntactically valid UUIDs.

## Platform Super Admin

`users.is_platform_super_admin` is checked by a **separate** dependency,
`get_platform_admin`, used only on `/api/platform/*` routes. It does not
bypass `get_current_membership` on tenant routes — a super admin viewing
tenant data goes through an explicit, separately-audited "support access"
path, not the normal membership path, and every such access is written to
`audit_logs` with `event_type='super_admin.tenant.viewed'` (or similar)
including the actor and target tenant.

## Testing

`apps/api/tests/test_tenant_isolation.py` is the canonical isolation test
suite and the template for all future tenant-owned resources. Pattern for
every new resource type going forward:

1. Create two tenants, A and B, each with a user and a resource row.
2. Authenticate as tenant A's user.
3. Attempt to read/update/delete tenant B's resource by ID (guessed or
   enumerated) → expect `404` (not `403`, to avoid confirming existence).
4. Attempt to pass tenant B's ID in a body field that references a related
   object (e.g. assigning to a user who is not a member of tenant A) →
   expect `422`/`400` at the service layer.
5. Confirm tenant A's own data is unaffected and still accessible.

CI fails the build if this suite fails; it is never skipped.
