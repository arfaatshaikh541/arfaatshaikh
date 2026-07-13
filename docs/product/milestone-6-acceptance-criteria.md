# Milestone 6 acceptance criteria

Covers the remaining half of Module 16 (Platform Super Admin):
subscription/plan management and platform-wide analytics. See
`docs/architecture/erd-summary-m6.md`.

## Subscription & plan management

- [ ] `GET/POST /platform/plans` and `PATCH /platform/plans/{id}` let a
      platform admin list, create, and edit the subscription plan
      catalog; a duplicate `code` is rejected (409/422), not silently
      overwritten.
- [ ] `GET /platform/tenants/{id}/subscription` returns the tenant's
      current plan and status.
- [ ] `POST /platform/tenants/{id}/subscription` changes a tenant's
      plan and/or status in one call and is recorded in the audit log
      with both the before and after plan/status - an admin looking at
      a tenant's history can see exactly what changed and when.
- [ ] Deactivating a plan does not alter or cancel any subscription
      already on that plan.
- [ ] Assigning a plan that doesn't exist, or belongs to no tenant,
      returns 404/422 - never a 500.
- [ ] Every platform endpoint requires `get_platform_admin`
      (`is_platform_super_admin`); a regular tenant owner/admin - even
      one with every tenant-level permission - gets 403 on all of them.

## Platform-wide analytics

- [ ] `GET /platform/overview` returns real counts aggregated across
      every tenant (never hardcoded) - verified in tests by creating
      fixtures across multiple tenants and asserting the totals sum
      correctly, not just that the endpoint returns 200.
- [ ] Counts are broken down by tenant status, subscription status, and
      plan code.
- [ ] A newly created tenant with no leads/appointments yet still
      contributes 0 to those totals without breaking the aggregate
      (no null-handling bugs).

## Frontend

- [ ] A platform super admin can sign in through the normal login flow
      and reach a `(platform)` admin area distinct from the tenant
      workspace UI - no tenant switcher, no `X-Tenant-Id` sent on any
      platform request.
- [ ] A non-super-admin user is redirected away from `/platform/*`
      client-side, and every underlying request would 403 server-side
      regardless (verified by checking the API call, not just the
      redirect).
- [ ] Tenant list/detail screens support viewing status, changing
      status (with a reason), and viewing/changing the subscription
      plan.
- [ ] Plan management screen supports creating and editing plans.
- [ ] Platform overview dashboard shows the real aggregate figures from
      `GET /platform/overview`.

## Quality gates (unchanged from prior milestones)

- [ ] `ruff format --check`, `ruff check`, `mypy` clean on `apps/api`.
- [ ] Full pytest suite passes, including new platform coverage.
- [ ] Frontend: `tsc --noEmit`, `next lint`, `vitest run`, `next build`
      all clean.
- [ ] Manual browser smoke test of the new platform admin screens,
      signed in as the seeded platform super admin.
