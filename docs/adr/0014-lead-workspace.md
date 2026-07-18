# ADR-0014: Lead Workspace design

## Status
Accepted.

## Context
Milestone 6 is "Lead Workspace": lead list, lead detail, filtering,
sorting, pagination, assignments, notes, tags, statuses, bulk actions,
saved views, duplicate review, permission-aware interface - built on top
of the `Lead`/`LeadScore`/`LeadOpportunity`/`LeadRecommendation` entities
Milestone 5 already created. The architecture's "Lead-workspace features"
list additionally specifies server-side pagination, server-side sorting,
advanced filtering, bulk selection, source display, score breakdown, and
opportunity evidence - all read-side requirements the list/detail
endpoints below satisfy directly. Bulk *export* and `LeadVerification`
are both out of scope: export (file generation, object storage, signed
URLs) is Milestone 7's own named milestone, and `LeadVerification`
appears nowhere in Milestone 6's build list or its feature list.

## Decision

### Lead status has no transition state machine
Unlike `campaigns.state_machine`'s explicit legal-transition graph, the
architecture gives `Lead` an enumerated status list (`LEAD_STATUSES`,
already stored since Milestone 5) but no transition rules. Real sales
workflows are non-linear - a rep can move a lead back to "reviewed" from
"contacted," or straight from "new" to "do_not_contact" - so
`services.change_status` validates only that the target is a member of
`LEAD_STATUSES`, not that the transition is "legal" from the current
status. Every change is still recorded in `LeadStatusHistory`
(append-only, mirroring `CampaignEvent`'s shape) regardless of direction,
so the audit trail is complete even without transition enforcement.

### Assignment is a fast current-state column plus an audit trail
`Lead.assigned_to_user_id` is the current assignment (indexed, so the
list can filter/sort by it directly without a join); `LeadAssignment` is
an append-only history of every assignment event, with `unassigned_at`
marking when an entry stopped being current. Reassigning to a different
user closes the open entry (`unassigned_at = now`) and opens a new one;
reassigning to the *same* user is a no-op, not a new history entry - the
history records genuine changes of ownership, not repeated confirmations
of the status quo.

### Tags are plain strings, not a normalized vocabulary
`LeadTag` is `(tenant_id, lead_id, tag)` with a uniqueness constraint on
the triple - no separate `Tag` table with its own ID, color, or rename-
propagation. Nothing in the architecture's tag requirement asks for a
managed taxonomy (just "tags" as a build item and "advanced filtering"
by tag), and a normalized vocabulary table would be exactly the kind of
premature abstraction this project's own conventions warn against. Tags
are lowercased and trimmed on write (`services.add_tag`) so "Hot Lead"
and "hot lead" are the same tag, and adding an already-present tag is a
no-op rather than a duplicate-key error.

### Saved views are tenant-shared, deletable by creator or editor
`SavedLeadView` stores a name plus a `filters` JSONB blob shaped exactly
like the list endpoint's own query parameters - applying a saved view is
just replaying its stored filters client-side. Views are visible tenant-
wide (consistent with every other entity in this schema never being
per-user-private), but only the creator or someone holding the broader
`leads.edit` permission may delete one - enforced in
`services.delete_saved_view` by comparing `created_by_user_id`, with the
caller's own `leads.edit` membership passed in from `TenantContext.
permissions` (already resolved by `require_permission`, not re-derived).

### Offset-based pagination, not cursor-based
The lead list is the first genuinely paginated endpoint in this
codebase - every prior list endpoint (campaigns, businesses) returns
everything, since none has approached a scale where that matters. Plain
`page`/`page_size` offset pagination (capped at 100 per page) is simplest
and sufficient at the scale a single tenant's lead list realistically
reaches; a cursor-based approach would add real complexity (opaque
cursor encoding, keyset-consistency handling across concurrent writes)
this milestone's actual requirement doesn't call for.

### The list query: one query for the page, one for tags, a window function for "latest score"
`repositories.list_leads` joins `Lead` to `Business` (filtering
`Business.merged_into_id IS NULL` - see below) and left-joins a `ROW_
NUMBER() OVER (PARTITION BY lead_id ORDER BY calculated_at DESC)`
subquery to get each lead's most recent `LeadScore.total_score` for
sorting/filtering by score, without needing a denormalized "current
score" column on `Lead` that could drift out of sync with `LeadScore`'s
own append-only history. Tag filtering and opportunity-type filtering
both use `Lead.id.in_(SELECT ...)` rather than a `JOIN`, specifically to
avoid duplicate result rows a 1:many join would produce before pagination
LIMIT/OFFSET is applied. Tags for display (as opposed to filtering) are
fetched in one batched second query scoped to just the current page's
lead IDs (`get_tags_for_leads`), not per-row, and not via a join that
would again risk row duplication.

### A real gap found and fixed: `dedup.merge_businesses` never touched `Lead`
Milestone 5 built `Business` merging without any awareness of `Lead`,
since `Lead` didn't exist for most of that milestone's own
implementation. Building the lead list on top of merge-aware `Business`
data surfaced the gap directly: a `Lead` attached to a business that
later lost a merge would be orphaned - still pointing at a real, valid,
but now-non-canonical `Business` row. Fixed by extending
`merge_businesses`/`undo_merge`: if only the losing business has a
`Lead`, it moves onto the winner (`Lead.business_id = winner.id`) -
since every child of a `Lead` (`LeadScore`, `LeadOpportunity`,
`LeadRecommendation`, `LeadNote`, `LeadTag`, `LeadStatusHistory`,
`LeadAssignment`) keys off `lead_id`, not `business_id`, moving the one
`Lead` row carries its entire history along for free, and the move is
recorded in `BusinessMergeHistory.moved_records["lead"]` for the same
precise, ID-scoped undo every other moved-record type already gets. If
*both* businesses already have independent `Lead` rows (each
discovered, scored, noted, and tagged before ever being recognized as
duplicates), this deliberately does **not** attempt to reconcile two
sets of human-authored history into one merged `Lead` - the loser's
`Lead` is left exactly as it was, simply excluded from `list_leads`
(which already filters `Business.merged_into_id IS NULL`) rather than
silently deleted or blended. Reconciling two independently-worked leads
is a real feature with real product decisions behind it (whose notes
win? whose tags?), not a merge side effect to improvise.

### A real routing bug found and fixed: bulk routes shadowed by `/{lead_id}`
`POST /leads/bulk/status` and `POST /leads/{lead_id}/status` are both
two-segment POST paths under `/leads`. Starlette matches routes in
registration order, and a parameterized segment (`{lead_id}`) matches
any string, including the literal `"bulk"`. Registering the `/{lead_id}`
routes first would mean a request to `/leads/bulk/status` incorrectly
tries to parse `"bulk"` as a UUID and returns 422, never reaching the
bulk handler. Fixed by registering every literal-segment route
(`/bulk/status`, `/bulk/assign`, `/bulk/tags`, `/meta/statuses`) before
any `/{lead_id}/...` route, with a comment in `routes.py` explaining why
the ordering matters so a future addition doesn't reintroduce it.
Verified with an HTTP-level test (`test_lead_workspace_api.py`) that
specifically checks a bulk request against a random, non-existent
lead-id-shaped payload reaches the bulk handler (404 "not found") rather
than being swallowed by UUID-parse validation (422) - the only way to
distinguish "routed correctly but the lead doesn't exist" from "routed
to the wrong handler entirely."

### A real prerequisite gap found and fixed: no way to list tenant members
Assigning a lead needs a picker of "who can this be assigned to," which
needs a list of the tenant's active members - and no such endpoint
existed (Milestone 1's team page only ever needed to list *invitations*,
never active members with their role). Added `GET /tenants/members`
(`tenancy.repositories.list_active_members_for_tenant`, permission
`users.view`, already in the Milestone 1 catalog) - the same "small,
transparent gap-fill surfaced by the next milestone's real requirement"
pattern as Milestone 4's Business persistence layer and Milestone 6's
own `dedup.merge_businesses` fix above.

### No new permissions beyond `leads.score` and `leads.enrich` (already added in Milestones 4-5)
The Milestone 1 permission catalog already anticipated `leads.assign`,
`leads.change_status`, `leads.export`, and `leads.delete` as coarse-
grained permissions years before this milestone needed them - assignment
uses `leads.assign`, status changes use `leads.change_status`, notes/
tags/duplicate-review/merge-undo all reuse the existing `leads.edit`
(the same reasoning ADR-0013 already applied to Milestone 5's dedup
review actions), and saved views are gated by `leads.view` (create/list)
with ownership-or-`leads.edit` for delete. No new permission rows were
needed for this entire milestone.

## Consequences
- New backend: `tenancy.repositories.list_active_members_for_tenant` +
  `GET /tenants/members`; `leads.models` gains `Lead.assigned_to_user_id`
  and four new tables (`LeadAssignment`, `LeadStatusHistory`, `LeadNote`,
  `LeadTag`) plus `SavedLeadView`; `leads.repositories.list_leads` (the
  paginated/sorted/filtered query) and a full set of status/assignment/
  note/tag/bulk/saved-view repository and service functions;
  `businesses.dedup.merge_businesses`/`undo_merge` extended for `Lead`
  reassignment.
- New frontend: `/leads` (filterable/sortable/paginated list, bulk
  selection and bulk status/tag actions, saved views) and `/leads/[id]`
  (business info, status + history, assignment + history, score
  breakdown, opportunities/recommendations, duplicate candidates, tags,
  notes) - both genuinely functional and verified live against the real
  running stack (registration → campaign launch → worker-driven
  discovery → scoring → the Lead Workspace UI itself, including status
  changes, assignment, notes, and tags actually persisting and
  redisplaying correctly), not just unit-tested in isolation.
- Bulk *export* is not implemented - "bulk selection" exists in the UI
  (the checkbox/select-all mechanism), but nothing consumes the
  selection for an export yet, since Milestone 7 owns file generation.
  The selection UI is real and reusable groundwork for that milestone,
  not a stub.
- Reconciling two independent `Lead` rows that turn out to describe the
  same real business (both pre-existing before a merge) is an explicitly
  deferred capability - the data is never lost (the loser's `Lead` and
  everything attached to it stays fully intact and queryable by ID), but
  no UI or endpoint surfaces "these two leads should probably be one"
  today. A future enhancement, not a Milestone 6 requirement.
- `LeadVerification` remains unbuilt, consistent with it appearing in
  neither Milestone 6's build list nor its feature list - if a future
  milestone needs it, it is added then, not spread thin across features
  it wasn't asked to be part of here.
