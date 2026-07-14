# Project status

**Current milestone:** Milestone 2 — Lead Capture and CRM
**Status:** Complete, verified against a real PostgreSQL + Redis stack. Awaiting your review before starting Milestone 3.
**Last updated:** 2026-07-14

---

## What was built (Milestone 2)

### Backend (`apps/api`)
- **Leads module**: `Service`, `ServiceCategory`, `QualificationForm`, `QualificationQuestion` (11 types: short/long text, email, phone, number, currency, date, single/multi-select, checkbox, yes/no), `QualificationOption`, `QualificationAnswer` (immutable historical record), `CustomFieldDefinition`/`CustomFieldOption` (schema only — see known limitations), `LeadSource`, `Lead` (every field from the spec: reference number, contact fields, service/source/pipeline/stage, priority, score placeholder for Milestone 3, estimated value, assignment, preferred contact method, next-follow-up, consent status, UTM attribution, duplicate flags).
- **CRM module**: `Pipeline`/`PipelineStage` (the ten spec-default stages: New → Contacted → Qualified → Consultation Booked → Proposal Sent → Follow-Up → Won/Lost → Nurture → Archived), `LeadStageHistory`, `Tag`/`LeadTag`, `Note`, `Task`/`TaskComment`, `Activity` (unified append-only timeline), `Attachment`.
- **Public lead capture** (`POST /api/public/capture/{token}/enquiry`, no auth): resolved by an unguessable per-tenant capture token (`TenantCaptureToken`, never the tenant's slug/UUID); honeypot field; Redis-backed throttling (10/10min per tenant+IP); idempotency key; duplicate detection (email/phone match within 30 days — flags, never silently drops); UTM + consent capture; `lead_capture` module + `leads` usage-limit enforcement even on this unauthenticated path. Verified end-to-end over real HTTP, including the honeypot and duplicate-detection cases.
- **Manual lead creation** (authenticated, `leads.create` + `lead_capture` module + usage limit).
- **CRM pipeline operations**: stage transitions (with full history + activity timeline entries), notes, tags, tasks (+ comments, completion), attachments (upload/list/signed-download-URL), all gated by `crm` (or `tasks`, for task creation) module entitlement and the relevant `leads.*`/`tasks.*`/`documents.*` permission.
- **Object storage**: `StorageAdapter` interface actually implemented this milestone (`app/core/storage.py`) — `LocalDiskAdapter` (dev, Redis-backed single-use signed download tokens via `GET /api/files/{token}`) and `S3Adapter` (production, real S3 presigned URLs). MIME allow-list + 20MB size limit enforced before any write.
- **Professional Services template**: 9 default services, a 9-question default qualification form (exactly matching the spec's question list, including options for emirates/revenue/budget ranges), and the default pipeline — applied automatically to every newly created tenant (`app/db/seed/professional_services_template.py`), not just the demo tenant.
- **New permission**: `services.manage` (services/qualification-form configuration), added to Tenant Owner/Administrator/Manager by default; `documents.upload` added to Sales Agent (needed to attach files to their own leads — the existing catalog only granted it to Administrator/Support Agent, which was too restrictive for basic CRM attachments).
- **New endpoint**: `GET /api/tenant/settings/capture-link` — surfaces the tenant's public capture URL in the UI instead of requiring direct DB access.
- **Two new Alembic migrations** (schema + RLS) plus a third for the tenant capture token table (with data backfill for pre-existing tenants), all exercised upgrade/downgrade/re-upgrade against real Postgres.
- **14 new pytest tests** (54 total with Milestone 1's), covering: public capture happy path, unknown token, honeypot, idempotency, duplicate detection, throttling, module-disabled rejection; CRM stage transitions + history + timeline, notes/tags/tasks, cross-tenant isolation for leads/attachments, permission enforcement, usage-limit enforcement at the exact boundary, and the Professional Services template.

### Frontend (`apps/web`)
- Public enquiry page (`/enquire/[token]`) — service picker, dynamically-rendered qualification questions (all 11 types), honeypot field (visually hidden), consent checkbox, generic success response regardless of honeypot triggering.
- Tenant admin: Services screen (list + create), Qualification Forms screen (list + create) and per-form question editor (add question with type-specific options, required flag, reorder via up/down controls).
- Lead table (search, priority, stage columns) and a Kanban board (columns per pipeline stage, stage change via a per-card select — see known limitations re: drag-and-drop) sharing one query.
- Lead detail page: contact details, notes (add/list), tasks (add/complete), tags (add), attachments (upload via native file input, list), and the activity timeline — all on one page.
- Settings page now also shows the tenant's public capture link.
- Sidebar nav gained Leads/Services/Qualification Forms, gated by `crm`/`lead_capture` module entitlements and the relevant permissions, using the same `useEntitlements()` mechanism as Milestone 1.

### Tests & verification
- `ruff check app` — 0 errors. `pytest -q` — 54 passed. `eslint` — 0 errors. `tsc --noEmit` — 0 errors. `next build` — succeeds, 22 routes. `vitest run` — 4 passed.
- Manually smoke-tested over real HTTP against the seeded demo tenant: full public capture flow (services → form → submit → acknowledgement email → follow-up task auto-created), duplicate detection, honeypot, Kanban stage change → history → timeline, notes/tags, file upload → signed download URL redemption, and the new capture-link endpoint.

## Acceptance criteria — verified

| Criterion (from your Milestone 2 spec) | Verified how |
|---|---|
| Services, qualification forms, custom fields | Services + qualification forms fully built and editable; custom fields are schema-only this milestone (see known limitations) |
| Public enquiry form | `/enquire/[token]` page + `POST /public/capture/{token}/enquiry`, manually and automatically tested |
| Lead creation, duplicate detection | Automated tests + manual smoke test (heuristic email/phone match within 30 days, flags rather than drops) |
| Lead table | `/leads` table view — search, priority, stage columns |
| Kanban pipeline | `/leads?view=board` — columns per stage; stage change via dropdown rather than physical drag-and-drop (see known limitations) |
| Lead detail | `/leads/[leadId]` — details, notes, tasks, tags, attachments, timeline all in one page |
| Notes, tags, tasks, attachments | All built, permission- and module-gated, automated tests + manual verification including real file upload/download |
| Activity timeline | `Activity` model, written by service-layer code at each mutation point, not reconstructed after the fact; automated test asserts both a creation and a stage-change entry appear |
| Filters, search | Search by name/email/phone/company/reference number; stage/assigned-user/service filters on the list endpoint |
| Entitlement enforcement | `lead_capture`/`crm`/`tasks` module checks and `leads` usage-limit checks on every relevant route, including the public capture path; automated tests for module-disabled rejection and usage-limit boundary |

## Known limitations

1. **Kanban board uses a "move to" dropdown per card, not physical drag-and-drop.** No drag-and-drop library (e.g. `@dnd-kit`) was introduced this milestone — the dropdown achieves the same functional outcome (any stage → any stage in one action) without adding a new frontend dependency. Revisit if the product requirement is specifically the drag gesture, not just the outcome.
2. **Custom fields are schema-only.** `custom_field_definitions`/`custom_field_options` tables exist and `Lead.custom_fields` (JSONB) is ready to receive values, but there is no admin UI or API route to define custom fields yet — the qualification-question system covers the spec's actual default-questions requirement, so this was deprioritised rather than left silently broken.
3. **Reference numbers are non-sequential** (`{TENANT-PREFIX}-{8 hex chars}`, derived from the lead's own UUID) rather than a per-tenant incrementing counter, to avoid adding row-locking contention on lead creation. Revisit if the product requirement is specifically sequential numbering.
4. **Duplicate detection is a flag, not a merge or a block** — by design, per the spec's "duplicate lead detection" (distinct from "duplicate-submission protection," which idempotency keys handle). A human still has to look at the two records.
5. **Public capture module/permission split**: creating a lead (public or manual) requires the `lead_capture` module; everything else (pipeline, notes, tasks, tags, attachments, timeline) requires `crm` (or `tasks` specifically for task creation). Every seeded plan bundles `lead_capture` and `crm` together today, so this distinction isn't yet user-visible — it becomes relevant only if a future plan unbundles them.
6. **Same environment caveats as Milestone 1 carry forward**: Docker Compose itself was not run end-to-end in this sandbox (no Docker daemon available); all verification used the same application code run directly against local PostgreSQL 16 + Redis 7. No browser was available to visually confirm the new UI — lint/typecheck/build/tests pass and the underlying API calls were manually confirmed working, but no screenshot confirms rendering/interaction.
7. Two more RLS/service-layer bugs were found and fixed during this milestone's own testing (not present in the final code): the public capture token lookup initially couldn't read the (RLS-protected) `tenants` row before establishing tenant context (fixed the same way as Milestone 1's `accept_invitation` bug — `resolve_tenant_by_capture_token` now sets RLS context immediately after the token itself, which is unprotected, resolves); and manual lead creation was double-incrementing the `leads` usage counter (once via the route's `check_usage_limit` dependency, once inside the service function itself) — fixed by making the route-level dependency the single source of truth for that path, keeping the service-internal check only on the public-capture path which has no dependency chain to rely on.

## Pending decisions

None new this milestone — Milestone 1's pending decisions (tenant-URL routing, production email/storage provider choice) remain open and don't block Milestone 3.

## Next action

Awaiting your review of Milestone 2. To proceed, reply exactly: **APPROVE MILESTONE 3**

Milestone 3 (per the approved architecture) is Scoring, Assignment, and
Communications: deterministic scoring rules with explainable results,
assignment rules (round-robin/service-based/branch-based/priority-based),
tenant-configurable email templates with delivery logs and retries, task
reminders, and entitlement/usage enforcement throughout.
