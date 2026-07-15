# Project status

**Current milestone:** Milestone 7 — Client Onboarding and Document Collection
**Status:** Complete, verified against a real PostgreSQL + Redis stack. Awaiting your review before starting Milestone 8.
**Last updated:** 2026-07-15

---

## What was built (Milestone 7)

This milestone combines the two modules the original architecture
bundled together: **Document Collection** (structured, reviewable file
requests, built first) and **Client Onboarding** (checklists that
compose on top of it and on the existing `crm` task infrastructure).

### Backend (`apps/api`)
- **New `documents` module**: `DocumentRequest` (a request for a specific document — title, description, lifecycle status `REQUESTED → UPLOADED → APPROVED/REJECTED`, review notes, an unguessable `public_token`) and `Document` (the uploaded file itself, kept as its own row so a rejected request can be re-uploaded without losing history; `uploaded_by` is null for a public/client upload).
- **New `onboarding` module**: `OnboardingTemplate` + `OnboardingTemplateStep` (ordered checklist steps, each either `TASK` or `DOCUMENT_REQUEST`) and `OnboardingCase` + `OnboardingCaseStep` (instantiated for a specific lead — each step spawns a *real* `Task` or `DocumentRequest` via a cross-module call, not a placeholder).
- **Auto-advancing checklist**: `crm.service.complete_task` and `documents.service.approve_document_request` each gained a small soft-fail hook back into `onboarding.service` to mark the corresponding case step complete; a case auto-completes once every step is done. Verified live: completing a task step left the case `in_progress` (the document step was still pending), and approving the document step then completed both the step and the case in the same request.
- **New `WorkflowActionType.START_ONBOARDING_CASE`** (config: `template_id`) — connects Milestone 5's automation engine to this milestone, e.g. "when a proposal is accepted, start onboarding." Verified live through a full trigger → sweep → case-created cycle.
- **Public, unauthenticated document upload surface** (`/public/documents/{token}`, `.../upload`) reusing the raw-token/no-RLS pattern proven in Milestones 4 and 6, but with **a deliberate divergence from the Milestone 6 proposal precedent**: the upload route *is* gated behind the `document_collection` module entitlement, because (unlike flipping a proposal's status) uploading a file consumes ongoing storage — a lapsed subscription should stop new uploads, not silently keep absorbing a resource nobody's paying for. Verified live (module disabled → view still works, upload returns 403).
- **A genuine malware-scan integration point**: uploads are checked against the EICAR test signature, the industry-standard string every real antivirus engine recognizes — a real, functioning safety net, not a stub, verified by both an automated test and a live upload of the actual EICAR string. It is explicitly **not** a substitute for a production AV engine (ClamAV/cloud API), which requires external infrastructure this sandbox doesn't have.
- **Storage usage enforcement**: every accepted upload increments the `document_storage_mb` usage metric (rounded up to whole megabytes) via the existing `check_and_increment_usage`; exceeding the plan's limit hard-fails the upload — unlike the soft-fail communications/workflow convention, a storage cap must actually block the write. Verified by automated test.
- **Three new `EmailTriggerEvent` values** (`document_requested`, `document_approved`, `document_rejected`) wired the same way Milestones 3, 4, and 6 wired theirs — no width migration needed, the column was already `VARCHAR(30)`.
- **The one real permission-catalog gap since Milestone 1**: unlike every prior milestone, the M1 catalog did not pre-provision a permission for *creating* an onboarding case or a document request (only `documents.view/upload/approve` existed, which cover viewing, uploading, and approving a file — not requesting one). Added `onboarding.view`, `onboarding.manage`, and `documents.manage` to the catalog and to every default role. `Manager` (like with `proposals.manage`) was granted `onboarding.manage`/`documents.manage` directly — these are treated as routine business actions, not admin-only configuration, the same reasoning that kept `workflows.manage` Administrator-only but gave Manager `proposals.manage`. As with every prior new permission code, this only applies to *newly created* tenants — existing tenants' seeded roles are not retroactively updated (the same long-standing, unremarked-on limitation since Milestone 4's `availability.manage`).
- **Two new Alembic migrations** (schema + RLS), exercised through a full upgrade → downgrade → re-upgrade cycle against both the dev and test databases. `document_requests` is deliberately excluded from RLS (same reasoning as `proposals` in Milestone 6); `documents` and all four `onboarding_*` tables are row-level-secured normally.
- **Extended the Engagement Operations seed template** with the three new email templates and a "Standard Client Onboarding" template (a document-request step + a task step) — applied to every newly created tenant.
- **20 new pytest tests** (129 total with Milestones 1–6's), covering: document request creation and notification, staff and public uploads, MIME/size validation, the EICAR malware check, the storage usage limit, approve/reject with notes, re-approval-after-rejection guards, the module-gated public upload (including the deliberate divergence from proposals), permission enforcement, cross-tenant isolation for both modules, template/case creation, step-to-resource spawning, cross-module auto-advancement (task completion and document approval each advancing their case step and triggering case auto-completion), manual completion for ad hoc steps (and its rejection for resource-backed steps), case cancellation, blank-case immediate completion, and the workflow-triggered case start.

### Frontend (`apps/web`)
- `/document-requests` — list (optionally filtered by `?leadId=`) and a create-request form.
- `/document-requests/[requestId]` — detail: staff upload, uploaded-file list with download links, the client-facing link, and approve/reject actions with notes.
- `/documents/upload/[token]` — the public, unauthenticated upload page.
- `/onboarding-templates` — template + step editor (task vs. document-request steps, with a due-in-days field for tasks).
- `/onboarding-cases` — list (optionally filtered by `?leadId=`) and a start-case form (lead + optional template picker).
- `/onboarding-cases/[caseId]` — checklist view linking each step through to its underlying task or document request, plus a cancel action.
- Lead detail page gained "Onboarding" and "Document requests" sections (mirroring the Milestone 4/6 pattern); sidebar nav updated.

### Tests & verification
- `ruff check app` — 0 errors. `pytest -q` — 129 passed. `eslint` — 0 errors. `tsc --noEmit` — 0 errors. `next build` — succeeds, 40 routes. `vitest run` — 4 passed.
- Both new Alembic migrations exercised through a full upgrade → downgrade → re-upgrade cycle against real Postgres, against both the dev (`cops`) and test (`cops_test`) databases.
- Manually smoke-tested over real HTTP against a freshly seeded demo tenant (upgraded to the Professional plan, which is where `client_onboarding`/`document_collection` first turn on) with the API server actually running: confirmed the seeded "Standard Client Onboarding" template via `GET`; started a case and confirmed a real `Task` and a real `DocumentRequest` were spawned; completed the task and confirmed its step advanced while the case correctly stayed `in_progress`; uploaded and approved the document and confirmed both the step and the case (with `completed_at`) flipped in the same request; uploaded the literal EICAR test string to a fresh request and confirmed a live `malware_detected` rejection; disabled the `document_collection` module for the tenant and confirmed the public upload route returned 403 while the public view route stayed 200; and configured a live workflow with a `start_onboarding_case` step, created a lead, ran the sweep, and confirmed a new case was created with both steps spawned — every major code path verified live, not just inside the test suite.

## Acceptance criteria — verified

| Criterion (from your Milestone 7 spec) | Verified how |
|---|---|
| Document requests with client upload | `DocumentRequest`/`Document` models, public token-based upload page, staff review (approve/reject) flow |
| Onboarding checklists tied to real work | `OnboardingTemplate`/`OnboardingCase` models; each step spawns a genuine `Task` or `DocumentRequest`, never a placeholder row |
| Progress tracks itself | `crm.service.complete_task` and `documents.service.approve_document_request` each advance the matching case step and, once every step is done, the case itself — verified live and by automated test |
| Building on scoring/booking/proposals/workflow primitives | `START_ONBOARDING_CASE` workflow action connects Milestone 5's engine directly to this milestone; document/onboarding email notifications reuse Milestone 3's communications infrastructure end-to-end |
| Secure document handling | MIME allow-list, size limit, storage-usage metering, and a genuine (if minimal) malware-scan integration point — all covered in `docs/security/README.md` |
| Entitlement enforcement (with one considered exception) | Both `client_onboarding` and `document_collection` modules checked on every authenticated route; the public upload route is *also* gated (unlike Milestone 6's proposal precedent) because uploads consume ongoing storage, not just a status flag |

## Known limitations

1. **No route to add an ad hoc step to an already-started case.** `OnboardingCaseStep.template_step_id` is nullable and `complete_step_manually` already supports completing a step with no underlying task/document request, but the only way to populate a case's steps today is from a template at start time. Adding "add a step to an in-progress case" is a natural, small follow-up.
2. **No document request or task reminder sweep.** Unlike appointment/task reminders (Milestone 3/4), a stale, un-uploaded document request or an overdue onboarding task doesn't currently trigger any automated nudge — left out to keep this milestone bounded; the existing `TASK_REMINDER` sweep already covers onboarding-spawned tasks specifically (they're ordinary `Task` rows), so only the document-request side is genuinely uncovered.
3. **Re-uploading after rejection replaces, rather than versions, the request's history.** Each upload is its own `Document` row (so nothing is destroyed), but there's no UI concept of "revision 1 vs revision 2" beyond the creation timestamp order.
4. **Malware scanning is a genuine EICAR-signature check, not a production-grade AV engine.** See `docs/security/README.md` for what this does and does not cover, and what wiring a real engine would require.
5. **New permission codes (`onboarding.view`, `onboarding.manage`, `documents.manage`) only apply to newly created tenants** — this is the same long-standing, previously-unremarked limitation that has applied to every new permission code since Milestone 4's `availability.manage`; existing tenants' seeded role-permission rows are never retroactively backfilled by a migration.
6. **Same environment caveats as Milestones 1–6 carry forward**: Docker Compose itself was not run end-to-end in this sandbox; all verification used the same application code run directly against local PostgreSQL 16 + Redis 7, including a real running `uvicorn` instance for the live HTTP smoke test. No real SMTP server is configured, so email delivery genuinely reports `FAILED` in `email_delivery_logs` even though the merge-field rendering and dispatch logic themselves are verified correct. No browser was available to visually confirm the new UI.

## Pending decisions

None new this milestone — Milestone 1's pending decisions (tenant-URL routing, production email/storage provider choice) remain open and don't block Milestone 8. The malware-scanning production integration (ClamAV vs. a cloud AV API) is a new open question worth deciding before a real launch, but doesn't block further feature milestones.

## Next action

Awaiting your review of Milestone 7. To proceed, reply exactly: **APPROVE MILESTONE 8**

Milestone 8 (per the approved architecture) is Client Portal and
Deadlines — an authenticated, self-service client login (distinct from
the per-request public token links this milestone used) and compliance/
service deadline tracking, the next stage after a client has been
onboarded.
