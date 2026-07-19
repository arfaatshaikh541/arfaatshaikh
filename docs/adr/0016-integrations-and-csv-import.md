# ADR-0016: CRM push integrations and CSV import

## Status
Accepted.

## Context
Milestone 8's scope was not spelled out verbatim anywhere the way
Milestones 3-7 were - it had to be inferred from breadcrumbs left in
earlier milestones: `QUEUE_CRM_PUSH` (declared since Milestone 2, unused,
commented "CRM delivery"), `integrations.view`/`integrations.manage`
(seeded since Milestone 1, unused), `credential_encryption_master_key`
(declared since Milestone 1, unused), a known-limitations note pointing
at "Milestone 8's CSV import / other connectors," and
`worker/crawler/safety.py`'s own module docstring already saying
`Business.website` values come from a connector today, "eventually CSV
import - see Milestone 8." Two independent feature tracks converge on
those breadcrumbs: pushing a lead **out** to an external system, and
bringing businesses **in** from a file instead of a connector search.

## Decision

### CRM push is a generic outbound webhook, not a named third-party connector
No real HubSpot/Salesforce/Pipedrive credentials exist to integrate
against, and this project's standing rule is never to build something
verifiable only by documentation-reasoning (the same reasoning behind
ADR-0010's real-but-mocked Google Places adapter and ADR-0012's SSRF
crawler). A generic webhook - tenant supplies a URL and a secret, the
platform POSTs a signed JSON payload - is fully testable end-to-end
against a real HTTP receiver, and it's what every actual CRM's own
"custom webhook" or Zapier-style integration expects on the receiving
end anyway.

### Credential encryption: Fernet, keyed from the already-declared master key
A webhook secret must be recovered in full to sign each outgoing
delivery, so it needs genuine encryption, not a one-way hash.
`app.core.security.encrypt_credential`/`decrypt_credential` use `Fernet`
(AES-128-CBC + HMAC-SHA256, from the already-a-dependency
`cryptography` package), with the key derived by SHA-256-stretching
Milestone 1's arbitrary-string `credential_encryption_master_key` config
value into a valid 32-byte Fernet key. `Integration.webhook_secret_encrypted`
is the only place a tenant's webhook secret is ever stored at rest; it is
never included in any API response (`IntegrationResponse` has no secret
field at all, not even a masked one).

### Webhook signing: HMAC-SHA256 over the exact bytes sent
`X-Gridkeep-Signature` is `HMAC-SHA256(webhook_secret, body_bytes)`,
where `body_bytes` is `json.dumps(payload, separators=(",", ":"))` -
the *exact* bytes the HTTP client sends, not a re-serialization of the
Python dict after some other step touched it. This is the same "sign
what you send" discipline Stripe/GitHub webhooks use, chosen specifically
to avoid a class of bug where the signer and the sender serialize the
same logical payload slightly differently (key order, whitespace) and
produce a signature the receiver can never actually verify.

### SSRF-safe webhook delivery reuses the enrichment crawler's existing defense
A tenant-admin-supplied webhook URL is exactly the same class of
lower-trust input `Business.website` already is for the Milestone 4
crawler (see ADR-0012) - both are strings a tenant controls that this
platform's own server ends up making an outbound request to.
`worker/crawler/safety.py` gained `safe_post_json`, sharing the module's
existing resolve-and-validate-before-connect check rather than
duplicating SSRF logic in a new module. `safe_post_json` deliberately
does **not** follow redirects (unlike `safe_get`, which does) - a
webhook target that redirects to a private address would otherwise
bypass the check entirely.

