# Milestone 5 acceptance criteria

Covers Module 13 (Dashboards & Reporting) and the remaining Module 14
gap (tenant business hours UI). See `docs/architecture/erd-summary-m5.md`.

## Dashboards & Reporting

- [ ] `GET /tenants/me/reports/dashboard` returns real, tenant-scoped
      aggregate figures (never hardcoded/mock numbers) computed from
      the same tables the rest of the app writes to - counts must
      reflect leads/tasks/appointments created through the normal API,
      verified in tests by creating fixtures via the service layer and
      asserting the report reflects them.
  - [ ] `test_qualification.py`-style tenant isolation: a lead/task/
      appointment created for tenant B never appears in tenant A's
      report.
- [ ] The pipeline funnel is ordered by stage `sort_order` and includes
      every pipeline stage, even ones with zero leads currently in them
      (a stage with no leads reports 0, it isn't omitted).
- [ ] Task and appointment stats use the exact same "overdue"/status
      definitions as Modules 9 and 11 - no duplicate, possibly-drifting
      definition of "overdue."
- [ ] The endpoint requires the `reports.view` permission; a role
      without it (e.g. sales_agent) gets 403.
- [ ] Documented limitation: figures are computed live on every
      request, not cached or pre-aggregated - acceptable at the
      current scale, called out explicitly rather than silently
      degrading under load at a larger scale.

## Tenant Settings: business hours

- [ ] The settings page renders all seven weekdays with an open/closed
      toggle and start/end time inputs, pre-filled from the tenant's
      current `business_hours` (or shown as unset/default if the
      tenant hasn't configured any yet).
- [ ] Saving submits the exact `{"mon": {"start": "HH:MM", "end":
      "HH:MM"}, ...}` / `null`-for-closed shape `AvailabilityService`
      already parses - verified by booking an appointment through the
      UI afterward and confirming the available-slots query reflects
      the newly saved hours.
- [ ] No backend changes required; this is purely wiring an existing,
      already-tested API field into a form that was previously missing
      it.

## Quality gates (unchanged from prior milestones)

- [ ] `ruff format --check`, `ruff check`, `mypy` clean on `apps/api`.
- [ ] Full pytest suite passes, including new reporting coverage.
- [ ] Frontend: `tsc --noEmit`, `next lint`, `vitest run`, `next build`
      all clean.
- [ ] Manual browser smoke test of the dashboard and settings screens
      against the seeded demo tenant.
