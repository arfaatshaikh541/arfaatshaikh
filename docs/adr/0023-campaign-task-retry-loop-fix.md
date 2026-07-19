# ADR-0023: connector fault injection and two real retry-loop bug fixes

## Status
Accepted.

## Context
`docs/project-status.md`'s known limitations and unresolved risks have
carried the same item since Milestone 3: "no automated test exercises a
real connector error path end-to-end through the worker's retry logic...
a fault-injecting test connector (or a flag on `MockConnector` to
simulate failures) is recommended as an early follow-up." Every existing
worker test either called a task's underlying `_run_..._async` coroutine
directly (bypassing Celery's retry machinery entirely, the same root-
cause shape ADR-0016 already diagnosed once for a different task) or
used connectors/crawl transports that never fail.

No spec text in this session names Milestone 15's scope. It was chosen,
under the user's "Milestone 15" authorization, as the next highest-value
credential-free gap - closing this specific, long-named testing hole.

## What building the test found: two real, previously-undetected bugs

Writing the test this ADR is about surfaced genuine production bugs, not
just a coverage gap - and investigating the first one led directly to
finding a second, identical bug in a different task.

### Bug 1: `worker.campaign_tasks`

`_run_campaign_task_async` claims a task via `jobs_repo.lock_task_for_
processing`, which transitions `CampaignTask.status` `pending -> running`
and commits immediately - deliberately idempotent in only one direction:
it refuses to reclaim a task that isn't currently `pending`, so a
duplicate Celery delivery for an already-running task is a safe no-op.
The connector's `search()` call happens *after* this transition, in a
separate step outside the transaction that claimed the task.

When `connector.search()` raised `ConnectorTransientError` or
`ConnectorRateLimitError`, the exception propagated uncaught, was caught
by `run_campaign_task`'s outer `except` clause, and (correctly) triggered
`retry_or_finalize` to schedule a genuine Celery retry - but **nothing
ever reset the task's status back to `pending` first**. The task was left
`running` from the already-failed attempt. When the real retried delivery
arrived (same `task_id`), `_run_campaign_task_async` ran from the top
again, saw `task.status != "pending"`, and hit its own duplicate-delivery
guard: `return` immediately, having done nothing.

### Bug 2: `worker.enrichment_tasks` (found by pattern-matching Bug 1)

After fixing Bug 1, the other four retrying tasks were checked by hand
for the same shape - a claimable-state field committed *before* the
task's own retryable failure point, with a `!= "pending"` duplicate-
delivery guard on the next delivery. `enrichment_tasks._run_business_
enrichment_async` has the identical structure: `enrichment.status =
"running"` is set and committed *before* `crawl_site(website)` (and
everything after it - detector execution, evidence persistence) runs. Any
exception there - the task's own docstring explicitly anticipates
"transient issues" being retried - propagates to the same `if
enrichment.status != "pending": return` guard on the next delivery,
exactly reproducing Bug 1's shape. A dedicated test written to check this
hypothesis (`test_transient_crawl_error_retries_then_succeeds`) failed
against the pre-fix code with the exact same symptom (`status == "running"`
where `"pending"` was expected) before the analogous fix was applied.

### The other three tasks were checked too, and are correctly designed already
- `export_tasks._run_export_async` sets `export.status = "processing"`
  but never commits it separately - the entire pipeline (selection
  resolution, row assembly, workbook generation, upload) runs inside one
  uncommitted transaction alongside the final success commit. An
  exception anywhere in that block leaves nothing durably changed, so the
  export row is still genuinely `pending` in the database on retry - safe
  by construction, not by an explicit reset.
- `csv_import_tasks._run_csv_import_async` commits `csv_import.status =
  "processing"` early, same as the two buggy tasks - but its own
  duplicate-delivery guard deliberately checks `status in ("completed",
  "failed")`, not `!= "pending"`, with an in-code comment explaining
  exactly why: "`processing` here must stay re-enterable... safe because
  `upsert_business_from_discovery` is idempotent per row." This was a
  correct design decision made in advance, not an accident.
