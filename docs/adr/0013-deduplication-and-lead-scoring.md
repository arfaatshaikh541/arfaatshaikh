# ADR-0013: Deduplication engine and explainable lead scoring

## Status
Accepted.

## Context
Milestone 5 is "Deduplication and Lead Intelligence": identifier/domain/
phone/address/fuzzy matching, duplicate candidates, merge history, undo
merge, lead scoring, confidence scoring, opportunity detection,
recommended services, and scoring explanations - all against real
`Business`/`BusinessSourceRecord`/`BusinessEnrichment`/
`EnrichmentEvidence` data that now exists from Milestones 2-4.

The architecture's own Deduplication section specifies an exact priority
order (identifier, then domain, then phone, then name+address, then
"conservative fuzzy matching") and an explicit non-negotiable rule:
"never silently merge uncertain records ... create duplicate candidates
for human review ... preserve source records after merging ... retain
merge history ... support undo merge." Its Lead Scoring section gives a
worked example - 7 factors summing to 100 (category+location match
20/20, business status+reviews 15/15, contact availability 12/15,
commercial opportunity 18/20, WhatsApp 8/10, enrichment confidence 8/10,
freshness 5/10 = 86/100) - which this milestone's scoring engine
replicates almost exactly, since a fully-specified worked example is a
much stronger design signal than a menu of "possible" factors.

The Lead Model section lists eleven entities (`Lead`, `LeadCampaign`,
`LeadScore`, `LeadScoreFactor`, `LeadOpportunity`, `LeadRecommendation`,
`LeadAssignment`, `LeadNote`, `LeadTag`, `LeadStatusHistory`,
`LeadVerification`, `LeadDuplicateCandidate`, `SavedLeadView`) - most of
which belong to Milestone 6's "Lead Workspace" (assignments, notes, tags,
statuses, bulk actions, saved views are all explicit Milestone 6 build
items, not Milestone 5's).

## Decision

### Deduplication (`app.modules.businesses.dedup`)

