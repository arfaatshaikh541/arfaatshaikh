# Project status

**Current milestone:** Milestone 5 — Workflow Automation
**Status:** Complete, verified against a real PostgreSQL + Redis stack. Awaiting your review before starting Milestone 6.
**Last updated:** 2026-07-14

---

## What was built (Milestone 5)

### Backend (`apps/api`)
- **New `workflow_automation` module**: `Workflow` (trigger-condition-action automation: `trigger_event` — LEAD_CREATED/STAGE_CHANGED/SCORE_THRESHOLD_REACHED/TAG_ADDED/APPOINTMENT_BOOKED/APPOINTMENT_COMPLETED — plus `trigger_config` to narrow the trigger, e.g. `{"stage_name": "Qualified"}`, and `conditions`, a list of field/operator/value filters evaluated at trigger time, AND semantics), `WorkflowStep` (ordered actions with a `delay_minutes` wait before each one), `WorkflowRun` (one per triggered lead, tracks current step + next-due time), `WorkflowStepLog` (immutable per-step execution record — the same "explainable" audit trail as Milestone 3's `LeadScoreLog`).
- **Independent condition evaluator** (`app/modules/workflow_automation/conditions.py`) — deliberately not shared with Milestone 3's near-identical scoring-rule evaluator, to avoid touching already-shipped, tested code for a two-caller abstraction (documented "rule of three" rationale in the module docstring).
- **Execution model, consistent with Milestones 3 & 4**: every step — including `delay_minutes=0` ones — executes only via a Celery beat sweep (`process_due_steps_for_tenant`, 15-minute cadence, same as the reminder sweeps), never synchronously at trigger time. This keeps one execution code path instead of two, at the cost of "immediate" steps taking up to one sweep interval to actually run.
- **Four action types**: `SEND_EMAIL_TEMPLATE` (sends a specific template by id, via the new `communications.service.send_template_by_id` — reusing Milestone 3's `MANUAL` trigger event slot, which was reserved for exactly this), `CREATE_TASK`, `CHANGE_STAGE` (resolves a stage by name within the lead's own pipeline), `ADD_TAG`. A step that raises (e.g. a workflow referencing a deleted template) is caught, logged as `FAILED`, and the run still advances to the next step rather than getting permanently stuck.
- **Trigger wiring into every relevant existing service**: both lead-creation paths (LEAD_CREATED), `scoring.service.score_and_apply` (SCORE_THRESHOLD_REACHED), `crm.service.change_stage` (STAGE_CHANGED) and `add_tag_to_lead` (TAG_ADDED), and `booking.service.create_appointment`/`complete_appointment` (APPOINTMENT_BOOKED/APPOINTMENT_COMPLETED) — six trigger points across four modules, all soft-failing the same way Milestone 3/4 communications do: a disabled `workflow_automation` module or an exhausted `automation_runs` usage limit skips silently rather than blocking the action that fired it.
- **No new permissions needed.** `workflows.view`/`workflows.manage` and the `workflow_automation` module (with its `automation_runs` usage metric) were already provisioned in the Milestone 1 catalog — Manager correctly pre-scoped to view-only, Administrator to full manage — the fourth catalog entry in a row (after communications, booking) that the original commercial-model design anticipated correctly.
- **Extended the Engagement Operations seed template** with a 2-step "New Lead Welcome Sequence" workflow (tag immediately, create a follow-up task after 1 day) — demonstrating the delayed-step pattern out of the box for every newly created tenant.
- **Two new Alembic migrations** (schema + RLS), exercised through a full upgrade → downgrade → re-upgrade cycle.
- **11 new pytest tests** (97 total with Milestones 1–4's), covering: a full trigger→execution cycle for each action type, multi-step delay ordering (a step scheduled 60 minutes out does not fire on a sweep pass one minute after trigger, only on a later pass), condition filtering (only matching leads get a run), trigger-config narrowing (STAGE_CHANGED only fires for the configured stage name), a genuinely failing step (malformed template id) being logged FAILED while the run still completes, soft-skip on disabled module, soft-skip on exhausted usage limit, Manager-can-view-but-not-manage permission enforcement, and cross-tenant isolation.

### Frontend (`apps/web`)
- `/workflows` — list/create screen with a trigger-event picker whose narrowing field adapts to the selected trigger (stage name, minimum score, tag name, appointment type).
- `/workflows/[workflowId]` — step editor (delay + action type, with action-specific fields: tag name / task title+due-hours / stage picker / email template picker) and a run-history view with expandable per-run step logs.
- Sidebar nav gained Workflows, gated by `workflows.view` and the `workflow_automation` module entitlement.

### Worker (`apps/worker`)
- `app/tasks/workflow_automation.py` — `process_due_steps` Celery beat task, a thin per-tenant-loop wrapper around the directly-tested `process_due_steps_for_tenant`, added to the beat schedule at a 15-minute interval alongside every other sweep.

### Tests & verification
- `ruff check app` — 0 errors. `pytest -q` — 97 passed. `eslint` — 0 errors. `tsc --noEmit` — 0 errors. `next build` — succeeds, 29 routes. `vitest run` — 4 passed.
- Both new Alembic migrations exercised through a full upgrade → downgrade → re-upgrade cycle against real Postgres.
- Manually smoke-tested over real HTTP against a freshly seeded demo tenant with the API server actually running: confirmed the seeded "New Lead Welcome Sequence" workflow and its 2 steps via `GET`; created a brand-new lead over live HTTP and confirmed **no** tag was present yet (proving steps really do wait for the sweep rather than running synchronously); then invoked the sweep function directly (exactly as the Celery beat task does) and confirmed the tag appeared, the run correctly advanced to step 2 and stayed `RUNNING` (step 2's 24-hour delay hadn't elapsed), and the step log recorded `"Tag added: New Lead."` — the full trigger-to-execution cycle verified live, not just inside the test suite.

## Acceptance criteria — verified

| Criterion (from your Milestone 5 spec) | Verified how |
|---|---|
| Trigger-condition-action automation engine | `Workflow`/`WorkflowStep` models, 6 trigger events wired into 4 existing modules, 4 action types, condition evaluator with AND semantics |
| "When a lead enters stage X, wait N days, then send template Y or create a task" (the spec's own example) | Exactly reproduced: `STAGE_CHANGED` trigger + `trigger_config.stage_name` + a `delay_minutes`-gated `SEND_EMAIL_TEMPLATE` or `CREATE_TASK` step; verified by the multi-step-delay test |
| Building on scoring/assignment/communications/booking primitives | `SCORE_THRESHOLD_REACHED` reads the score Milestone 3 computes; `SEND_EMAIL_TEMPLATE` reuses Milestone 3's communications infrastructure end-to-end (soft-fail, delivery log); `APPOINTMENT_BOOKED`/`APPOINTMENT_COMPLETED` read from Milestone 4's booking module |
| Explainable / auditable execution | `WorkflowStepLog` records a human-readable result summary for every step attempt, exposed via the run-history UI and the `/runs/{id}/logs` endpoint |
| Entitlement/usage enforcement | `workflow_automation` module + `automation_runs` usage limit checked before every run is created, both soft-failing; automated tests for both |

## Known limitations

1. **Every step, including `delay_minutes=0` ones, waits for the next sweep tick (up to 15 minutes) rather than running instantly at trigger time.** This was a deliberate consistency choice (one execution code path, matching Milestones 3 & 4's reminder sweeps) rather than an oversight — see the module docstring in `app/modules/workflow_automation/service.py`. Revisit if "immediate" steps need to be closer to instant in practice.
2. **No deduplication of repeated trigger matches.** A lead can trigger the same workflow more than once if the triggering condition is met again — e.g. `SCORE_THRESHOLD_REACHED` re-firing on a manual rescore, or `STAGE_CHANGED` re-firing if a lead moves back into a stage it already passed through. This mirrors how a real automation platform behaves (the trigger is the source of truth, not a one-time flag) but tenants building workflows should be aware a lead could end up in multiple concurrent runs of the same workflow.
3. **The condition evaluator is independent from Milestone 3's scoring-rule evaluator**, not a shared utility, even though the two are structurally almost identical. This was a deliberate choice to avoid touching already-shipped, tested M3 code for a two-caller abstraction — documented in `conditions.py`'s module docstring as a "rule of three" candidate for extraction later.
4. **No webhook or external-integration action type** — reserved for the Integrations milestone per the original architecture's milestone breakdown, and deliberately excluded here to keep the action-execution surface free of any external-call/arbitrary-endpoint risk this milestone.
5. **The step editor's action-config UI stores raw field values without validating them against the tenant's actual data** (e.g. a `CHANGE_STAGE` step's stage name is picked from the current pipeline via a dropdown, but if that stage is later renamed or deleted, the step will silently skip at execution time rather than erroring at configuration time — this is intentional graceful-skip behaviour at runtime, but there's no UI warning today if a workflow's configuration becomes stale).
6. **Same environment caveats as Milestones 1–4 carry forward**: Docker Compose itself was not run end-to-end in this sandbox; all verification used the same application code run directly against local PostgreSQL 16 + Redis 7, including a real running `uvicorn` instance plus a direct sweep invocation for the live HTTP smoke test. No browser was available to visually confirm the new UI. Celery beat's scheduler itself was not run continuously in this sandbox; the task *logic* it calls was verified directly, both via the automated tests and the live manual sweep invocation.

## Pending decisions

None new this milestone — Milestone 1's pending decisions (tenant-URL routing, production email/storage provider choice) remain open and don't block Milestone 6.

## Next action

Awaiting your review of Milestone 5. To proceed, reply exactly: **APPROVE MILESTONE 6**

Milestone 6 (per the approved architecture) is Proposals: proposal
templates, line items, and client acceptance — the next stage in the
lead-to-client lifecycle after the scoring/assignment/booking/automation
primitives built in Milestones 3 through 5.