- `integration_tasks._run_push_async` never transitions `delivery.status`
  away from `"pending"` until either final success or the task is
  finalized as failed - also explicitly commented: "marking it `failed`
  prematurely would make every subsequent retry silently no-op instead of
  actually retrying."

So two of five tasks had the bug (both fixed this milestone); the other
three were already correctly designed against it, two of them with
comments showing the design was deliberate. `campaign_tasks` and
`enrichment_tasks` simply never got that same deliberate treatment,
because - until this milestone - nothing had ever exercised their retry
paths for real to surface the gap.

### Practical impact
In both buggy tasks, the *user-visible* outcome was still eventually
correct: no data corruption, no campaign or enrichment stuck forever - the
retry budget simply burned down doing nothing until `max_retries` was
exhausted, at which point the existing finalize-as-failed path (Milestone
8/12, ADR-0016/ADR-0020) correctly marked the task/campaign/enrichment
failed with a real error. But the actual retry-then-recover mechanism -
the entire point of distinguishing transient from permanent failures -
never functioned. A single genuinely transient blip (one dropped
connection, one rate-limited request, one flaky DNS lookup) would fail
the whole task after several wasted, non-functional "retries" instead of
recovering on the very next real attempt as designed.

This was found the same way ADR-0016's Bug 2 was: by finally building the
test that exercises the real Celery-wrapped task through a real retry,
instead of only the underlying async function directly.

## Decision

### `FaultInjectingConnector` (`connector_sdk/fault_injecting.py`) - test-only, not registered
A small connector wrapping `MockConnector`: `outcomes[i]` scripts the
i-th call to `search()` as either `None` (delegate to a real
`MockConnector` call) or a specific exception to raise instead. Once
`outcomes` is exhausted, every further call delegates. Deliberately not
exported from `connector_sdk/__init__.py` and not added to
`connector_sdk.registry`'s production `_REGISTRY` dict - it must never be
selectable as a real campaign's `source_key`. Tests wire it in by
monkeypatching the caller's own `get_connector` reference
(`worker.campaign_tasks.get_connector`), never the production registry.

### The fix, applied identically in both tasks: reset to `pending` before a genuine retry
Both `run_campaign_task`'s and `run_business_enrichment`'s retryable
`except` branches now check `self.request.retries < self.max_retries`
(the same condition `retry_or_finalize` itself checks, intentionally
duplicated locally rather than extended into the shared helper - see
below) and, only when a genuine retry is about to happen, reset the
claimable-state field back to `pending` before `retry_or_finalize`
schedules the retry - undoing exactly what the earlier claim step did, so
the real retried delivery can reclaim and actually re-attempt the work.

Not done unconditionally (i.e., not before every `retry_or_finalize`
call regardless of outcome): if the retry budget is already exhausted,
the row is about to be finalized as `failed` directly - briefly setting
it back to `pending` first would open a real, if narrow, race window in a
multi-worker deployment where a *different* worker process could claim
and duplicate-process a row that's about to be marked failed anyway.

### Why not extend `retry_or_finalize` (Milestone 12, ADR-0020) itself
`retry_or_finalize` is deliberately generic across all five of this
worker's retrying tasks, with no domain-specific knowledge of any one
task's own status model. Adding a "reset before retry" hook to it would
either force every other task to opt out of behavior it doesn't need, or
make the shared helper's contract task-shape-aware in a way that
contradicts its own reason for existing. A local, explicit `if` check in
each of the two affected task files - the only two whose claimable-state
transition happens durably before their own retryable failure point - is
the more honest fix, and it now sits directly alongside the exact
`except` block it protects, impossible to miss when reading that code.

