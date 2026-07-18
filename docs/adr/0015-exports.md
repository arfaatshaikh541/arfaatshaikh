# ADR-0015: Exports design

## Status
Accepted.

## Context
Milestone 7 is "Exports": XLSX exports, CSV exports, export templates,
background export jobs, object storage, signed URLs, expiry, audit
records, workbook validation tests. Milestone 1 already reserved
S3-compatible object storage configuration (`core/config.py`'s
`s3_*` settings) but nothing had ever connected to it - this milestone
finally closes that gap.

## Decision

### The `Export` row is its own audit record and status tracker
`AuditLog` (Milestone 1) is used exclusively by `tenancy`/`platform_admin`
for membership and platform-staff actions - no campaign, lead, or
dedup action routes through it either. Rather than being the first
domain feature to force a dependency on a table nothing else in this
domain uses, `Export` follows the same pattern `CampaignEvent`/
`LeadStatusHistory` already established: the entity's own row (who
requested it, what it covered, when it started/finished, how many rows,
how many errors) *is* the audit trail, and `status` (`pending` ->
`processing` -> `completed`/`failed`) *is* the job-status tracker. No
second table was needed for either requirement.

### Selection is persisted as a replayable spec, re-resolved at execution time
`POST /exports` accepts either an explicit `lead_ids` list (a Lead
Workspace bulk selection) or a `filters` object shaped exactly like
`leads.repositories.LeadListFilters` (the API the list endpoint already
accepts) - "export everything matching my current view." `Export.
selection` stores this spec (`{"mode": "lead_ids", "lead_ids": [...]}`
or `{"mode": "filters", "filters": {...}}`), not a frozen list of lead
ids. The Celery task re-resolves it against current data when the job
actually runs (`exports.services.resolve_lead_ids`), the same way a
campaign's task queue re-reads current state rather than replaying a
stale plan - an export queued behind a backlog reflects any status/tag/
assignment changes made in the meantime, and a lead deleted or merged
away between request and execution is simply excluded (see "partial
completion" below) rather than causing a crash on a dangling id.

### Object storage: store the key, sign the URL fresh per download
`app.core.storage` wraps `boto3`'s S3 client (already a declared
dependency since Milestone 1, just unused). `Export.object_key` is
stored; `GET /exports/{id}/download` calls `generate_presigned_url`
fresh on every request rather than storing a presigned URL. A stored
presigned URL would eventually expire and become dead data requiring
its own refresh logic; regenerating is a local HMAC-signing operation
(no network round trip), cheap enough to do on every request, and
guarantees the link handed back is never already-expired. The signed
URL's own TTL is 15 minutes; `Export.expires_at` is a separate,
longer-lived marker for the underlying *object's* eventual storage
cleanup (informational only in this milestone - no cleanup job consumes
it yet, the same "declared for a fixed scheme, not yet consumed" pattern
`queue.crm_push` already used before this milestone wired up
`queue.export`).

Bucket creation is deliberately **not** the app's job - a real S3
deployment's bucket is provisioned by infrastructure/ops; auto-creating
it on first use would mask a real configuration error (wrong bucket
name, wrong credentials) behind a "helpful" side effect. If the
configured bucket doesn't exist, `upload_bytes` raises and the export is
recorded `failed` with a clear `error_message`.

### Streaming XLSX generation for "background export for large files"
`app.modules.exports.workbook` uses `openpyxl.Workbook(write_only=True)`,
which streams rows to the zip archive as they're appended instead of
holding every cell as a Python object in memory - the architecture's
explicit "background export for large files" requirement, satisfied
structurally rather than by a size-based branch to a different code
path. One real interop gap this surfaced: **write-only worksheets only
serialize `freeze_panes`/pane state if it's set before the first row is
appended** - setting it afterwards (natural in normal, non-streaming
openpyxl usage) is silently dropped on save with no error. Fixed by
moving every `ws.freeze_panes = "A2"` assignment to immediately after
`wb.create_sheet(...)`, confirmed by reopening the generated file and
asserting `freeze_panes` round-trips (see
`apps/worker/tests/test_export_tasks.py`).

