# ADR-0028: OpenStreetMap/Overpass connector

## Status
Accepted.

## Context
The only real (non-mock) business-data connector this codebase has ever
had is Google Places, which needs a paid, credentialed Google Cloud API
key with billing enabled - a real barrier for anyone who wants to try
this platform against real business data without committing to that.
The user asked directly: "How about we use OpenStreetMap + Overpass
API" - Overpass is OpenStreetMap's standard read-only query service,
free, with no signup or credential of any kind.

No spec text in this session named this milestone; it's a direct,
explicit user request rather than a self-selected gap, unlike every
milestone since 10.

## Decision

### A third connector, not a replacement
`OverpassConnector` implements the same `BaseConnector` interface as
`MockConnector`/`GooglePlacesConnector` and is registered under a new
`"osm"` key alongside them - `mock` and `google_places` are unchanged.
Campaign orchestration code (the worker's task chain, credit
reservation/reconciliation, dedup, scoring) needed zero changes; this is
exactly the abstraction boundary ADR-0002/ADR-0010 were built to make
adding a third real source a connector-layer-only change.

### `BaseConnector.supports_rating_filter` - a new, small interface addition
OpenStreetMap's schema has no rating/review concept at all - not
"sometimes populated," structurally absent. Silently accepting a
campaign's `min_rating`/`min_reviews` filter for this source and never
enforcing it would be worse than an error: the filter would appear to
have taken effect while doing nothing. `BaseConnector` gained
`supports_rating_filter: bool = True` (unchanged default, so
`MockConnector`/`GooglePlacesConnector` are unaffected);
`OverpassConnector` sets it `False`, and `campaigns.services.
create_campaign` now rejects `min_rating`/`min_reviews` outright for any
connector that sets this false, with a clear validation error, both
server-side (authoritative) and client-side (the campaign form's zod
schema mirrors the same rule for immediate feedback, kept in sync by
hand since the frontend has no live connector registry to query).

### Industry -> OSM tag mapping, not free text
OSM has no "industry" field - every real-world category is one specific
`tag=value` pair (`amenity=restaurant`, `shop=car_repair`, etc.).
`INDUSTRY_TAG_MAP` covers ~30 common lead-generation categories
(restaurants, cafes, hotels, auto repair, salons, gyms, pharmacies,
and more), matched case-insensitively against `category` (preferred) or
`industry`, mirroring `GooglePlacesConnector._build_text_query`'s own
precedence. An industry string not in the table raises
`ConnectorPermanentError` with the actual supported list, rather than
silently returning zero results (which would look identical to "no
matches found" and mislead the user) or guessing at a mapping.

### No server-side pagination - re-query and slice, like MockConnector
Overpass has no pagination concept: a query returns every matching
element in one response. Rather than building a stateful cache, this
connector re-runs the *same* deterministic query on every `search()` call
(one call per campaign page, per the existing task-chain design) and
slices the requested page out of the freshly-fetched list - the same
"recompute deterministically, slice by page" contract `MockConnector`
already uses. The cost is real: a multi-page campaign re-queries Overpass
once per page instead of once total. This was chosen over an
instance-level result cache because the connector registry's instances
are shared module-level singletons across every tenant's requests - a
naive cache would need per-query keys, TTLs, and eviction to avoid
unbounded memory growth and cross-tenant staleness, real complexity this
milestone's scope doesn't justify yet given Overpass's own queries for a
single city+category are typically fast.

### Country-then-city area chaining, not lat/lon
`CampaignFilter` has no latitude/longitude fields - campaigns are defined
by text location filters (country/region/city/area), matching how
`GooglePlacesConnector`'s Text Search already works. The Overpass query
resolves the named country's OSM administrative area first, then the
city within it (`area["name"="UAE"]["admin_level"="2"]->.country;
area["name"="Dubai"](area.country)->.searchArea;`), avoiding ambiguity
for common city names that exist in multiple countries. `region`/`area`
filters are not used to further scope the query in this version
(deliberately deferred - nesting a third level of OSM area matching
reliably across arbitrary neighbourhood names was judged not worth the
complexity for a first version); `radius_km` is unsupported for the same
reason as the missing lat/lon center. Both gaps are disclosed, not silent.

### Never fabricate what OSM doesn't have
Every `BusinessRecord` field this connector produces traces to a real OSM
tag or a defensible, documented fallback:
- `rating`/`review_count` are always `None` - never fabricated.
- `business_status` is `None` (genuinely unknown) unless a
  `disused:`/`abandoned:`-prefixed tag is present, in which case it's
  `"closed_permanently"` - OSM doesn't reliably track operating status,
  so "operational" is never assumed the way it might be for a source that
  actually tracks it.
- `country`/`city` fall back to the queried country/city only because the
  Overpass query itself already scoped the search to that named
  administrative area - a structurally defensible completion, not a
  guess. `region`/`area` have no such fallback, since the query doesn't
  actually filter by them.
- A record with no `name` tag gets `f"OSM {type} {id}"` as its label -
  the source's own stable identifier, never an invented business name,
  the same convention `GooglePlacesConnector` already uses.

### Frontend: a source picker, not a silent default change
The campaign-creation form previously hardcoded `source_key: "mock"` with
no way to choose otherwise (known limitation #9 - `google_places` was
deliberately never exposed there, since a connector that can only fail
without a real key would be poor UX). A new "Data source" select offers
"Mock (sample data)" (still the default) and "OpenStreetMap (real,
free)", with the form's own explanatory caption switching to describe
whichever is selected, including the no-rating-data disclosure.
`google_places` remains unexposed in this form for the same reason as
before - unlike OSM, it still needs a credential this environment
doesn't have.