### Tests prove both bugs and both fixes, not just the happy path
`apps/worker/tests/test_campaign_task_retry_loop.py` (3 tests) and
`apps/worker/tests/test_enrichment_task_retry_loop.py` (1 test) drive the
real Celery-wrapped tasks (not the underlying async functions directly)
through `push_request`/direct invocation, the same pattern ADR-0016/
ADR-0020's own Celery-wrapper regression tests established. The campaign
suite also covers retries-exhausted finalizing cleanly (task/campaign
`failed`, reservation fully released - extends Celery-wrapper-exhaustion
coverage to `campaign_tasks`, never covered there before) and an auth
error failing immediately with no retry attempted at all.

### A second, pre-existing test-infrastructure gap found and fixed along the way
Driving the real Celery-wrapped task via `worker.async_utils.run_db_task`
(a fresh event loop per call) inside a test process that *also* runs
ordinary tests calling `_run_..._async` directly (sharing pytest-asyncio's
own session-scoped loop) turned out to have a latent cross-contamination
bug: the production `app.core.db.engine`/`app.core.rate_limit`'s cached
redis client accumulate connections bound to that shared session loop
from the ordinary-style tests, and the *first* real `run_db_task` call
anywhere in the whole test session then tries to gracefully close them
from its own unrelated fresh loop in its `finally: engine.dispose();
reset_redis_connection()` cleanup - the same cross-event-loop
`RuntimeError` `worker.async_utils`'s own docstring exists to prevent,
just one layer removed (a stale pooled connection rather than a stale
single client). This was invisible until now because
`test_campaign_task_retry_loop.py` happened to be the alphabetically-first
worker test file - sheer file-ordering luck, not a real guarantee - and
`test_enrichment_task_retry_loop.py` sorts after several ordinary-style
test files that populate the shared pool first, surfacing it immediately.
Fixed with a new `real_celery_task_isolation` fixture (`conftest.py`)
that disposes both while still running on the session loop that actually
owns whatever is currently pooled; both retry-loop test files request it,
and the campaign suite's own working-by-luck manual redis-reset was
removed in favor of it.

## Consequences
- New: `packages/connector-sdk/connector_sdk/fault_injecting.py`,
  `packages/connector-sdk/tests/test_fault_injecting.py` (4 tests),
  `apps/worker/tests/test_campaign_task_retry_loop.py` (3 tests),
  `apps/worker/tests/test_enrichment_task_retry_loop.py` (1 test),
  `real_celery_task_isolation` fixture in `apps/worker/tests/conftest.py`.
- Modified: `apps/worker/worker/campaign_tasks.py`,
  `apps/worker/worker/enrichment_tasks.py` (the two fixes).
- Closes the "no connector-error-path test coverage through the worker's
  own retry loop" gap named since Milestone 3, and - unexpectedly, since
  the gap was believed to be a testing hole, not a functional one - fixes
  two real bugs that had been silently degrading this worker's retry
  behavior since Milestone 2 (campaign) and Milestone 4 (enrichment). No
  campaign or enrichment run ever got stuck or corrupted data because of
  this; each affected task still eventually reached the correct terminal
  state after its retry budget was consumed - but the actual retry-then-
  recover behavior a transient failure is supposed to get never worked
  for these two tasks.
- `export_tasks`, `csv_import_tasks`, and `integration_tasks` were
  specifically checked and confirmed not to share this bug - two by
  deliberate, already-documented design, one by the accident of never
  committing an intermediate status change. Any *future* retrying task
  added to this worker should be checked against this same question
  before shipping: does a claimable-state field get committed before this
  task's own retryable failure point, and if so, is it reset before a
  genuine retry?
- The `FaultInjectingConnector` pattern (a real, deterministic, non-
  network test double implementing the actual `BaseConnector` contract,
  driven through the real production code path rather than a stub of that
  path) and the `real_celery_task_isolation` fixture are now available
  for any future test needing to exercise a Celery-wrapped task's retry
  handling anywhere else in this codebase.
