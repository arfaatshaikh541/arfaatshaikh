# ADR-0025: duplicate-candidate review UI on the lead detail page

## Status
Accepted.

## Context
Deduplication (matching engine, `business_duplicate_candidates` and
`business_merge_history` tables, auto-merge above 0.85 confidence,
`pending` candidates below it) has been fully built and tested since
Milestone 5. The lead detail page has shown a read-only list of duplicate
candidates for the current lead's business since Milestone 6, with copy
that explicitly said "review from the Businesses API until a dedicated
review screen exists." The three review endpoints - `POST
/duplicate-candidates/{id}/confirm`, `POST /duplicate-candidates/{id}
/reject`, `POST /merges/{id}/undo` - have existed and been tested since
Milestone 5/6 but were never wired to any button. `docs/project-status.md`
carried this as known limitation #14 across ten further milestones.

No spec text in this session names Milestone 17's scope. This was chosen
as "the other frontend gap flagged at the end of Milestone 16": like
enrichment before it, a fully-built, fully-tested backend capability a
real user cannot reach without calling the raw API by hand.

## Decision

### Wire the three actions onto the existing card, and add a new Merge History card
The existing "Duplicate candidates" card on `/leads/[id]` already lists
candidates involving the lead's business. This milestone:
- Adds "Confirm merge" / "Reject" buttons to each `pending` candidate,
  using the page's existing `runAction`/`pending`/`actionError` pattern
  (the same one every other action on this page - status change, assign,
  notes, tags, push - already uses).
- Shows resolved status/confidence/reviewed-at for already-reviewed
  candidates instead of leaving them as an inert list item.
- Adds an entirely new "Merge history" card (nothing previously rendered
  merge history anywhere in the frontend) listing confirmed merges for the
  lead's business, each with an "Undo" button while `undone_at` is null.

A new card was added, rather than only wiring buttons onto the existing
list, because limitation #14 explicitly named "or undoing a merge" as part
of the gap, and `GET /businesses/{id}/merge-history` had no frontend
consumer at all.

### Business-name resolution via a batch `useQueries` lookup
Neither `DuplicateCandidateResponse` nor `MergeHistoryResponse` includes a
business name - only `business_id_a`/`business_id_b` and
`winner_business_id`/`loser_business_id`. Showing raw UUIDs in the list
would be unusable. The page now collects the set of "other business" IDs
referenced across the current lead's duplicate candidates and merge
history (excluding whichever ID equals the lead's own `business_id`),
dedupes it, and batch-fetches each via `useQueries` (`@tanstack/react-
query`) against the existing `GET /businesses/{id}` endpoint - the same
endpoint the page already calls once for the lead's own business. This
needed `useQueries` rather than `useQuery` because the ID list is a
dynamic array (rules-of-hooks forbids calling `useQuery` in a loop).
No new backend endpoint was added for this; batching N single-business
GETs was judged acceptable at the volume a lead detail page's duplicate
list realistically reaches (a handful of candidates/merges, not hundreds).

### No new invalidation logic needed for the reactive business_id case
Per Milestone 6's dedup-merge design, confirming a merge where the
*current* lead's business is the losing side reassigns the lead's
`business_id` to the winner. The page's `businessId` is already derived
reactively from `detailQuery.data?.business_id`, and every action's
existing `refresh()` call already invalidates `["lead", leadId]` - so this
reassignment cascades automatically through `businessQuery`,
`mergeHistoryQuery`, and the `useQueries` batch (all keyed on `businessId`)
with no new code. The one addition needed was invalidating
`["business", businessId, "merge-history"]` explicitly after confirm/undo,
since merge history is a separate query the lead-detail response doesn't
carry (mirroring how `handleEnrich` already invalidates enrichment/
evidence queries after triggering a crawl).

### Live-verified against the real running stack, including a real fuzzy-match duplicate
Per this project's standing rule for UI changes, this was driven through a
real `uvicorn`/Celery-worker/`next dev` stack in headless Chromium
(Playwright), not just `pnpm typecheck`/`pnpm build`. To produce a real
`pending` duplicate candidate (not fabricated data), a mock campaign
seeded one business, then a CSV import (`POST /imports` +
`POST /imports/{id}/start`) added a second business with a name ~90%
similar in the same city and a different phone - landing in the
`fuzzy_name` matching tier (max confidence 0.75, structurally below the
0.85 auto-merge threshold in `dedup.py`), which reliably stays `pending`
rather than auto-merging. CSV import's upload step writes to object
storage synchronously from the request handler, which needed a real S3-
compatible endpoint; this sandbox has no Docker daemon and cannot pull a
MinIO image, so a standalone `moto.server.ThreadedMotoServer` (the same
approach `apps/api/tests/conftest.py`'s `moto_s3` fixture already uses,
per its own comment referencing this exact constraint) was started as a
persistent process on port 9000, with `S3_ENDPOINT_URL` set for the
manually-started `uvicorn`/Celery processes. The script then clicked
"Confirm merge" on the real page, watched the candidate's status update
and the new Merge History card appear with the correct resolved winner/
loser names, clicked "Undo," and watched the entry flip to "undone" with
the Undo button disappearing - all screenshotted (before/after-confirm/
after-undo) and visually inspected.

### An environment detail worth recording: Celery task routing needs all five queues consumed
The worker in this project routes tasks across five named queues
(`queue.search`, `queue.enrichment`, `queue.export`, `queue.crm_push`,
`queue.maintenance` - see `worker/celery_app.py`'s `task_routes`), not the
Celery default queue. A worker started with no `-Q` flag (or `-Q default`)
silently accepts campaign/CSV-import tasks into its connection but never
executes them, leaving a campaign stuck in `queued` with the task neither
failing nor completing. This isn't a code bug - Milestone 15's ADR-0023
retry-loop fix already covers genuine stuck-task failure modes - it's
purely an artifact of manually starting the worker for live verification
without listing queues explicitly, recorded here so a future milestone's
verification pass doesn't lose time rediscovering it.

## Consequences
- New: nothing in `apps/api`/`apps/worker` - every endpoint this UI calls
  already existed, unchanged, since Milestone 5/6.
- Modified: `apps/web/lib/types.ts` (new `MergeHistoryEntry` type),
  `apps/web/app/(tenant)/leads/[id]/page.tsx` (business-name batch
  resolution, three new action handlers, updated Duplicate Candidates
  card, new Merge History card).
- Closes `docs/project-status.md` known limitation #14 in full - both the
  confirm/reject buttons and the previously-entirely-unbuilt undo UI.
- The business-name lookup is one `GET /businesses/{id}` request per
  distinct "other business" referenced on the page, not a single batch
  endpoint - fine at today's volume, worth revisiting only if a future
  milestone's dedup UI needs to show dozens of candidates/merges at once.
- Rejecting a candidate does not need a merge-history invalidation (reject
  never produces a merge-history row), so only confirm/undo trigger the
  extra invalidation - a small, deliberate asymmetry in the three handlers.