### Formula-injection protection, in one function, applied to every string cell in both formats
Business data is scraped or human-entered - never validated as
"formula-safe." Both Excel/Sheets (via openpyxl, which auto-detects a
leading `=` and sets `data_type="f"`) and any spreadsheet application
that opens the CSV treat a cell beginning with `=`, `+`, `-`, or `@` (or
a leading tab/CR) as a formula to evaluate, not literal text.
`workbook.sanitize_cell_value` prefixes a leading apostrophe - the
standard Excel/OWASP-recommended defense (it forces text interpretation
and is never itself displayed) - applied to every string cell in both
`build_xlsx` and `build_csv`, so the two formats can never drift out of
sync on this. **A known, correct false-positive**: any phone number
stored in international format (`+971-4-...`) also starts with `+` and
gets the same apostrophe prefix. This is the accepted OWASP-documented
tradeoff, not a bug - the apostrophe is invisible when the cell is
rendered in Excel/Sheets (confirmed during live verification), only
visible in a raw text view of the CSV.

### Two columns are always empty, by design, not fabricated
The spec's exact 31-column schema includes **Opening Hours** and
**Verification Status**. Neither has a real data source anywhere in this
codebase: no connector (mock or Google Places) ever returns opening
hours, no crawler detector extracts them, and `LeadVerification` was
explicitly deferred out of Milestone 6's scope (see ADR-0014's
Consequences) and still doesn't exist. Both columns stay present, in the
spec's exact order, but every row leaves them empty - the same "never
fabricate a missing field" discipline `Business.email` (enrichment-only,
never set by discovery) already established. This is documented here
rather than silently possibly being mistaken for a bug during review.

### Campaign Summary, Scoring Rules, and Errors sheets are real, not placeholders
**Campaign Summary** groups the exported businesses by the campaign that
most recently (re)discovered them (`BusinessSourceRecord.campaign_id`,
batched via `businesses.repositories.
list_latest_campaign_ids_for_businesses`), showing each campaign's name,
status, result limit, and how many of *this export's* rows came from it
- real counts from the actual selection, not a static template.
**Scoring Rules** is the real, live `OPPORTUNITY_RECOMMENDATIONS` table
from `leads.scoring` (Milestone 5) plus the full `LEAD_STATUSES`
vocabulary - if that rule table ever changes, the sheet changes with it
automatically, since it's read directly from the module, not
transcribed. **Errors** lists every lead id that failed to resolve
during this export, each with a real, specific message - never a silent
gap. All four sheets get styled (bold white-on-slate) headers, frozen
header rows, and per-column widths tuned to their content.

### "Partial completion" for exports: per-row resilience within one task, not multi-task fan-out
The project-wide rule "every campaign must support retries/cancellation/
partial completion" is about campaigns specifically; an export has no
Milestone 2-style page fan-out to coordinate - one Celery task queries,
builds the file, and uploads it. The applicable shape of "partial
completion" here is that **one bad lead never fails the whole export**:
a requested lead id that doesn't resolve (deleted, or its business lost
a Milestone 5 dedup merge between request and execution) is recorded as
an `ExportError` row and skipped; the export still completes with an
accurate `row_count`/`error_count`, visible in both the API response and
the workbook's own Errors sheet. The job only reaches `failed` for a
genuine, total failure (can't reach object storage, can't query the
database at all), retried up to 3 times with exponential backoff -
exactly the same shape `worker.enrichment_tasks.run_business_enrichment`
already uses, reused rather than reinvented.