### CSV import deliberately does not implement `connector_sdk.BaseConnector`
`BaseConnector`'s shape (`estimate_cost`/`search` with a pagination
cursor) is built around a paginated remote API search - it doesn't fit
"parse a file that's already been uploaded." Rather than force an
ill-fitting interface, CSV import reuses the pipeline stage *after*
connector search already hands off to: `businesses.repositories.
upsert_business_from_discovery` -> `businesses.dedup.
process_new_business_for_duplicates`, the exact same functions a
campaign's discovered businesses flow through, called directly with
`campaign_id=None` (that parameter's type was tightened from `uuid.UUID`
to `uuid.UUID | None` to make this explicit rather than relying on
Python's runtime laxness about type hints).

### CSV import's credit model: reserve the row count, commit the actual imported count
Unlike a campaign (`estimate` -> `reserve` -> `commit`, where the
estimate is a connector's own cost prediction before any data exists),
CSV import already knows the exact row count at preview time - the file
is already uploaded and parsed. `start_import` reserves `row_count`
credits directly; the worker task commits `imported_count` as the actual
charge once the import finishes, so rows that failed to parse or
violated a database constraint cost nothing. Reuses `campaigns.create`/
`campaigns.view` rather than inventing a new permission - CSV import is
another way of getting businesses into the system, the same tier of
action as launching a campaign.

### Manual-trigger-only scope
CRM push happens only when a user clicks "Push to CRM" on a specific
lead, or bulk-pushes a selection - there is no automatic push on status
change or score threshold. The captured requirements never specified a
trigger condition for that, and inventing one (which status transition?
which score threshold? every tenant's integration fires on the same
rule?) would be adding a requirement, not implementing one. A future
milestone can add rule-based auto-push once there's an actual
specification for what should trigger it.

### Two systemic bugs found during live verification

**Bug 1 (integrations-specific): a too-narrow `except` clause left an
unanticipated exception type uncaught.** Live end-to-end verification
pushed a real lead to a real integration; the delivery stayed stuck at
`status="pending", attempt_count=0` through 20+ polls. `celery.log`
showed the real cause: `decrypt_credential` raised `RuntimeError`
because `CREDENTIAL_ENCRYPTION_MASTER_KEY` wasn't in the manually-started
worker process's environment (traced further to a real, separate
operational gap: `Settings.model_config`'s `env_file=".env"` resolves
relative to the process's current working directory, and the worker was
started from `apps/worker/`, which has no `.env` of its own - only
`apps/api/.env` does). `RuntimeError` was neither of the two exception
types the task's `except` clauses anticipated
(`UnsafeUrlError`, `(FetchError, httpx.HTTPError)`), so Celery logged
"raised unexpected" and the task died without ever recording an error.
Fixed by broadening the catch-all clause to `except Exception`, matching
the already-correct pattern `export_tasks.py`/`csv_import_tasks.py` used
from the start - any unanticipated exception (not just this one specific
missing-env-var case) must still retry-then-cleanly-fail.

**Bug 2 (found while writing a regression test for Bug 1, systemic
across five task files): `except MaxRetriesExceededError` never actually
catches anything once `retry(exc=exc, ...)` is used.** Investigating why
a synthetic regression test for Bug 1 didn't behave as expected led to
inspecting Celery's own `Task.retry()` source and confirming empirically
(a standalone repro script against the installed Celery version) that
when retries are exhausted **and** `exc=` was passed to `retry()`,
Celery's `raise_with_context(exc)` re-raises the *original* exception,
not `MaxRetriesExceededError`. Every task in this codebase that follows
the `try: raise self.retry(exc=exc, ...) except MaxRetriesExceededError:
finalize(...)` pattern - `campaign_tasks.run_campaign_task`,
`enrichment_tasks.run_business_enrichment`, `export_tasks.run_export`,
`csv_import_tasks.run_csv_import`, and this milestone's own
`integration_tasks.push_lead_to_integration` - had this pattern, meaning
**none of them ever actually ran their "finalize as failed with a clear
error" cleanup on real retry exhaustion**: the task just died uncaught on
its final attempt, the exact stuck-with-no-error failure mode Bug 1's
live verification surfaced, just deferred by however many retries.
`campaign_tasks.py`'s `_SlotUnavailable` branch had a related but
distinct exposure: since it doesn't pass `exc=`, exhausting those
retries raised an *uncaught* `MaxRetriesExceededError` directly (no
`try/except` wrapped that branch at all), also leaving the task dead
with no cleanup.

Fixed in all five files by replacing the try/except-based branch with an
explicit check *before* calling `retry()`: `if self.request.retries >=
self.max_retries: finalize(...) else: raise self.retry(...)`. This
doesn't depend on which exception type `retry()` happens to raise once
exhausted, so it can't have the same class of dead-code bug regardless
of whether `exc=` is passed. `campaign_tasks.py`'s `_SlotUnavailable`
branch now also finalizes the task as permanently failed (reusing the
existing `_finalize_task_permanently_failed` helper) instead of dying
uncaught if a concurrency slot never frees up after 8 retries.

A regression test (`test_celery_wrapper_finalizes_as_failed_once_
retries_are_exhausted` in `test_integration_tasks.py`) exercises the
real Celery-wrapped `push_lead_to_integration` task (not just
`_run_push_async` directly) via `Task.push_request`/`pop_request` to
simulate the final retry attempt, proving `_finalize_failed` is now
actually reached. It stubs `_run_push_async`/`_finalize_failed`/
`run_db_task` to trivial, non-awaiting coroutines rather than exercising
the real database through them - `worker.async_utils.run_db_task` calls
`asyncio.run(...)`, which cannot nest inside pytest-asyncio's
already-running event loop the way it can inside a real Celery prefork
worker's own process, and routing around that by moving the real
database work to a separate thread was tried and found to reintroduce a
different, unrelated problem: the module-scoped SQLAlchemy engine and
redis client, already bound to the pytest loop by other tests earlier in
the same session, raise "attached to a different loop" when touched from
a second thread's own fresh loop. What's under test is specifically the
task's own exception-handling control flow, which the existing
`test_finalize_failed_marks_terminal_status` test already covers against
a real database from the correct (non-Celery-wrapped) angle.

Live re-verification (after both fixes, with the worker restarted with
`CREDENTIAL_ENCRYPTION_MASTER_KEY` correctly exported into its
environment) pushed a fresh lead to the same real integration: the
delivery correctly progressed through all 5 attempts (1 initial + 4
retries, backoff 5s/10s/20s/40s) against `https://example.com/gridkeep-hook`,
then finalized as `status="failed"` with the real, honest error
(`Connection failed for https://example.com/gridkeep-hook: 403
Forbidden` - this sandbox's egress-restricting proxy blocking the
outbound call, the same restriction already confirmed against
httpbin.org/webhook.site during earlier milestones) instead of staying
stuck forever with no error recorded.

### Route ordering: `/push/bulk` before `/push/{lead_id}`
Same class of bug ADR-0014 already found once (`/leads/bulk/status` vs.
`/leads/{id}/status`): `POST /integrations/{id}/push/bulk` and
`POST /integrations/{id}/push/{lead_id}` are both two-segment paths
after `/{integration_id}`, and a parameterized segment matches any
string including the literal `"bulk"`. The bulk route is registered
first, caught proactively before any test ran rather than found by a
failing request the way ADR-0014's instance was.

### Two more recurrences of already-documented bug classes
`csv_import_tasks.py`'s status guard initially rejected any retry once
status left `"queued"` (i.e. once it became `"processing"`), silently
no-opping a legitimate retry after a mid-batch transient failure -
fixed by only treating `"completed"`/`"failed"` as terminal, since
per-row idempotency (`_source_native_id`, a stable hash of normalized
name/address/phone) makes a full retry of the row loop safe. And
`_run_csv_import_async`'s `await session.commit()` immediately after
`mark_processing` silently dropped the RLS tenant context for every
subsequent query in the row loop, because `set_tenant_context` uses
`SET LOCAL` (transaction-scoped, per ADR-0007) - fixed by re-applying it
right after that commit. Both are the same bug *classes* ADR-0007 and
earlier milestones' campaign worker code already hit once; documented
here rather than treated as novel.

## Consequences
- New backend modules: `app.modules.integrations` (`models.py`:
  `Integration`, `IntegrationDelivery`; `repositories.py`; `payload.py`
  - builds the real lead payload from live data, never fabricated;
  `schemas.py`; `services.py`; `routes.py`) and `app.modules.csv_import`
  (`models.py`: `CsvImport`, `CsvImportError`; `parsing.py`;
  `repositories.py`; `schemas.py`; `services.py`; `routes.py`), each with
  its own RLS-protected migration.
- `app.core.security` gained `encrypt_credential`/`decrypt_credential`/
  `sign_payload`. `app.core.storage` gained `download_bytes` (CSV
  import's preview endpoint uploads synchronously from the API request
  handler, and the worker task downloads the same object).
- New worker tasks: `worker.integration_tasks.push_lead_to_integration`
  (`queue.crm_push`, finally consumed after being declared unused since
  Milestone 2) and `worker.csv_import_tasks.run_csv_import`
  (`queue.search`, reused rather than given its own queue - CSV import
  is conceptually "another way businesses enter the system," the same
  category of work campaign search already queues there).
- `worker/crawler/safety.py` gained `safe_post_json`; its module
  docstring now describes both consumers (enrichment crawler,
  integration webhook delivery) sharing the one SSRF defense.
- The `except MaxRetriesExceededError` dead-code pattern was fixed in
  **five** files, not just this milestone's new one:
  `campaign_tasks.py`, `enrichment_tasks.py`, `export_tasks.py`,
  `csv_import_tasks.py`, `integration_tasks.py`. This was a
  pre-existing, silent bug in every one of the first four (present since
  Milestones 2, 4, and 7 respectively) - real retry-exhaustion cleanup
  never ran in any of them until this fix.
- New frontend pages: `/integrations` (create/enable/disable/delete a
  webhook, per-integration delivery history) and `/imports` (upload ->
  column-mapping preview -> start -> polling history with per-row
  errors). The lead detail page gained a "Push to CRM" card (only shown
  if at least one enabled integration exists).
- Permission catalog: `integrations.view` added to Campaign Manager and
  Sales Manager roles' defaults (previously only Owner/Administrator had
  any `integrations.*` permission) - using an existing integration to
  push a lead is a lower-privilege action than creating/managing one.
- **Known limitation, disclosed the same way as ADR-0010's Google Places
  API key gap and ADR-0012/ADR-0015's live-internet gaps**: no real
  external webhook delivery has been observed succeeding in this
  sandbox - only the SSRF-check-engaging path and the full retry/failure
  pipeline have been verified live, since this sandbox's egress-
  restricting proxy blocks outbound calls to any real endpoint tested
  (`example.com`, `httpbin.org`, `webhook.site`).
- CSV import's numeric fields (`rating`, `review_count`) are silently
  dropped (not fabricated as 0 or null-with-error) if a row's value
  fails to parse as a number - consistent with "never fabricate a
  missing field," but worth calling out since it means a malformed
  numeric cell doesn't show up in `CsvImportError` the way a missing
  `name` does.
