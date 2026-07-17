# ADR-0010: Google Places connector design, and its live-verification gap

## Status
Accepted, with one explicitly unresolved verification gap (see Consequences).

## Context
Milestone 3 calls for a real Google Places integration (Text Search,
Nearby Search "where justified," Place Details, field masks, pagination,
quota management, API usage measurement, source attribution, business
normalization, provider health checks, and mocked adapter tests) built
against the same `BaseConnector` interface `MockConnector` already
implements, so campaign orchestration code needs no changes to use it.

No Google Cloud API key was available while building this. The
architecture's own `.env.example` already reserved `GOOGLE_PLACES_API_KEY`
for this milestone, confirming it was anticipated that a real key would be
supplied later, separately from implementation.

## Decision

**Interface and registration.** `GooglePlacesConnector` implements
`BaseConnector` exactly like `MockConnector` and is registered in
`connector_sdk.registry` under `"google_places"`. Its constructor reads
`GOOGLE_PLACES_API_KEY` from the environment lazily and never raises if
the key is missing - only calling into the connector (`search`,
`get_place_details`, `search_nearby`, `health_check`) raises
`ConnectorAuthError` at that point, so an unconfigured key never breaks
process startup, matching every other `ConnectorAuthError` case in the
codebase.

**No cached HTTP client (ADR-0009, generalized).** `GooglePlacesConnector`
instances are module-level singletons in the registry, reused across the
worker's per-task event loops (ADR-0009). `httpx.AsyncClient` connections
are bound to the event loop that created them, exactly like asyncpg and
redis-py's connections - so this connector opens a fresh
`httpx.AsyncClient` per request rather than holding one at instance scope.
This is the third async client this codebase has had to get right on this
point (SQLAlchemy's engine, redis-py, now httpx); ADR-0009 already
predicted a new task type built the naive way would reintroduce this bug
class, and this connector is exactly that new task type.

**Cursor encoding carries two pieces of state.** The worker's task chain
(`worker.campaign_tasks`) relies entirely on `SearchPage.has_more` to
decide whether to enqueue another page - it does not independently track
how many results a campaign has accumulated so far (see `MockConnector`,
which has the same contract). Google's own `nextPageToken` is opaque and
carries no count information, so this connector's own cursor is
`"{count_so_far}:{google_page_token}"` - the only channel that survives
between one page's Celery task and the next (possibly a different worker
process). This lets the connector enforce `query.result_limit` itself,
truncating a page's results client-side the moment the cumulative count
would exceed it, even if Google's own `nextPageToken` says more are
available.

**Page-token-related `INVALID_ARGUMENT` is transient, not permanent.**
Google's documented behavior includes a short activation delay before a
freshly issued `nextPageToken` becomes valid. Rather than sleeping inside
the connector, an `INVALID_ARGUMENT` response to a request that included
a `pageToken` is mapped to `ConnectorTransientError` (retryable);
Celery's existing 5-60s backoff comfortably covers the activation delay,
and a token that is genuinely expired/invalid will keep failing until
`max_retries`, which is the correct terminal outcome either way. The same
`INVALID_ARGUMENT` on a request with *no* page token (a malformed initial
query) is `ConnectorPermanentError`, since retrying an identically
malformed query would fail identically forever.

**Client-side filtering for fields Google's API doesn't accept as
parameters.** Text Search has no "must have a phone number" or "must/must
not have a website" request parameter, so `must_have_phone`,
`website_requirement`, and `min_reviews` are applied to the real,
already-returned records after the fact - filtering never invents or
removes data, only excludes real records that don't match.

**Minimal field masks.** `TEXT_SEARCH_FIELD_MASK`/`PLACE_DETAILS_FIELD_MASK`
request only the fields `_business_from_place` actually reads. Google's
Places API (New) bills per requested field/SKU, so requesting the default
"everything" mask would be needlessly expensive at any real volume.

**Place Details and Nearby Search are real, working, but not the default
path.** `get_place_details` and `search_nearby` are both implemented
against Google's real endpoints and covered by mocked tests, satisfying
the architecture's explicit line items for both - but `search()`'s Text
Search path already returns every field `BusinessRecord` needs with the
field mask above, so hydrating each result with a second, separately
billed Place Details call would be pure quota waste with no data benefit
today. `search_nearby` needs a latitude/longitude center, which
`SearchQuery`/`CampaignFilter` don't carry yet (campaigns are defined by
text location filters) - it's a real capability ready for a future
milestone that adds coordinate-based filters, not one the current task
chain calls.

**Business normalization never fabricates.** Every `BusinessRecord` field
either comes directly from Google's response or is `None` - a place
missing `displayName` (documented as required by Google's schema, but
handled defensively anyway) falls back to a label built from its own
stable Google place ID, never an invented plausible-sounding name.

## Consequences

- **This connector has not been exercised against the real Google Places
  API.** Every claim above about Google's request/response contract and
  error format is reasoned from Google's published Places API (New)
  documentation, and verified here via `tests/test_google_places.py`,
  which mocks the HTTP transport with responses shaped exactly like that
  documented contract (success, pagination, every error class this module
  maps, missing-optional-field cases, address-component parsing). This is
  real, genuine test coverage of this connector's own logic - but it is
  categorically not the same thing as a live call succeeding against
  Google's actual servers, and no such live call has been made.
- **Before relying on this connector in any real campaign**, a Google
  Cloud project needs the Places API (New) enabled, billing configured,
  an API key issued and set as `GOOGLE_PLACES_API_KEY`, and at minimum one
  live `search()` call run against it and inspected by a human - ideally
  via a small smoke-test script, not by launching a real tenant's
  campaign against it first.
- If Google's actual response shapes differ from what's assumed here in
  any way the mocked tests didn't anticipate (a field renamed, an error
  format variant, a rate-limit header not accounted for), that will only
  surface on first live use, not before. This is the single largest
  unresolved risk this milestone carries forward - see
  `docs/project-status.md`'s Milestone 3 section.
- The frontend campaign-creation form still only offers the `mock`
  connector; wiring `google_places` into the UI as a selectable source is
  deliberately left out of this milestone's scope (the original
  architecture's Milestone 3 line items are all backend-connector items),
  and doing so before a real key exists would offer users a choice that
  can only fail.
