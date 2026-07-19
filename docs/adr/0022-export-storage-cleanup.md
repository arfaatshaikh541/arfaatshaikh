# ADR-0022: export storage cleanup

## Status
Accepted.

## Context
`Export.expires_at` has existed since Milestone 7, documented in its own
model comment as "informational only ... no cleanup job consumes it yet."
`export_tasks.py` always passed `expires_at=None` on completion, so no
export has ever actually expired, and nothing has ever deleted an export's
underlying object storage file. `docs/project-status.md` carried this
forward as a known limitation from Milestone 7 onward: "exported files
persist in the bucket indefinitely today... a `queue.maintenance`-style
periodic cleanup task (mirroring `expire_stale_reservations`) is natural
follow-up work."

No spec text in this session names Milestone 14's scope. It was chosen,
under the user's "Milestone 14" authorization, as the next highest-value
credential-free gap: it needs no live external service beyond object
storage, which has been fully testable since Milestone 7 via the real,
local `moto` S3-API server (no MinIO binary is installable in this
sandbox - see ADR-0015), and it closes a real, long-named limitation
rather than a cosmetic one.

## Decision

### A real, configurable retention period, not a fabricated one
The original architecture never specified how long an export should be
retained. Rather than invent a number without disclosing it as a choice,
a new `EXPORT_RETENTION_DAYS` setting (default 30) was added to
`app.core.config.Settings` - a real, changeable operational default, not
a hardcoded constant buried in the task. `worker.export_tasks.run_export`
now sets `expires_at = completed_at + timedelta(days=export_retention_
days)` on every successful completion, instead of `None`.

### A periodic Celery beat sweep, mirroring `expire_stale_reservations` exactly
`worker.export_cleanup_tasks.cleanup_expired_exports_task` follows the
same shape Milestone 1's reservation-expiry sweep already established: a
thin Celery task wrapping an async service function
(`exports.services.cleanup_expired_exports`) that runs under
`set_platform_bypass` (inherently cross-tenant - the whole point is
finding every tenant's expired exports in one sweep) and acts on each row
found individually. Registered on the existing `queue.maintenance` queue
(this is maintenance work, not request-serving throughput competing with
campaigns/enrichment/exports/CRM push), scheduled hourly via
`beat_schedule.py` - looser than the reservation sweep's 5-minute
interval, since storage cleanup has no urgency the way a stuck credit
reservation does.

### Idempotency: `storage_deleted_at`, and a deliberately idempotent delete
A new nullable `Export.storage_deleted_at` column, set exactly once per
export (never unset), is the sweep's own idempotency key -
`list_expired_uncleaned_exports` only returns rows where it is still
`NULL`. `app.core.storage.delete_object` (new) calls S3's `DeleteObject`,
which by its own protocol design succeeds silently against an
already-absent key rather than erroring - so a retry after a mid-sweep
crash (object deleted, row not yet marked; or the reverse, impossible
here since the row is only marked *after* the delete call succeeds) is
always safe to repeat. Verified directly: a dedicated test
(`test_cleanup_is_idempotent_when_the_object_is_already_gone`) deletes
nothing from S3 up front (simulating an object a prior, interrupted sweep
already removed) and confirms the sweep still completes and marks the row
correctly.

### The `Export` row is never deleted, and the object key is kept
Consistent with this codebase's standing "the entity's own row is the
audit trail" pattern (`CampaignEvent`, `LeadStatusHistory`, `Export`
itself), a cleaned-up export's row - and its `object_key` - are left in
place. The row remains a complete record of what was exported and when
its file was removed; only the underlying object is gone.

### The download path now checks for cleanup, not just completion
`exports.services.get_download_url` previously only checked `status ==
"completed"` before presigning a URL. It now also rejects a request once
`storage_deleted_at` is set, with a clear `ConflictError` ("has been
deleted after its retention period expired... request a new export"),
rather than silently presigning a URL to an object that no longer exists
and only failing once the browser actually tries to download it.

## Consequences
- New: `apps/api/alembic/versions/17cc4debecf6_*.py` (adds
  `exports.storage_deleted_at`), `apps/worker/worker/
  export_cleanup_tasks.py`, `apps/worker/tests/test_export_cleanup_
  tasks.py` (4 tests), `docs/adr/0022`.
- Modified: `app/core/config.py` (`export_retention_days`), `app/core/
  storage.py` (`delete_object`), `app/modules/exports/models.py`
  (`Export.storage_deleted_at`), `app/modules/exports/repositories.py`
  (`list_expired_uncleaned_exports`, `mark_storage_deleted`),
  `app/modules/exports/services.py` (`cleanup_expired_exports`,
  `get_download_url`'s new check), `apps/worker/worker/export_tasks.py`
  (real `expires_at` on completion), `apps/worker/worker/{celery_app,
  beat_schedule}.py` (task registration/routing/schedule),
  `apps/api/tests/test_exports.py` (+1 test).
- Closes `docs/project-status.md`'s "no storage-cleanup job exists for
  completed exports' underlying objects" known limitation in full.
- Same disclosed gap as the rest of object storage (ADR-0015): this has
  been exercised against `moto`'s real local S3-API server, not a real
  MinIO/S3 deployment - `DeleteObject`'s idempotent-on-missing-key
  behavior is standard S3 protocol semantics `moto` implements
  faithfully, but has not itself been confirmed against a real deployment.
- The retention period is a single global setting, not configurable per
  tenant or per export. Nothing in the captured requirements asked for
  per-tenant retention policies, so none was invented; a future billing
  tier wanting a longer or shorter retention window would need this
  revisited.
