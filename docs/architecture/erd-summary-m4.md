# ERD addendum — Milestone 4

Covers Module 11 (Booking / Appointments) and Module 12 (Workflow
Automation). Builds on `erd-summary.md`, `erd-summary-m2.md`, and
`erd-summary-m3.md`.

## Module 11 — Booking / Appointments

### `appointments`

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| tenant_id | uuid fk tenants, cascade | indexed |
| lead_id | uuid fk leads, cascade | indexed |
| assigned_membership_id | uuid fk memberships, set null, nullable | who the appointment is with |
| branch_id | uuid fk branches, set null, nullable | |
| service_id | uuid fk services, set null, nullable | |
| starts_at | timestamptz | |
| ends_at | timestamptz | |
| status | text | `scheduled` / `confirmed` / `completed` / `cancelled` / `no_show` |
| location_type | text | `in_person` / `online_meeting` / `phone` |
| notes | text, nullable | |
| cancellation_reason | text, nullable | required when status becomes `cancelled` |
| created_by_user_id | uuid fk users, set null, nullable | |

Composite index on `(tenant_id, assigned_membership_id, starts_at)` -
the availability engine's core query is "does this staff member have
anything booked in `[starts_at, ends_at)` on this day".

### Availability

There is no separate `staff_availability` table for v1. Working hours
come from the existing `tenant_settings.business_hours` JSONB column
(added in Milestone 1, unused until now):

```json
{
  "mon": {"start": "09:00", "end": "18:00"},
  "tue": {"start": "09:00", "end": "18:00"},
  "wed": {"start": "09:00", "end": "18:00"},
  "thu": {"start": "09:00", "end": "18:00"},
  "fri": null,
  "sat": null,
  "sun": {"start": "09:00", "end": "18:00"}
}
```

A `null` value (or a missing day key) means closed. If a tenant hasn't
configured `business_hours` at all (empty dict, the model default),
the availability engine falls back to Sun-Thu 09:00-18:00 (the common
UAE working week) rather than reporting zero availability - see
`AvailabilityService.DEFAULT_BUSINESS_HOURS` in
`app/services/availability_service.py`. Per-staff availability
overrides (time off, different hours per person) are out of scope for
v1 and are a documented limitation - every active member of the tenant
is assumed to work the tenant's business hours.

Slot generation: for a given date and duration, the tenant's business
hours for that weekday are split into fixed-size slots (default 30
minutes, configurable per request), and any slot overlapping an
existing non-cancelled appointment for the requested
`assigned_membership_id` is excluded. This is a pure computation with
no persisted "slot" rows.

### Confirmation and reminders

Booking an appointment renders and sends the tenant's
`appointment_confirmation` message template (reserved since Milestone
3) to the lead's email, logged via the existing `MessageLog` table -
same best-effort, non-blocking pattern as the M3 acknowledgement/
assignment-alert emails.

A new Celery beat task, `send_appointment_reminders`, emails the
`appointment_reminder` template roughly 24 hours before `starts_at`
for `scheduled`/`confirmed` appointments, deduped against `MessageLog`
the same way `send_follow_up_reminders` is (see
`erd-summary-m3.md` and `apps/worker/worker/tasks/scheduled.py`).

## Module 12 — Workflow Automation

The Milestone 3 automation (moving a lead to the "qualified" stage
creates a callback task) was hardcoded Python in `LeadService`. This
milestone generalizes it into a tenant-configurable rule engine while
keeping the exact same hard constraint from the original spec: **no
`eval`/`exec`, no unsafe arbitrary-code execution**. Every trigger,
condition, and action is drawn from a fixed, enumerated set - there is
no user-supplied code or expression string anywhere in the execution
path, only structured JSON matched against a closed dispatch table
(the same pattern as the Milestone 3 scoring and assignment engines).

### `workflow_rules`

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| tenant_id | uuid fk tenants, cascade | indexed |
| name | text | |
| trigger_type | text | one of `WORKFLOW_TRIGGER_TYPES` |
| conditions | jsonb | list of `{field, operator, value}` objects, ANDed together |
| actions | jsonb | list of `{type, ...type-specific config}` objects, executed in order |
| sort_order | integer | |
| is_active | boolean | |

`WORKFLOW_TRIGGER_TYPES = ("lead_created", "lead_stage_changed", "lead_assigned", "appointment_booked")`

`WORKFLOW_ACTION_TYPES = ("create_task", "send_email", "add_tag", "create_notification")`

Condition fields recognized: `service_id`, `source`, `priority`,
`estimated_value`, `to_stage_slug` (only meaningful for
`lead_stage_changed`). Operators: `equals`, `not_equals`,
`at_least` (numeric). An empty `conditions` list always matches.

`change_stage` is deliberately not an action type in v1: an action
that changes a lead's stage would need to re-enter the
`lead_stage_changed` trigger evaluation, and guarding against
unbounded recursive automation chains is out of scope for this
milestone. Every other action is a terminal side effect (create a
task, send an email, tag the lead, notify a user) that cannot itself
re-trigger the same rule.

### `workflow_execution_logs`

Append-only audit trail, one row per rule that actually fired (rules
whose conditions didn't match are not logged - there was nothing to
audit).

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| tenant_id | uuid fk tenants, cascade | indexed |
| workflow_rule_id | uuid fk workflow_rules, cascade | |
| lead_id | uuid fk leads, set null, nullable | |
| trigger_type | text | |
| actions_taken | jsonb | list of `{type, result}` describing what actually ran |
| executed_at | timestamptz | |

### Trigger points

`WorkflowService.evaluate_triggers(tenant_id, trigger_type, lead, context)`
is called from:
- `LeadService.create()` - after scoring and auto-assignment, trigger `lead_created`
- `LeadService.change_stage()` - trigger `lead_stage_changed` with
  `context = {"to_stage_slug": ...}` for condition matching, replacing the
  Milestone 3 hardcoded qualified-stage block
- `LeadService.create()`'s auto-assignment block and `LeadService.assign()` -
  trigger `lead_assigned`
- `AppointmentService.create()` - trigger `appointment_booked`

Every newly created tenant (`TenantService.create_tenant_with_owner`)
is seeded with one default workflow rule reproducing the exact
Milestone 3 behavior: trigger `lead_stage_changed`, condition
`to_stage_slug equals qualified`, action `create_task` (title "Call
back qualified lead", priority high, due 24h out, assigned to the
lead's current assignee). This keeps existing tests and demo behavior
unchanged while moving the logic into the data-driven engine.
