# ADR-0020: shared Celery retry-exhaustion helper

## Status
Accepted.

## Context
ADR-0016 (Milestone 8) documented a real bug found across all five of this
worker's retrying Celery tasks: `Task.retry(exc=exc, ...)` re-raises the
*original* exception, not `MaxRetriesExceededError`, once a task's retry
budget is exhausted. A `try/except MaxRetriesExceededError` wrapped around
that call therefore never catches anything on real exhaustion - every one
of `campaign_tasks`, `enrichment_tasks`, `export_tasks`, `csv_import_tasks`,
and `integration_tasks` was silently dying uncaught on its final retry
attempt, with no error ever recorded, across three separate milestones
before the bug was found. The fix at the time was hand-written identically
in all five files: check `self.request.retries >= self.max_retries` *before*
calling `retry()`.

ADR-0016's own Consequences section named the gap this left open explicitly:
"nothing automated stops a *future* task written with the old
`try/except MaxRetriesExceededError` shape from reintroducing it. A lint
rule or a shared task-wrapper helper enforcing the
`if self.request.retries >= self.max_retries` pattern would close this
permanently." `docs/project-status.md`'s Unresolved risks list carried the
same item forward through Milestones 9-11.

No spec text in this session names Milestone 12's scope. The originally
preferred next step - a live-verification pass against real Google
Places/Stripe/webhook credentials - turned out to need something only the
user can supply (real API keys) that wasn't available when this milestone
started; this item was chosen instead as the highest-value gap that needs
no external credentials or network access, closing ADR-0016's own named
follow-up precisely.

## Decision

### `worker/retry.py`'s `retry_or_finalize` - the one sanctioned way to retry-then-finalize
A new module, not a lint rule: a custom ruff/AST plugin was considered (as
ADR-0016 itself suggested) and rejected as more machinery than the problem
needs - a shared function that *replaces* the duplicated pattern outright
makes the old broken shape impossible to reintroduce by construction,
rather than merely flagged after the fact by a separate tool a future
change could still bypass.

`retry_or_finalize(task, *, exc, finalize, countdown, task_name, task_id)`:
- If `task.request.retries >= task.max_retries`, logs one consistently-
  named `task_retries_exhausted` event and runs `finalize()` (a zero-
  argument callable returning a fresh coroutine - not an already-created
  coroutine object, so nothing is ever created-but-never-awaited on the
  retry path) via `worker.async_utils.run_db_task`, then returns normally.
  The domain record `finalize` writes (a campaign task, enrichment, export,
  CSV import, or integration delivery row marked `"failed"` with a real
  error) is the task's actual terminal outcome; Celery itself sees the task
  complete without raising.
- Otherwise, raises `task.retry(exc=exc, countdown=countdown)` (or
  `task.retry(countdown=countdown)` when `exc` is `None`, preserving
  `campaign_tasks`' `_SlotUnavailable` branch's original behavior of not
  passing an internal control-flow exception through to Celery).

`default_backoff(retries) -> float` extracts the
`min(60, 5 * (2**retries))` formula all five tasks already used, so it only
needs to change in one place if it ever does - not required by
`retry_or_finalize` itself, since a future task could reasonably want a
different backoff curve.

### All five tasks migrated to it
`campaign_tasks.py` (both its `_SlotUnavailable` and connector-error
branches), `enrichment_tasks.py`, `export_tasks.py`, `csv_import_tasks.py`,
and `integration_tasks.py` now call `retry_or_finalize` instead of their
own hand-written exhaustion check. Each task's own per-attempt `logger.warning`
call (present in four of the five files, informative on every retry, not
just the final one) was left in place, unchanged, immediately before the
`retry_or_finalize` call - `retry_or_finalize`'s own log line is a second,
consistently-named event specifically for the exhaustion transition, not a
replacement for each task's richer per-attempt context.

