# ERD addendum — Milestone 5

Covers Module 13 (Dashboards & Reporting) and the remaining piece of
Module 14 (Tenant Settings: `business_hours`). No new tables or
migration - reporting is entirely computed from existing data.

## Module 13 — Dashboards & Reporting

No new persisted tables. Every figure is a live SQL aggregate over
`leads`, `pipeline_stages`, `tasks`, `appointments`, and
`memberships`/`users`, scoped by `tenant_id` the same way every other
query in the codebase is - there is no separate reporting/analytics
data store or nightly rollup job for v1. This keeps the numbers always
current at the cost of doing the aggregation on every request; that's
an acceptable tradeoff at demo/small-tenant scale and is a documented
limitation (see acceptance criteria) rather than a hidden one.

`ReportingService.get_dashboard_report(tenant_id)` returns a single
composite object rather than one endpoint per widget, because a
dashboard page needs all of it at once and a single round trip is
simpler for both sides than seven small ones:

- **overview**: total lead count, hot-lead count, open task count,
  overdue task count, upcoming appointment count (next 7 days).
- **pipeline_funnel**: one row per pipeline stage (ordered by
  `sort_order`) with the current count of leads sitting in it, plus
  each stage's `is_won`/`is_lost` flags so the frontend can render a
  funnel without re-deriving stage semantics.
- **lead_sources**: lead count grouped by `Lead.source`.
- **score_distribution**: lead count grouped by `Lead.priority`
  (hot/warm/standard/low_priority) - the same bands the Module 7
  scoring engine assigns.
- **team_performance**: per active membership, count of leads
  currently assigned and count of leads currently sitting in a
  `is_won` stage.
- **task_stats**: open / overdue / completed-in-last-30-days counts,
  reusing the same "overdue is computed, not stored" definition from
  Module 9 (`due_at < now AND status = 'open'`).
- **appointment_stats**: count per `Appointment.status`.

Endpoint: `GET /tenants/me/reports/dashboard`, gated by the `reports.view`
permission (already part of the Milestone 1 permission catalog, granted
to owner/administrator/manager/viewer by default - reporting is a
read-only, managerial-visibility capability, not something every
front-line agent role gets by default).

## Module 14 — Tenant Settings: `business_hours`

`tenant_settings.business_hours` (JSONB) and the
`TenantSettingsUpdate.business_hours` PATCH field have existed since
Milestone 1 and were exercised programmatically by the Milestone 4
availability engine, but no UI ever rendered or edited them - editing
required a raw API call. This milestone adds the missing settings-page
form: one row per weekday with an open/closed toggle and start/end
time inputs, submitting the same `{"mon": {"start": "09:00", "end":
"18:00"}, "fri": null, ...}` shape `AvailabilityService` already
expects. No backend change was needed - the schema already supported
this field.
