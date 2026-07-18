# ADR-0011: Business entity consolidation, and the Milestone 2 persistence gap it fixes

## Status
Accepted.

## Context
Milestone 2's campaign task chain (`worker.campaign_tasks`) already
discovered real businesses via a connector and stored each page's results
in `CampaignTask.result_snapshot` - a JSON blob of that one page. That was
sufficient for Milestone 2's own scope (proving the task chain worked end
to end), but it left no addressable, queryable `Business` row anywhere:
nothing a later feature could look up by ID, enrich, deduplicate, or
attach evidence to. Milestone 4 (website enrichment) needs exactly that -
"crawl *this business's* website and store what you find *on it*" only
makes sense if "this business" is a row with an identity that outlives one
campaign's result page.

The original architecture's Business Data Model section describes eleven
entities: `Business`, `BusinessIdentifier`, `BusinessCategory`,
`BusinessLocation`, `BusinessContact`, `BusinessWebsite`,
`BusinessSocialProfile`, `BusinessSourceRecord`, `BusinessFieldProvenance`,
`BusinessSnapshot`, `BusinessMergeHistory`. Building eleven separate
tables for a milestone whose actual scope is "safe crawler + detectors +
evidence storage" would be premature - most of that list exists to serve
Milestone 5 (deduplication) and Milestone 6 (the lead workspace), neither
of which are in scope yet.

This is the same situation ADR-0008 already resolved once for the
campaign domain: the original architecture's fine-grained entity list is
a complete conceptual model, not a literal table-per-entity mandate, and
collapsing genuinely 1:1 sub-entities into columns on their parent avoids
premature joins nothing in the current milestone needs.

## Decision

**One new table, `businesses`, absorbs six of the eleven entities.**
`BusinessIdentifier`, `BusinessCategory`, `BusinessLocation`,
`BusinessContact`, `BusinessWebsite`, and `BusinessSocialProfile` are all,
in this architecture, a 1:1 relationship to one `Business` - a business
has exactly one canonical name, one address, one public phone, one
website. Each becomes a nullable column on `Business` (`name`, `category`,
`subcategory`, `address`, `country`/`region`/`city`/`area`, `latitude`/
`longitude`, `phone`, `email`, `website`, `canonical_domain`,
`google_place_id`, `google_maps_url`, `rating`, `review_count`,
`business_status`) instead of five separate one-row-per-business tables
that would only ever be joined 1:1 anyway.

**`BusinessFieldProvenance` becomes a JSONB column, not a table.** The
architecture's own rule - "every collected field must preserve source,
source URL, extraction method, collection timestamp, confidence,
provider-native identifier" - is enforced per-field, but a normalized
`BusinessFieldProvenance` table (one row per field per business) buys
nothing over a `field_provenance: dict` JSONB column keyed by field name,
since provenance is always read and written as "the whole provenance
record for this business," never queried or filtered by field name across
businesses. `upsert_business_from_discovery` (`app.modules.businesses.
repositories`) writes one `field_provenance[field_name] = {"source",
"source_record_id", "confidence", "collected_at"}` entry per discovery
field actually present in the incoming record - never for fields the
source didn't provide, so a missing field is genuinely absent from
provenance, not recorded with a fabricated placeholder.

**`BusinessSourceRecord` gets its own real table**, unlike the five
entities above, because it is genuinely 1:many: the same business can be
(re-)discovered by more than one campaign, and by more than one source in
future milestones (Google Places today, CSV import and other connectors
later - see Milestone 8). Each row is the raw, unmodified snapshot from
one discovery event, uniquely keyed on `(tenant_id, source,
source_native_id)` so re-discovering the same real-world business (same
Google place ID, found again by a second campaign) updates the existing
row's `campaign_id`/`source_url`/`collected_at`/`raw_snapshot` rather than
creating a duplicate - and, critically, resolves back to the *same*
`Business` row rather than creating a second one. `test_campaign_tasks.py`
(`test_rediscovering_the_same_business_updates_the_existing_row`) proves
this: launching two campaigns with identical filters against the
deterministic mock connector reuses the same 45 `Business` IDs, not 90.

**`BusinessSnapshot` and `BusinessMergeHistory` are deferred entirely, not
built as empty tables.** Both are explicitly about deduplication history -
"what did we merge, and when, and what did the record look like before" -
which is Milestone 5's concern. There is nothing for either table to
record yet, since nothing merges businesses today; building them now
would be exactly the kind of speculative-for-a-later-milestone table this
ADR series has consistently avoided.

**`Business.email` is set only by enrichment, never by discovery.**
Neither `MockConnector` nor `GooglePlacesConnector` (Milestone 3) return
an email field at all - Google Places' schema has no public business
email field, and the architecture explicitly warns against fabricating
missing lead fields. `upsert_business_from_discovery`'s own
`_DISCOVERY_FIELDS` tuple deliberately excludes `email`, so there is no
code path by which discovery could ever set it, even accidentally; the
enrichment task (`worker.enrichment_tasks`, see ADR-0012) is the only
writer.

**One `BusinessEnrichment` run produces many `EnrichmentEvidence` rows**,
a new two-table pair introduced alongside `Business` rather than added to
the eleven-entity list above, since the architecture's own Website
Enrichment section requires storing, per finding: "exact source URL,
detector type, structured result, confidence, collection timestamp,
minimal supporting snippet" - which is what `EnrichmentEvidence` stores,
one row per detector finding, linked to the `BusinessEnrichment` run that
produced it.

## Consequences
- `apps/api/app/modules/businesses/` (models, repositories, schemas,
  routes) and `apps/api/app/modules/enrichment/` (same four files) are new
  modules; `apps/worker/worker/campaign_tasks.py` now persists a
  `Business` + `BusinessSourceRecord` for every discovered page result, in
  addition to the pre-existing `CampaignTask.result_snapshot` (kept
  unchanged, as a raw per-page audit copy - not the queryable source of
  truth anymore).
- If Milestone 5 (deduplication) later needs `BusinessSnapshot`/
  `BusinessMergeHistory`, they are added as new tables at that point, not
  retrofitted into this migration - this ADR does not claim to have
  pre-built Milestone 5's schema, only to have left room for it (the
  `field_provenance` JSONB shape and the source-record table both
  generalize cleanly to a future merge/dedup workflow without a breaking
  schema change).
- A future field that genuinely needs cross-business querying (e.g. "find
  all businesses whose phone provenance came from source X") would need
  provenance to move out of JSONB into a real table at that point - not a
  concern today, since nothing queries provenance by field across
  businesses yet.
