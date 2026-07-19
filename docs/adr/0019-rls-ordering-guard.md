# ADR-0019: RLS ordering guard (runtime enforcement)

## Status
Accepted.

## Context
ADR-0001 and ADR-0007 each named two separate, independent gaps around Row
Level Security: *coverage* (does every tenant-owned table actually have a
real RLS policy?) and *ordering* (does every query against such a table run
on a session that already had `set_tenant_context`/`set_platform_bypass`
called on it?). ADR-0018 (Milestone 10) closed the coverage gap with a
schema-introspecting test. It explicitly left ordering open, because that
property - "did this specific call site remember to set context before its
first query" - cannot be verified by inspecting the schema. It is a
call-site discipline property, and until now this codebase relied on
manual discipline alone to get it right.

That risk is not hypothetical: two real ordering bugs have already hit this
codebase once each (`worker.campaign_tasks`, `worker.csv_import_tasks`),
both caught only because a human happened to notice the zero-row symptom
during manual testing. The core danger is that a missing context call does
not raise an error - Postgres's own RLS policy evaluates
`tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')`
to `NULL = NULL`, which is never `TRUE`, so the query simply returns zero
rows. That is indistinguishable from "this tenant genuinely has no data
yet" without deliberately going looking for the bug.

No spec text in this project names Milestone 11 directly (the same
situation ADR-0018 itself documented for Milestone 10). Closing this
explicitly-named, still-open gap from ADR-0007/ADR-0018 was chosen as the
milestone's scope over the only other outstanding candidate - live
verification against real Google Places/Stripe credentials - which isn't
actionable in this environment.

## Decision

