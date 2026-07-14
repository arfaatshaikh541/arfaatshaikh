# Milestone 7 acceptance criteria

Covers Module 17 (Onboarding) and closes out the project with a final
full-system hardening pass across all seven milestones. See
`docs/architecture/erd-summary-m7.md`.

## Self-serve signup

- [ ] `POST /auth/signup` creates a tenant and its owner in one call,
      using the exact same `create_tenant_with_owner` path as
      platform-admin tenant creation - identical defaults (roles,
      pipeline stages, services, business hours, default workflow
      rule), verified by asserting on all of them, not just that the
      tenant row exists.
- [ ] The new owner is logged in immediately after signup (auth
      cookies set), without a separate login step.
- [ ] A verification email is sent to the owner; their account works
      before they click it (no verification gate blocks first login).
- [ ] A duplicate slug is rejected (409/422), not silently
      overwritten or given a different slug.
- [ ] More than 5 signups from the same IP within 60 minutes are
      rejected (429), verified with a real loop of requests in a test,
      not just checking the rate-limit code exists.
- [ ] Password and email validation match `TenantCreate`'s existing
      rules (min length, valid email) - no weaker path was introduced
      just because this endpoint is public.

## Onboarding wizard

- [ ] A freshly signed-up owner lands on the wizard, not directly on
      an empty dashboard.
- [ ] Every wizard step calls an endpoint that already existed before
      this milestone (services, settings, invitations) - the wizard
      introduces no new business logic, only sequencing.
- [ ] Completing the wizard sets `onboarding_completed_at` and the
      dashboard's "finish setup" banner disappears; skipping ahead to
      the dashboard without finishing still shows the banner.
- [ ] The wizard is skippable at every step past the first - a business
      that wants to explore on their own is never trapped in it.

## Final hardening pass (all 7 milestones)

- [ ] `ruff format --check`, `ruff check`, `mypy` clean on `apps/api`.
- [ ] `ruff format --check`, `ruff check` clean on `apps/worker`.
- [ ] Full pytest suite passes (every milestone's tests, cumulative).
- [ ] Alembic has a clean upgrade → downgrade → upgrade round-trip
      from scratch and `alembic check` reports no drift.
- [ ] Frontend: `tsc --noEmit`, `next lint`, `vitest run`, `next build`
      all clean.
- [ ] A production frontend build + live API, exercised with a
      Playwright browser session, walks the full lead-to-booking
      journey at least once: sign up → onboarding wizard → dashboard →
      create a lead → see it scored and auto-assigned → book an
      appointment → platform admin can see the new tenant.
- [ ] Every milestone's documented acceptance criteria file
      (`docs/product/milestone-{1..7}-acceptance-criteria.md`) reflects
      what was actually built - no stale checkboxes describing
      unimplemented behavior.
