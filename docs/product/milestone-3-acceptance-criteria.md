# Milestone 3 — Acceptance Criteria

Scope: scoring, assignment, tasks, notifications, email templates
(builds on Milestones 1-2).

## Lead Scoring

- [ ] Tenant admin (settings.manage) can create/edit/deactivate scoring
      rules (service match, estimated-value threshold, consent/complete
      contact info, source match, repeat-enquiry) with a point value.
- [ ] Score bands (hot/warm/standard/low priority) are tenant-configurable
      thresholds, not hardcoded.
- [ ] Creating or updating a lead recalculates its score and priority
      immediately; `GET` on the lead returns `score_reasons` explaining
      every point awarded.
- [ ] No rule type performs unexplained/black-box scoring - every active
      rule that matched is listed in the reasons.

## Assignment Engine

- [ ] Round-robin, service-based, and manual-fallback strategies are
      implemented and covered by tests; branch-based and priority-based
      reuse the same rule/condition mechanism.
- [ ] A newly created lead (manual or public form) is automatically
      assigned per the tenant's active assignment rules, evaluated in
      order; falls back to the configured fallback member if nothing
      matches.
- [ ] Every assignment decision - automatic or manual - is recorded in
      the activity timeline with enough metadata to explain why.

## Tasks & Follow-ups

- [ ] Tasks can be created manually (with due date, priority, assignee,
      optional related lead) and via automation.
- [ ] Default automation: moving a lead to a "qualified"-flagged stage
      creates a callback task for the assignee.
- [ ] `GET /tenants/me/tasks` supports filtering by assignee and status,
      and overdue is computed from `due_at` vs. now (not a stored,
      driftable flag).
- [ ] Completing a task records `completed_at`; task comments are
      supported.

## Communications (Templates, Notifications, Email)

- [ ] Tenant-specific `MessageTemplate` rows exist for acknowledgement,
      assignment alert, appointment confirmation/reminder, and follow-up,
      editable by settings.manage, with a preview endpoint that performs
      safe variable substitution only (no `eval`, verified by a test that
      a template containing Python-looking syntax is rendered literally,
      not executed).
- [ ] Lead creation sends an acknowledgement (email, using the tenant's
      template) and, when auto-assigned, an assignment alert to the
      assignee plus an in-app `Notification` row.
- [ ] `GET /tenants/me/notifications` and unread-count are scoped
      strictly to the requesting user within the current tenant.

## Tenant Isolation (extends Milestones 1-2 suite)

- [ ] Scoring rules, assignment rules, tasks, templates and notifications
      from tenant B are not readable, updatable, or referenceable from
      tenant A's context.

## Quality Gates

Same as Milestones 1-2: ruff lint/format, mypy, migration round-trip,
full pytest suite, frontend lint/typecheck/tests/build, all green.
