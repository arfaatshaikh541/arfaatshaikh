# Milestone 2 — Acceptance Criteria

Scope: services, configurable fields, enquiry form, leads, pipeline,
activity timeline, search and filtering (builds on Milestone 1's
multi-tenancy/auth/RBAC foundation).

## Services & Configurable Fields

- [ ] Tenant admin (settings.manage) can create/edit/deactivate service
      categories and services.
- [ ] Tenant admin can build a qualification form: add/reorder/edit/
      deactivate questions of every required type (short text, long text,
      email, phone, number, currency, date, single-select, multi-select,
      checkbox, yes/no).
- [ ] Conditional questions (show question B only if question A has a
      given answer) are supported and enforced.
- [ ] Deactivating or editing a question does not delete or corrupt
      previously-submitted `lead_answers` (verified by a snapshot test).

## Public Enquiry Form

- [ ] `GET /public/{public_key}/form` returns active services + active
      qualification questions for that tenant, no auth required, no
      internal tenant `id` or secrets exposed.
- [ ] `POST /public/{public_key}/submit` creates a lead: validates
      required questions, records consent, captures UTM + referrer +
      source, rejects when the honeypot field is filled, is rate-limited
      per IP, and is idempotent given a repeated `Idempotency-Key` header.
- [ ] Duplicate detection flags (does not block) a submission that shares
      email or phone with a recent lead in the same tenant.
- [ ] A suspended/archived tenant's public form returns 404.

## Leads & Pipeline

- [ ] Manual lead creation, update, and soft business fields (priority,
      estimated value, preferred contact method, next follow-up) work via
      the tenant API, permission-gated by `leads.create`/`leads.update`.
- [ ] Pipeline stages are tenant-configurable rows (not hardcoded), seeded
      with the ten default stages, reorderable, with `is_won`/`is_lost`
      flags.
- [ ] Changing a lead's stage writes a `lead_stage_history` row and an
      activity-timeline entry; a `loss_reason` is required when moving to
      a `is_lost` stage.
- [ ] Table view supports search (name/email/phone/company/reference),
      filters (stage, service, source, priority, assignee, branch), and
      pagination.
- [ ] Kanban view groups leads by stage and supports drag-and-drop stage
      changes, calling the same authorized stage-change endpoint as the
      table view (no separate unauthenticated code path).
- [ ] Bulk stage-change and bulk-assign re-check permission for every
      item in the batch, not just once.
- [ ] Notes and tags can be added to a lead and appear in the timeline.

## Activity Timeline

- [ ] Every lead lifecycle action (created, updated, stage changed,
      assigned, note added, tag added) appears in
      `GET /tenants/me/leads/{id}/timeline`, ordered newest-first, scoped
      strictly to that tenant and that lead.

## Tenant Isolation (extends Milestone 1 suite)

- [ ] A lead, service, pipeline stage, or qualification question
      belonging to tenant B is not readable, updatable, or referenceable
      (e.g. assigning tenant B's stage/tag/branch to tenant A's lead) from
      tenant A's authenticated context - 404 on direct access, 422 on
      cross-tenant references in a request body.

## Quality Gates

Same as Milestone 1: ruff lint/format, mypy, migration round-trip, full
pytest suite, frontend lint/typecheck/test/build, all green before this
milestone is considered done.
