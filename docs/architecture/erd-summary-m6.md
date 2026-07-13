# ERD addendum — Milestone 6

Covers the remaining half of Module 16 (Platform Super Admin):
subscription/plan management and platform-wide analytics. Builds on
`Subscription`/`SubscriptionPlan` (present since Milestone 1 but never
exposed through any endpoint) and the existing `platform.py` router /
`PlatformService` / `get_platform_admin` guard. No new tables.

## Subscription & plan management

`SubscriptionPlan` is a platform-owned catalog (not tenant data), so
plan CRUD lives entirely under `/platform/plans`, gated the same way
every other platform route is - `get_platform_admin`, which only checks
`User.is_platform_super_admin` and requires no tenant/membership
context (no `X-Tenant-Id` header).

New repositories: `SubscriptionPlanRepository` (list, get_by_code,
get_by_id, create, update) and `SubscriptionRepository`
(get_for_tenant, create, update). `PlatformService` grows:

- `list_plans()` / `create_plan(...)` / `update_plan(...)`
- `get_tenant_subscription(tenant_id)` - a tenant's current plan +
  status, or `None` if it somehow has no subscription row (shouldn't
  happen post-`TenantService.create_tenant_with_owner`, but the
  endpoint tolerates it rather than 500ing)
- `assign_subscription(actor, tenant_id, plan_id, status)` - changes a
  tenant's plan and/or subscription status in one call, audit-logged
  as `super_admin.subscription.changed` with `{"from_plan", "to_plan",
  "from_status", "to_status"}` metadata, following the exact pattern
  `set_tenant_status` already established.

Deactivating a plan (`is_active=false`) does not touch tenants already
on it - it only hides the plan from being assigned to *new* or
*changing* subscriptions. Existing subscriptions on a deactivated plan
keep working; this mirrors how `MessageTemplate.is_active` and
`ScoringRule.is_active` already behave elsewhere in the codebase
(deactivate, don't cascade-delete).

## Platform-wide analytics

`PlatformReportingService.get_overview()` - the platform-level sibling
of Milestone 5's tenant-scoped `ReportingService`, same "live SQL
aggregate, no cache, no pre-rollup" tradeoff, just unscoped by
`tenant_id` (`select(func.count()).select_from(Tenant)` instead of
`.where(Lead.tenant_id == tenant_id)`):

- tenant counts by status (active / suspended / archived)
- total leads and total appointments across every tenant
- subscription counts by status (trialing / active / past_due /
  canceled)
- subscription counts by plan code

Endpoint: `GET /platform/overview`, gated by `get_platform_admin`.

## Frontend: platform admin surface

No platform-admin UI existed before this milestone - only the backend
routes. A platform super admin is a `User.is_platform_super_admin`
flag, not a tenant membership, so this is a genuinely separate
frontend surface from the `(tenant)` route group: a new `(platform)`
route group with its own shell (no tenant switcher, no `X-Tenant-Id`
header on any request) gated by checking `useCurrentUser().data
?.is_platform_super_admin` client-side - the same defense-in-depth
pattern as everywhere else in this app: the frontend gate is a UX
convenience, the real enforcement is server-side `get_platform_admin`
on every request. Pages: overview dashboard, tenant list/detail
(status changes, subscription assignment), and plan management.