### Live-verified, including the honest failure path
Per the standing rule for UI changes, this was driven through a real
`uvicorn`/Celery-worker/`next dev` stack in headless Chromium
(Playwright): registered a user, opened the campaign form, confirmed the
caption changes when switching to OpenStreetMap, confirmed the
min_rating field is rejected client-side for this source, cleared it and
created the campaign for real, then **launched it for real**. This
sandbox's egress proxy rejects every Overpass/OpenStreetMap host tried
(`overpass-api.de`, `overpass.kumi.systems`, `nominatim.
openstreetmap.org`) with a policy-level 403 - the same class of
restriction the website crawler and Stripe already carry (confirmed
directly with `curl` before writing a line of connector code, not assumed).
Launching the real campaign against this genuinely blocked network
correctly and cleanly reached a `"failed"` terminal state after retrying
through the existing, already-tested retry/backoff machinery (`worker/
retry.py`'s `retry_or_finalize`), with the real error
(`ConnectorTransientError: Overpass request failed: 403 Forbidden`)
recorded in both the campaign's Errors list and its status-history
timeline, and the full 20-credit reservation correctly released (wallet
balance confirmed unchanged afterward, via `GET /usage/wallet`). This is
not a live proof the connector correctly parses real Overpass data - that
remains unverified, exactly like Google Places' own disclosed gap - but
it is a genuine, live proof that a real network failure through this
brand-new connector is handled correctly end-to-end by machinery this
codebase already trusts.

## Consequences
- New: `packages/connector-sdk/connector_sdk/overpass.py`
  (`OverpassConnector`), `packages/connector-sdk/tests/test_overpass.py`
  (23 mocked-adapter tests).
- Modified: `connector_sdk/base.py` (`supports_rating_filter` attribute),
  `connector_sdk/registry.py` and `__init__.py` (registration),
  `apps/api/app/modules/campaigns/services.py` (`create_campaign` rejects
  `min_rating`/`min_reviews` for a connector with `supports_rating_filter
  = False`), `apps/api/tests/test_campaign_engine.py` (2 new tests: the
  rejection, and successful creation without those filters),
  `apps/web/app/(tenant)/campaigns/page.tsx` (Data source selector,
  per-source caption, matching client-side zod validation).
- No schema/migration change - `Business`/`BusinessSourceRecord` already
  had every column this connector needs; `google_maps_url` is reused
  (unlabeled anywhere in the frontend as Google-specific) to hold a real
  `openstreetmap.org` record link instead.
- New disclosed limitation: this connector has never been exercised
  against the real Overpass API - the same shape of gap as Google Places,
  caused by this sandbox's egress policy rather than a missing
  credential. Its real-network *failure* path has been proven live; its
  real-network *success* path (actual query parsing against Overpass's
  real JSON) has not.
- New disclosed limitations, by design, not fixed here: `region`/`area`
  campaign filters and `radius_km` are not applied to the Overpass query
  itself for this source; an industry string outside `INDUSTRY_TAG_MAP`
  is rejected rather than guessed at; multi-page campaigns against this
  source re-query Overpass once per page rather than once total.