### A real Python footgun found and fixed while migrating: `except ... as exc` unbinds `exc` at block exit
Passing `lambda: some_finalize_fn(str(exc))` directly as `finalize` - the
first version of this change - failed ruff's `F821` check on every one of
the four call sites that build the lambda from an `except SomeError as exc:`
block. This is a genuine Python semantic, not a false positive: the name
bound by `except ... as exc` is implicitly `del`eted when the block exits,
specifically to avoid a reference cycle keeping the traceback (and
everything it references) alive. A lambda that closes over `exc` still
works correctly *in this specific case* (confirmed by direct testing) since
`retry_or_finalize` calls the lambda synchronously, before the `except`
block exits - but ruff correctly flags the pattern in general, since it is
unsafe for any closure that might outlive the block. Fixed by assigning
`error = exc` to a plain local variable immediately after entering each
`except` block, and closing over `error` instead - `worker/retry.py`'s own
docstring now documents this as a note to any future caller.

### A stale test-double target found and fixed: `test_integration_tasks.py`'s retry-exhaustion regression test
`test_celery_wrapper_finalizes_as_failed_once_retries_are_exhausted`
(ADR-0016's own regression test) monkeypatches `run_db_task` to a
synchronous `coro.send(None)` driver, since a real `asyncio.run(...)` call
is illegal nested inside pytest-asyncio's already-running loop. Before this
migration, the only call to `run_db_task` on the exhausted path lived in
`integration_tasks.py` itself, so patching `it.run_db_task` was sufficient.
After migration, that call moved into `worker.retry.retry_or_finalize`,
which holds its own separate `run_db_task` reference (`from
worker.async_utils import run_db_task`) - patching only `it.run_db_task`
left the *real* `run_db_task` running on the finalize path, which failed
with `RuntimeError: asyncio.run() cannot be called from a running event
loop`. Fixed by additionally monkeypatching `worker.retry.run_db_task` in
this one test. No other existing task test needed a change - this was the
only test in the suite that monkeypatched `run_db_task` at all, confirmed
via a grep across every test file.

### Tests
`apps/worker/tests/test_retry.py` (new, 5 tests) exercises
`retry_or_finalize` directly against a minimal fake Celery task double
(not the real `celery.Task`, which needs an app/broker to construct) -
retries-with-exc, retries-without-exc (the `_SlotUnavailable` shape),
finalizes-and-does-not-raise on exact exhaustion, finalizes defensively
when retries already exceed the budget (`>=`, not `==`), and
`default_backoff`'s exponential-capped-at-60 formula. Written as plain
(non-`async def`) functions specifically so the finalize-path tests can
drive `retry_or_finalize` without pytest-asyncio's session-scoped loop
already running - those two tests still monkeypatch
`worker.retry.run_db_task` with the same synchronous driver used in
`test_integration_tasks.py`, rather than relying on the real one, since a
plain sync test function calling the real `run_db_task` was found to
intermittently collide with a Redis client another test in the same
session had already bound to a different event loop (a variant of exactly
the cross-loop hazard `worker.async_utils`'s own docstring describes).

## Consequences
- New: `apps/worker/worker/retry.py`, `apps/worker/tests/test_retry.py`
  (5 tests).
- Modified: all five task files (`campaign_tasks.py`, `enrichment_tasks.py`,
  `export_tasks.py`, `csv_import_tasks.py`, `integration_tasks.py`) -
  each one's retry-exhaustion `if`/`else` block replaced by a call to
  `retry_or_finalize`; `apps/worker/tests/test_integration_tasks.py` -
  one test updated to monkeypatch the new call site.
- Closes ADR-0016's own named follow-up risk in full: a future Celery task
  added to this codebase now has no hand-written exhaustion check to get
  wrong, miscopy, or omit - `retry_or_finalize` is the only path.
- Does not change any task's externally-observable retry/backoff/failure
  behavior - this is a pure internal refactor verified by the full existing
  test suite (77/77 worker, unchanged in count except for the 5 new tests)
  passing unmodified except for the one monkeypatch-target fix.
- The `except ... as exc` unbind-on-exit footgun this migration surfaced is
  now a documented pattern (in `worker/retry.py`'s own docstring) for any
  future code building a deferred closure from inside an `except` block
  anywhere in this codebase, not just the five call sites fixed here.
