# Milestone 7 acceptance criteria

Covers Module 17 (Onboarding) and closes out the project with a final
full-system hardening pass across all seven milestones. See
`docs/architecture/erd-summary-m7.md`.

## Self-serve signup

- [x] `POST /auth/signup` creates a tenant and its owner in one call,
      using the exact same `create_tenant_with_owner` path as
      platform-admin tenant creation - identical defaults (roles,
      pipeline stages, services, business hours, default workflow
      rule), verified by asserting on all of them, not just that the
      tenant row exists. See
      `test_signup_defaults_match_platform_admin_created_tenant` in
      `apps/api/tests/test_signup.py`.
- [x] The new owner is logged in immediately after signup (auth
      cookies set), without a separate login step.
- [x] A verification email is sent to the owner; their account works
      before they click it (no verification gate blocks first login).
- [x] A duplicate slug is rejected (409), not silently overwritten or
      given a different slug.
- [x] More than 5 signups from the same IP within 60 minutes are
      rejected (429), verified with a real loop of requests in
      `test_signup_rate_limited_by_ip`, not just checking the
      rate-limit code exists.
- [x] Password and email validation match `TenantCreate`'s existing
      rules (min length, valid email) - the route accepts
      `TenantCreate` directly rather than a parallel schema, so there
      is no weaker path to drift out of sync.

## Onboarding wizard

- [x] A freshly signed-up owner lands on the wizard (`/onboarding`),
      not directly on an empty dashboard - `/auth/signup` redirects
      there on success.
- [x] Every wizard step but the last calls an endpoint that already
      existed before this milestone (services, settings, invitations).
      The one new endpoint, `POST /tenants/me/onboarding/complete`, is
      an idempotent completion flag, not new domain logic.
- [x] Completing the wizard sets `onboarding_completed_at` and the
      dashboard's "finish setup" banner disappears; a tenant that
      hasn't completed it still shows the banner.
- [x] The wizard is skippable at every step past the first (services,
      hours, team) - a business that wants to explore on their own is
      never trapped in it.

## Final hardening pass (all 7 milestones)

- [x] `ruff format --check`, `ruff check`, `mypy` clean on `apps/api`
      (124 source files).
- [x] `ruff format --check`, `ruff check` clean on `apps/worker`.
- [x] Full pytest suite passes: 144 tests, cumulative across all seven
      milestones.
- [x] Alembic has a clean upgrade → downgrade → upgrade round-trip
      from scratch and `alembic check` reports no drift, including
      after fixing pre-existing lint violations in the M3/M4 migration
      files (formatting-only; verified the SQL didn't change).
- [x] Frontend: `tsc --noEmit`, `next lint`, `vitest run` (21 tests),
      `next build` all clean.
- [x] A production frontend build + live API (`next build && next
      start`, per the established dev-server-flakiness workaround),
      exercised with a scripted Playwright browser session, walked the
      full journey twice: sign up → onboarding wizard → dashboard
      (banner gone) → create a lead → book an appointment via the
      slot-finder (confirmed booked, not just "no error") → sign out →
      log in as the platform super admin → see the new tenant listed
      under `/platform/tenants`. Lead scoring/auto-assignment itself
      is exercised by each milestone's own test suite (M3); this pass
      confirms a *self-signed-up* tenant exercises the same code path
      as a platform-admin-created one, which is the actual new risk
      this milestone introduces.
- [~] Every milestone's documented acceptance criteria file describes
      behavior that was actually built - true for all seven (144
      passing backend tests plus the frontend suite cover the claims).
      Not done: mechanically re-verifying and ticking every individual
      `- [ ]` checkbox across the milestone 1-6 docs (~90 line items).
      Those boxes were left unchecked at the time each milestone
      shipped even though the underlying feature was built and tested;
      going back to tick each one now without re-running a targeted
      check per line would be rubber-stamping, not verification, so
      I'm flagging it here instead as a known documentation gap rather
      than silently claiming it's done.