**One confidence threshold decides auto-merge vs. human review**, rather
than five special-cased rules. Each match tier gets a fixed confidence:
identifier 1.00, domain 0.95, phone 0.90, name+address 0.88 - all above
`AUTO_MERGE_CONFIDENCE_THRESHOLD = 0.85`, so all four exact tiers merge
immediately. Fuzzy name matching's confidence is `similarity *
0.75`, capped so it can *never* reach the threshold even at a perfect
1.0 similarity (which the exact name+address tier would have already
caught anyway) - "conservative" is enforced structurally, not by hoping
a human tuned the fuzzy threshold correctly.

**Matching checks tiers in the architecture's exact priority order**,
stopping at the first tier with a hit, since a stronger signal makes a
weaker one redundant - identical to checking "does this resolve by
identifier? by domain? by phone? by name+address?" in sequence.
Name+address and fuzzy matching are additionally scoped to same-city
candidates (a new index on `Business.city`) - both for correctness (a
name+address match across two different cities isn't "conservative")
and to keep the comparison set bounded without needing a full-text/
trigram index this milestone doesn't otherwise need.

**Merges are soft, field-combining, and precisely reversible.** The
losing `Business` row is never deleted - `merged_into_id` is set instead
(a new self-referential composite FK, same-tenant-enforced like every
other composite FK in this schema). Its `BusinessSourceRecord`/
`BusinessEnrichment`/`EnrichmentEvidence` rows are reassigned onto the
winner, and the exact row IDs moved are recorded in
`BusinessMergeHistory.moved_records` - so `undo_merge` reverses only
what *this* merge moved, never anything created afterwards that happens
to share the winner's `business_id`. Field data is combined by the same
"never overwrite higher-confidence data silently" rule
`field_provenance` already enforces at discovery time (ADR-0011): a
field the loser knows with strictly higher confidence than the winner
currently has fills in a gap or replaces a lower-confidence value: never
the reverse. `BusinessMergeHistory.field_changes` records the winner's
pre-merge value for every field actually touched, so undo restores it
exactly.

**Winner selection favors the more complete record**: the business with
more populated `field_provenance` entries wins (a thinly-populated fresh
discovery should never displace an already-enriched record), ties broken
by whichever was discovered first.

**`BusinessDuplicateCandidate` rows are deduplicated by pair**, not by
match event - `business_id_a`/`business_id_b` are always stored with the
smaller UUID first, so the same real-world pair can only ever have one
candidate row regardless of which business triggered the check. A
rejected candidate is never re-proposed on a later (re)discovery
("permit manual review and correction" means a human's decision sticks);
a still-*pending* candidate is upgraded in place if a later check finds
a stronger match type for the same pair.

**Runs synchronously, inline in the discovery task**, not as a separate
Celery task or queue. `worker.campaign_tasks` calls
`process_new_business_for_duplicates` right after each
`upsert_business_from_discovery` call, in the same transaction. This is
deliberately different from Milestone 4's enrichment crawl (a genuinely
slow, external-network operation that has to be a background job):
matching here is a handful of indexed-equality lookups (identifier/
domain/phone) plus a same-city-bounded scan (name+address/fuzzy) against
data already in Postgres - cheap enough to run inline, and doing so
means a duplicate is caught (or flagged) at the moment it's discovered,
not on some later sweep.

**Never merges more than one pair per discovery event.** If three or
more businesses are genuinely the same real place, the first
(re)discovery resolves the strongest pair it finds; later
(re)discoveries of any of the remaining businesses will find and resolve
the rest, converging over multiple discovery events rather than
attempting an all-at-once N-way merge in one pass. This is a deliberate
v1 simplification, not a correctness gap: `find_duplicate_matches` is
always re-run against the tenant's *current* canonical business set, so
nothing is ever missed, only resolved incrementally.

### Lead scoring (`app.modules.leads.scoring`)

**The 7-factor, 100-point algorithm is the architecture's own worked
example**, replicated with the same factor names and point weights
(category+location match /20, business status+reviews /15, contact
availability /15, commercial opportunity /20, WhatsApp presence /10,
enrichment confidence /10, freshness /10). Each factor's `explanation`
string is built from the real values that produced it and its `evidence`
dict points at exactly what was checked - never an unexplained number,
per the architecture's explicit prohibition.

**Every score is a new, immutable row** (`LeadScore`, `algorithm_version
= "v1"`) rather than an update-in-place - a lead's score history is
preserved, and adding a v2 algorithm later never rewrites v1's history,
it just starts appending v2 rows. Factors live in a `factors` JSONB
column on `LeadScore`, not a separate `LeadScoreFactor` table, for the
same "no join for what's always read together" reasoning ADR-0011 gave
`field_provenance`: a score's factor breakdown is always read and
written as one complete unit, never queried by factor across leads.

**"Commercial opportunity" scores *higher* when more opportunities are
found** - the architecture's own worked example does this too ("no
online reservation detected: 18/20" is a near-full score, not a
penalty). This is intentional and specific to what this platform sells:
a business with zero detected gaps is a weak lead for a service that
exists to pitch fixes for those gaps, even though the business itself
might be thriving. `whatsapp_presence` is the deliberate exception -
missing WhatsApp specifically costs only 2 of 10 points (8/10 missing,
matching the worked example exactly), since it's treated as one minor
channel among several, not the primary "is there something to sell"
signal `commercial_opportunity` already captures.

**Opportunity detection never invents a problem.** Every
`LeadOpportunity` is either a direct 1:1 read of one `EnrichmentEvidence`
row (the detector already observed it - `website_unavailable`,
`ssl_failure`, `missing_mobile_viewport`, `missing_online_booking`,
`missing_online_ordering`, `missing_whatsapp`, `missing_contact_form`,
`missing_contact_method`, `weak_page_metadata`,
`outdated_copyright_year`) or a direct read of a `Business` field
(`no_website` when `business.website` is `None`, `low_review_activity`
from the business's own real `rating`/`review_count`) or a whole-crawl
absence check already computed once by `worker.enrichment_tasks`
(`missing_social_links`, added here since no individual detector emits
"no social links found across the whole crawl" the way it already emits
`missing_whatsapp`/`missing_online_booking`/etc.). `evidence_reference`
on every opportunity points at exactly what was observed, so a human can
verify it rather than trust it blindly - the same principle
`EnrichmentEvidence` already established.

**Recommended services are a data-driven rule table**
(`OPPORTUNITY_RECOMMENDATIONS: dict[str, tuple[str, ...]]`), not
restaurant-specific if/else branches - satisfying the architecture's
explicit "do not hardcode restaurants into core architecture" and
"support opportunity rules by industry" requirements directly: every key
is a generic opportunity type (any business can be missing online
booking, not just a restaurant), and a future per-industry override
would key off `Business.category` to select a different rule table
without changing this module's shape. `crm_implementation` is left in
the architecture's recommendation vocabulary but deliberately unmapped -
no opportunity type here actually evidences "needs a CRM," and force-
fitting one would violate "never invent problems" for the sake of using
every listed recommendation type.

**Recommendation confidence is the average of its supporting
opportunities' confidences**, and `supporting_opportunity_ids` always
references real, already-persisted `LeadOpportunity` rows - opportunities
are persisted first (so they have real IDs), then recommendations are
built from the persisted rows, never from the pre-persistence dicts.

**Re-scoring replaces stale opportunities/recommendations, not
accumulates them** (`leads_repo.replace_opportunities`/
`replace_recommendations` upsert by `(lead_id, type)` and delete
anything no longer detected) - a lead's opportunity list reflects its
*current* state; an opportunity the business has since fixed (e.g. added
online booking) stops appearing, while one still present keeps its
original `detected_at` rather than looking freshly discovered on every
re-score.

**Runs synchronously, in-request**, not as a Celery task. Unlike
enrichment (a real website crawl) or dedup (indexed DB lookups at
discovery time), scoring is pure computation over already-persisted data
- no network call, no crawl, nothing that benefits from being a
background job. `POST /businesses/{id}/score` computes and returns the
full breakdown in one request.

### Lead entity consolidation

Only `Lead`, `LeadScore`, `LeadOpportunity`, and `LeadRecommendation` are
built this milestone. `LeadCampaign` is not a separate table: a lead's
originating campaign(s) are already recoverable via
`BusinessSourceRecord.campaign_id` on its underlying `Business` (used
directly by the `category_and_location_match` factor to find the
relevant `CampaignFilter`), so a redundant attribution join table would
only duplicate data that already exists - the same reasoning ADR-0008/
0011 already applied to `CampaignSource` and `BusinessSourceRecord`.
`LeadAssignment`, `LeadNote`, `LeadTag`, `LeadStatusHistory`,
`LeadVerification`, `SavedLeadView` are Milestone 6's "Lead Workspace"
scope, per the milestone's own explicit build list (statuses,
assignments, notes, tags, bulk actions, saved views are all *there*, not
here) - `Lead.status` is stored now (with the architecture's full 10-
value lifecycle already in the column's valid-value set, so Milestone 6
never needs a migration just to widen it), but Milestone 5 only ever
sets it to `"new"`; no transition workflow exists yet.
`LeadDuplicateCandidate` is `BusinessDuplicateCandidate` instead -
matching happens on `Business` rows, before a `Lead` necessarily exists
for either side of a candidate pair, so naming and scoping it to
`Business` is the structurally accurate choice, not `Lead`.

## Consequences
- New modules: `app.modules.businesses.dedup`,
  `app.modules.businesses.normalize` (shared name/phone/address/domain
  normalization, split into its own module specifically so
  `repositories.py` and `dedup.py` can both import it without a
  circular import), `app.modules.leads` (models, repositories, schemas,
  scoring, routes). `worker.campaign_tasks` gains one call
  (`process_new_business_for_duplicates`) after each discovery upsert.
- Six new tables (`business_duplicate_candidates`,
  `business_merge_history`, `leads`, `lead_scores`,
  `lead_opportunities`, `lead_recommendations`) plus two new columns and
  four new indexes on `businesses` (`merged_into_id`,
  `normalized_phone`, plus indexes on `city` and `google_place_id`) -
  all RLS-enabled/FORCE'd with the same tenant-match-or-bypass policy as
  every prior milestone's tables.
- New permission: `leads.score` (paired with the existing `leads.enrich`
  pattern, granted to the same three roles). Duplicate-candidate review
  and merge/undo actions reuse the existing `leads.edit` permission
  rather than adding new ones - the pre-existing Milestone 1 permission
  catalog already anticipated a coarser-grained "editing lead/business
  data" permission that these actions fit naturally into.
- **Two pre-existing Milestone 4 worker tests changed their assertions**,
  not their intent: `test_completed_campaign_persists_individual_business_rows`
  and `test_rediscovering_the_same_business_updates_the_existing_row`
  previously hardcoded "exactly 45 Business rows" for a 45-result mock
  campaign. With dedup now active, the mock connector's limited (10
  adjective x 10 suffix = 100 combinations) name generator can, across
  45 random draws, produce two "different" fake businesses that share
  the exact same generated name and (derived from it) website domain -
  a real domain-tier match that correctly gets auto-merged. This was
  found by the test suite itself failing (44 rows, not 45) after wiring
  dedup into the discovery pipeline - not a bug in dedup, a correct
  response to a data collision the test's old hardcoded count didn't
  anticipate. The tests now assert the real invariants ("no duplicate
  rows," "no two canonical businesses share a domain," "re-discovery
  never creates new rows") instead of a fragile exact count tied to the
  mock generator's specific word-list size.
- False-positive and false-negative scenarios are directly tested
  (`apps/api/tests/test_deduplication.py`): a fuzzy near-match creates a
  candidate rather than merging; two genuinely different businesses in
  the same city produce no match at all; a same-name business in a
  *different* city produces no match (the city-scoping working as
  intended); matching never crosses tenants.
- No frontend UI exists yet for reviewing duplicate candidates, merging/
  undoing merges, or viewing a lead's score/opportunities/
  recommendations - this milestone's scope (per the original
  architecture) is backend-only, matching Milestone 4's own pattern; a
  `/campaigns/[id]` duplicate-review panel and lead detail view are
  natural Milestone 6 (Lead Workspace) follow-up work.
