# ADR-0008: Campaign entity consolidation for Milestone 2

## Status
Accepted.

## Context
The original architecture's entity list for the campaign/job engine names
more tables than Milestone 2 actually needs to ship a working, correct
campaign lifecycle: `CampaignSearchArea`, `CampaignSource`,
`CampaignUsageReservation`, `CampaignQuery`, and `SearchCursor` were all
called out as separate entities, alongside `Campaign`, `CampaignFilter`,
`CampaignJob`, and `CampaignTask`.

Building each of those as its own table would mean four extra joins on
every read path, for relationships that are 1:1 or trivially scalar in
Milestone 2's actual scope (one connector per campaign; one filter per
campaign; one reservation per campaign at a time).

## Decision
Consolidate the trivial 1:1 entities into columns on the table they always
accompany, and defer splitting them out until a real requirement forces a
1:many relationship:

- `CampaignSearchArea` -> fields live directly on `CampaignFilter`
  (`country`, `region`, `city`, `area`, `radius_km`). A campaign has
  exactly one search area in Milestone 2; there is no multi-area campaign
  yet.
- `CampaignSource` -> a plain `source_key` string column on `Campaign`
  (looked up in the connector registry - see `connector_sdk.registry`).
  Milestone 2 supports exactly one connector per campaign; a join table
  for that today would be pure ceremony.
- `CampaignUsageReservation` -> a nullable `reservation_id` FK directly on
  `Campaign`, pointing at the existing `credit_reservations` table from
  the Milestone 1 usage ledger (ADR-0004). A campaign holds at most one
  open reservation at a time (reserved at launch, committed or released
  at finalization), so a separate join table would carry no information
  a single FK doesn't already.
- `CampaignQuery` and `SearchCursor` -> live on `CampaignJob`/`CampaignTask`
  instead of their own tables: `CampaignTask.cursor_in`/`cursor_out` are
  plain nullable string columns (the connector SDK's cursor is an opaque
  string - see `connector_sdk.types.SearchPage.next_cursor`), and the
  query parameters needed to resume a page are reconstructed on demand
  from `Campaign`/`CampaignFilter` via `campaigns.services.build_search_query`
  rather than persisted as their own row per task.

The tables that *do* exist as their own entities are the ones with a real
1:many or independently-queried lifecycle: `Campaign`, `CampaignFilter`,
`CampaignUsageEstimate`, `CampaignEvent` (append-only status-change log),
`CampaignError` (append-only per-task error log), `CampaignJob`, and
`CampaignTask` (one row per page, the actual fan-out unit).

## Consequences
- Fewer joins on every campaign read path; `CampaignDetailResponse` is a
  single `Campaign` + `CampaignFilter` fetch, not a five-table join.
- If a future milestone needs multiple search areas per campaign, or
  multiple connectors queried in parallel for one campaign, or a
  reservation history beyond "the current one," those will need to become
  real tables at that point - this consolidation is scoped to what
  Milestone 2 actually does, not a permanent architectural ceiling.
- `docs/project-status.md` and the campaign model docstrings
  (`app/modules/campaigns/models.py`) point back to this ADR so the
  reduced entity count reads as a deliberate decision, not a shortcut that
  was never revisited.
