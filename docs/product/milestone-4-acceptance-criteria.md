# Milestone 4 acceptance criteria

Covers Module 11 (Booking / Appointments) and Module 12 (Workflow
Automation). See `docs/architecture/erd-summary-m4.md` for the schema.

## Booking / Appointments

- [ ] Staff can query available slots for a given staff member, date,
      and duration; the response excludes any time already covered by
      a non-cancelled appointment for that person.
- [ ] Availability respects the tenant's configured `business_hours`
      (per weekday, nullable = closed); a tenant with no configuration
      falls back to a documented default rather than showing zero slots.
- [ ] Booking an appointment for a slot that overlaps an existing
      non-cancelled appointment for the same assignee is rejected
      (409/422), even if the caller didn't check availability first -
      the server is the source of truth, not the client.
- [ ] Creating an appointment sends a best-effort confirmation email
      using the `appointment_confirmation` template and logs the
      attempt to `MessageLog`; a delivery failure never blocks the
      booking itself.
- [ ] Appointments can be rescheduled (new start/end, re-validated
      against availability), cancelled (requires a reason), marked
      completed, or marked no-show.
- [ ] A lead's appointments are visible on the lead detail view.
- [ ] All appointment queries and mutations are tenant-scoped and
      re-verify the lead/membership/branch/service referenced belong
      to the caller's tenant.
- [ ] A Celery beat task emails an `appointment_reminder` roughly 24h
      before each upcoming appointment, deduped so it never sends the
      same reminder twice.

## Workflow Automation

- [ ] Workflow rules are tenant-scoped, CRUD-able via API, and driven
      entirely by structured JSON (trigger type, conditions, actions)
      - there is no code-string field anywhere in the schema, and the
      execution path contains no `eval`/`exec`/dynamic-import call.
- [ ] Supported triggers: `lead_created`, `lead_stage_changed`,
      `lead_assigned`, `appointment_booked`.
- [ ] Supported actions: `create_task`, `send_email`, `add_tag`,
      `create_notification` - each maps to a fixed, reviewed function;
      an unrecognized trigger/action/operator is rejected at rule
      creation time (422), not silently ignored at execution time.
- [ ] A rule with an empty `conditions` list always matches its
      trigger; a non-empty list is ANDed.
- [ ] Every rule that actually fires (conditions matched) is recorded
      in `workflow_execution_logs` with the actions taken, viewable
      per-tenant.
- [ ] The Milestone 3 "qualified lead gets a callback task" behavior
      is now implemented as a seeded default workflow rule, not
      hardcoded Python, and produces the identical observable outcome
      (existing tests for it still pass).
- [ ] Every newly created tenant gets this default rule automatically;
      an existing tenant seeded before Milestone 4 is backfilled
      idempotently (same pattern as the M3 scoring-rule backfill).
- [ ] Deactivating a workflow rule stops it from firing without
      deleting its execution history.

## Quality gates (unchanged from prior milestones)

- [ ] `ruff format --check`, `ruff check`, `mypy` clean on `apps/api`.
- [ ] Alembic migration has a clean upgrade → downgrade → upgrade
      round-trip and `alembic check` reports no drift.
- [ ] Full pytest suite passes, including new coverage for
      availability computation, double-booking rejection, appointment
      lifecycle, and workflow condition/action matching.
- [ ] Frontend: `tsc --noEmit`, `next lint`, `vitest run`, `next build`
      all clean.
- [ ] Manual browser smoke test of the new screens against the seeded
      demo tenant.