### Permissions: `leads.export` to create, `exports.view` to read
Both permission keys were already present in Milestone 1's catalog,
unused until now. `POST /exports` requires `leads.export` (the
lead-data-specific action, mirroring how `leads.score`/`leads.enrich`
gate lead-triggered actions); `GET /exports`, `GET /exports/{id}`, and
`GET /exports/{id}/download` require `exports.view` (the generic
"exports" resource-category permission, consistent with every other
`<resource>.view` in the catalog). No new permission rows were needed.

### Live verification: no MinIO binary is installable in this sandbox, `moto` stands in
This sandbox has no Docker daemon and no direct internet access to
download a MinIO binary (confirmed: `docker ps` fails to reach a daemon,
`curl` to `dl.min.io` gets a proxy 403). `moto`'s `ThreadedMotoServer` -
installable from PyPI - is a genuine local HTTP server implementing real
S3 API semantics; pointed at via `S3_ENDPOINT_URL`, `boto3` cannot tell
it apart from a real bucket, since every request is a real, unmocked
HTTP round trip. Used both for the automated test suite
(`apps/worker/tests/test_export_tasks.py`) and for a full manual
live-verification pass: register -> verify email -> create tenant ->
launch a mock-connector campaign -> score the discovered businesses ->
request an XLSX export of a bulk lead selection and a CSV export of
"everything matching current filters" -> watch the Celery worker process
both -> fetch the real presigned URL and reopen the downloaded XLSX to
confirm its structure - plus a Playwright pass through the actual
`/leads` bulk-selection-to-export flow and the `/exports` list/download
UI. This is disclosed the same way the Milestone 3 Google Places API key
gap and the Milestone 4 SSRF-crawler live-internet gap were: a real
MinIO server was never exercised, a functionally equivalent real S3
implementation was.

## Consequences
- New backend module `app.modules.exports` (`models.py`: `Export`,
  `ExportError`; `repositories.py`; `data.py` - the batched row-assembly
  layer; `workbook.py` - XLSX/CSV generation; `schemas.py`; `services.py`;
  `routes.py`), `app.core.storage` (the S3 client wrapper), and
  `worker.export_tasks.run_export` on its own `queue.export`.
- New batched repository functions added to existing modules where the
  row data actually lives, following the same "batch, don't N+1"
  discipline `leads.repositories.get_tags_for_leads` (Milestone 6)
  established: `leads.repositories.list_leads_for_export`/
  `list_all_lead_ids_matching_filters`/`get_latest_scores_for_leads`/
  `get_opportunities_for_leads`/`get_recommendations_for_leads`/
  `get_open_assignments_for_leads`/`get_latest_notes_for_leads`;
  `businesses.repositories.list_latest_source_records_for_businesses`/
  `list_latest_campaign_ids_for_businesses`;
  `enrichment.repositories.list_social_evidence_for_businesses`;
  `identity.repositories.list_users_by_ids`;
  `campaigns.repositories.list_campaigns_by_ids`.
- New frontend: `/exports` (list with live status/row/error/size columns,
  polling while any export is pending/processing, download button once
  completed) and the Leads page gained an export-format selector, an
  "Export selected" action in the bulk action bar, and an "Export all
  matching filters" action in the filter card - both wired to the same
  `POST /exports` endpoint with different `selection` shapes.
- `openpyxl` is now a real dependency of `apps/api` (previously absent
  from the whole monorepo); `moto[s3,server]` is a dev-only dependency of
  both `apps/api` and `apps/worker`, used only in tests and this
  milestone's live-verification pass - never imported by production code.
- Two columns (Opening Hours, Verification Status) are always empty in
  every export, by design - see "Two columns are always empty" above.
  If a future milestone adds `LeadVerification` or an opening-hours data
  source, populating these becomes a small, additive change, not a
  schema migration.
- Credit/usage charging was deliberately **not** added for exports - the
  captured build list has no mention of metering exports, and the
  seeded subscription-plan features (`max_team_members`,
  `max_concurrent_campaigns`) don't include one either. Inventing a
  credit cost here would be adding a requirement, not implementing one.