### An always-on runtime guard, not a static lint rule
A source-level analyzer ("does this function call `set_tenant_context`
before its first query, on every code path") was considered and rejected.
It would require real control-flow analysis to avoid both false positives
(context set in a helper called earlier) and false negatives (context set
on one branch but not another), and even a perfect version would only
catch mistakes in code someone remembered to run the linter against.

Instead, `apps/api/app/core/db.py` registers two SQLAlchemy ORM event
listeners that make the mistake fail loudly the instant it is *exercised*,
in every environment (dev, test, prod) - there is no settings flag gating
this, since the entire point is that it cannot be silently skipped:

- **`do_orm_execute`**: fires for every `Session.execute()` /
  `AsyncSession.execute()` call, including raw `text()` statements, not
  just ORM-constructed `select()`/`insert()`. This was chosen over the
  lower-level `before_cursor_execute` specifically because it hands the
  listener the `Session` object directly (`orm_execute_state.session`);
  `before_cursor_execute` only has the `Connection`, which cannot be
  correlated back to session-level state without extra bookkeeping.
- **`after_transaction_end`**: used to clear the marker once the
  transaction that `SET LOCAL` was scoped to ends.

On each `do_orm_execute` call, the listener checks a marker in
`session.info` (SQLAlchemy's built-in per-session bookkeeping dict). If
absent, it checks whether the statement text mentions any RLS-protected
table; if so, it raises `RuntimeError` immediately, before the query ever
reaches Postgres. `set_tenant_context`/`set_platform_bypass` set
`session.info["rls_context_set"] = True` right after their `SET LOCAL`
call, which is the only way to clear the guard.

### Transaction-scoped marker clearing, savepoint-aware
`SET LOCAL` is scoped to the outermost Postgres transaction, not to a
SAVEPOINT. CSV import (Milestone 9) opens one outer transaction per task
and a `session.begin_nested()` SAVEPOINT per row for isolation. If the
marker were cleared whenever *any* transaction (including a nested one)
ended, every row after the first would be wrongly re-blocked. The
`after_transaction_end` listener therefore checks
`transaction.parent is None` and only clears the marker when the *outer*
transaction ends.

### Scoped to a dedicated `_AppSession` subclass, not the global `Session` class
The first implementation attached both listeners to SQLAlchemy's global
`Session` class. Running the full test suite against it produced 55
failures: this test suite's own service-level tests (`test_lead_workspace.py`,
`test_deduplication.py`, `test_lead_scoring.py`, `test_exports.py`,
`test_platform_admin.py`, `test_tenant_isolation.py`,
`test_campaign_engine.py`, and others) build ad-hoc sessions directly via
`async_sessionmaker(bind=create_async_engine(migrator_asyncpg_url()))`,
connecting as the `gridkeep_migrator` role, which has `BYPASSRLS`. Lacking
the Python-level marker is genuinely harmless on those sessions - guarding
them would be a pure false positive, not a real risk caught, since RLS
itself is bypassed at the database connection level regardless of any
in-process marker.

The fix: a `_AppSession(Session)` subclass exists solely to give the guard
a specific event target. `AsyncSessionLocal` - confirmed via
`grep -rln "async_sessionmaker("` to be the *only* session factory
anywhere in this codebase's production code, imported directly by both the
API and the worker - is built with `sync_session_class=_AppSession`. Both
listeners are registered on `_AppSession`, not the global `Session` class,
so the guard protects every real request/task session while leaving
unrelated test-only sessions untouched. This scoping behavior (a session
built from a class the listener is registered on triggers it; a session
built from a different, unrelated `async_sessionmaker` does not) was
verified against a standalone prototype script before being applied for
real.

### Two deliberate table exclusions, discovered empirically
After the scoping fix, three failures remained, all in
`test_platform_admin.py`, all tracing to queries against `role_permissions`
from `app/dependencies.py`'s `require_platform_permission` dependency. That
dependency checks a platform admin's own role permissions *before* any
tenant is selected, by design, and does not call `set_platform_bypass`.
Direct inspection of `pg_policies` confirmed `roles` and `role_permissions`
carry a deliberately more permissive policy than the other ~44 RLS-protected
tables:

```
tenant_id = current_tenant_id OR tenant_id IS NULL OR platform_bypass
```

The extra `tenant_id IS NULL` clause exists specifically so platform-role
catalog rows (`tenant_id = NULL`) are readable with zero context set. This
is legitimate, pre-existing, correct design - not a bug - confirmed by the
fact that `test_platform_admin.py`'s tests were already passing before this
milestone's changes.

`roles` and `role_permissions` were added to a `_GUARD_EXCLUDED_TABLES`
set, alongside `platform_audit_logs` (already excluded per ADR-0018's own
reasoning - its `tenant_id` is an informational nullable FK, not an
ownership column, and the table is never RLS-protected at all). This
trades away the guard's protection for the *tenant-scoped* half of `roles`
/`role_permissions` (a context-less query for a real tenant's own custom
role would still silently return zero rows) in exchange for not requiring
real SQL parsing to distinguish "which half of this table's policy is this
specific query hitting." Accepted as a narrow, documented residual risk on
exactly two tables, rather than building a SQL parser for one edge case.

### Word-boundary regex, not substring matching
The one remaining failure after both exclusions above was
`list_platform_audit_logs` (in `platform_admin/routes.py`) being wrongly
blocked, even though its query only ever touches `PlatformAuditLog`
(table name `platform_audit_logs`, an excluded table). The cause: a naive
`if table_name in statement_text` loop matched the *included* table name
`"audit_logs"` as a literal substring inside `"platform_audit_logs"` in the
generated SQL text - `_` is a `\w` character, so there is no word boundary
between `platform` and `audit_logs` in the compound name.

Fixed by replacing the substring loop with a single precompiled
`re.Pattern` using word-boundary alternation
(`\b(?:table1|table2|...)\b`), sorted longest-first. Verified directly via
`re.search` in Python that this correctly distinguishes `audit_logs` from
`platform_audit_logs`, and via a scan of all 47 RLS-tracked table names
that this substring collision was the *only* one present in the full set -
confirming the fix is complete, not just addressing this one instance.

### Schema-introspected table set, not a hardcoded list
`_rls_protected_table_names()` reuses the same principle
`test_rls_coverage.py` (ADR-0018) established: compute the guarded table
set once, from `Base.metadata.tables.values()` filtering for a `tenant_id`
column, rather than a hardcoded list that silently stops covering a future
tenant-owned table the moment someone forgets to update it.

### Dedicated regression tests
`apps/api/tests/test_rls_ordering_guard.py` (9 tests) exercises the real
`AsyncSessionLocal` against the real test database, proving each property
the prototype was checked against by hand is now permanent regression
coverage: blocks a context-less query; permits one after
`set_tenant_context`; permits one after `set_platform_bypass`; re-blocks
after the transaction that set context commits; does *not* re-block across
a nested SAVEPOINT rollback (the CSV-import per-row shape); does not
false-positive on `platform_audit_logs` or on `roles`/`role_permissions`
(regression tests for the two bugs found and fixed above); does not affect
a session built from a differently-configured `async_sessionmaker`
(scoping proof); and blocks a raw `text()` query exactly as it blocks an
ORM-constructed one.

## Consequences
- Modified: `apps/api/app/core/db.py` (the guard itself - `_AppSession`,
  `_GUARD_EXCLUDED_TABLES`, `_rls_protected_table_names`,
  `_rls_protected_table_pattern`, the two event listeners). No other
  production file changed - the worker package required zero code changes
  and its full 72-test suite passed unmodified on the first run once the
  guard was correctly scoped, positive evidence that this codebase's
  actual RLS-context call-site discipline (already hardened across
  Milestones 1, 2, and the two CSV-import/campaign-task fixes) was already
  sound.
- New: `apps/api/tests/test_rls_ordering_guard.py` (9 tests). Full API
  suite: 141 → 150 passing.
- `docs/project-status.md`'s "RLS ordering... remains a manual-discipline
  risk" known limitation (left open by ADR-0018/Milestone 10) is closed
  for the ~44 tables using the standard policy shape, and narrowed to a
  documented, much smaller residual risk: a context-less query against the
  *tenant-scoped* half of `roles`/`role_permissions` specifically would
  still silently return zero rows, since those two tables were excluded
  from the guard for the reasons above.
- This guard only fires on code paths that are actually exercised (by a
  real request, task, or test). It provides no protection against a code
  path that is written but never executed by anything - that residual gap
  is unavoidable for any runtime-only mechanism and would require the
  coverage-side static analysis this ADR explicitly rejected as
  disproportionate to the risk.
- The guard is scoped to `_AppSession`/`AsyncSessionLocal` only. Any future
  code that constructs its own `async_sessionmaker` outside of
  `app.core.db` (there is currently none in production code, confirmed via
  `grep -rln "async_sessionmaker("`) would silently bypass this protection
  - a risk worth re-checking if that ever changes.
