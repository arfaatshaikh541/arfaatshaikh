# GRIDKEEP Lead Intelligence — Project Status

## Current milestone
**Milestone 7: Exports** — implementation complete, backend and frontend both. XLSX and CSV exports of leads (bulk-selected or "everything matching my current filters"), a four-sheet workbook (Leads, Campaign Summary, Scoring Rules, Errors) with styled headers, frozen panes, autofilter, wrapped cells, hyperlinks, and formula-injection protection applied uniformly to both formats; a background Celery export task on its own `queue.export`; tenant-scoped object storage with signed, expiring download URLs regenerated fresh per request; export status tracking and per-lead partial-completion error recording; and workbook-reopen-and-validate tests per the architecture's explicit requirement. No MinIO binary is installable in this sandbox (no Docker daemon, no internet access to fetch one), so `moto`'s real local S3-API server stood in for both the automated tests and a full manual live-verification pass (registration → campaign → worker discovery → scoring → bulk-selected XLSX export → filter-based CSV export → real presigned-URL download → reopened and validated workbook → the actual `/leads` and `/exports` UI in a live browser). See ADR-0015. Pending your review before proceeding to Milestone 8.

## Completed work

### Monorepo & infrastructure
- pnpm workspace (`apps/web`, `packages/ui`, `packages/shared-types`, `packages/config`) and a uv workspace (`apps/api`, `apps/worker`) sharing one Python venv.
- `docker-compose.yml` defining postgres, redis, minio, mailpit, api, worker, web services; `infrastructure/docker/{api,worker,web}/Dockerfile`; `infrastructure/docker/postgres/init/01-init-roles.sh` creating the migrator/app role split inside the container.
- `infrastructure/scripts/setup-local-db.sh` — idempotent local Postgres role/DB setup for running the API directly (used throughout this milestone's own verification, since Docker image pulls are blocked in this build environment — see **Known limitations**).
- Root `.env.example`, `apps/api/.env.example`, `apps/web/.env.example`.

### Backend (`apps/api`, FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL)
- **Core**: config, async DB engine/session, Argon2id password hashing, opaque-token generation/hashing, structured error responses (`AppError` hierarchy → `{error:{code,message,request_id}}`), request-ID + security-header middleware, structlog JSON logging, Redis-backed rate limiting, SMTP mail sending, session/CSRF cookie helpers.
- **Identity**: register, email verification, login (with lockout after repeated failures), logout, password reset (revokes all sessions), `/auth/session`.
- **Tenancy**: tenant creation (seeds default roles/permissions/wallet/trial subscription in one transaction), tenant switching (re-validates membership server-side), invitations (create/accept/expire, plan-limit-aware), tenant status enforcement.
- **Permissions**: table-driven role→permission grants (not hardcoded role checks), 8 default tenant roles + 4 platform roles, composite-FK-enforced separation between tenant and platform roles (a tenant `Membership` structurally cannot reference a platform role; a `PlatformRoleAssignment` structurally cannot reference a tenant role — both backed by DB constraints/triggers, not just application code).
- **Subscriptions/Entitlements**: plan/feature/plan-feature catalog, tenant subscriptions, add-ons, feature overrides, `EntitlementResolver` combining all three, `max_team_members` limit enforced against active memberships **and** pending invitations.
- **Usage/Credit ledger**: wallet with atomic `SELECT...FOR UPDATE`-based reserve/commit/release, append-only transactions, a Celery-driven reservation-expiry sweep.
- **Audit**: tenant-scoped `AuditLog` + platform-scoped `PlatformAuditLog`, written by every state-changing tenancy/support-access action.
- **Platform admin**: tenant listing, time-boxed/reason-logged/revocable support-access grants (dual-write to both platform and tenant audit logs — support access is visible to the tenant it targets, not a silent backdoor).
- **Row Level Security**: enabled + FORCE'd on every tenant-owned table, policy = tenant match OR platform-bypass GUC; `roles`/`role_permissions` additionally allow reading (never writing) `tenant_id IS NULL` platform-scoped rows.
- **Seed data**: idempotent script populating the permission/role/plan catalog and the fictional "Northstar Digital Solutions Demo" tenant with 5 demo users + 1,000 seeded credits.
- **Worker** (`apps/worker`): Celery app + one real scheduled task (`expire_stale_reservations`, every 5 min) proven end-to-end through a live Redis broker and worker process.

### Frontend (`apps/web`, Next.js 16 App Router + React 19 + Tailwind v4)
- Auth pages: login, register, verify-email, forgot-password, reset-password, invitation-accept.
- Onboarding page (create workspace / switch to an existing one).
- Tenant workspace shell (`(tenant)` route group): Dashboard, Team (invite + pending invitations list), Usage & Billing (wallet + credit history), Audit Log — all backed by real API calls, gracefully degrading (a permission-scoped banner, not a crash) when the caller's role lacks the relevant permission.
- `packages/ui`: Button, TextField, Card, Banner — accessible (labelled inputs, `aria-invalid`/`aria-describedby`, focus-visible rings).
- Session-cache invalidation fixed after login/tenant-create/tenant-switch/invitation-accept (see **Known limitations** for how this was found).
- `proxy.ts` (Next 16's renamed middleware convention) for presence-only protected-route redirects.

### Tests
- **Backend**: 25 pytest tests across auth, tenancy/permissions/entitlements, tenant isolation (including a direct RLS-bypass-attempt test against the raw `gridkeep_app` DB role), credit-wallet atomicity, and platform admin/support-access — run against a real, separate PostgreSQL database (`gridkeep_test`) and a real Redis logical DB, with a genuine in-process SMTP server capturing verification/reset/invitation emails (not mocked).
- **Frontend**: `pnpm lint` (ESLint 9 flat config) and `pnpm typecheck` (`tsc --noEmit`, strict mode) both clean.
- **End-to-end**: a 12-step Playwright script (headless Chromium) drove the actual `next dev` server against the actual `uvicorn` API server through register → verify → login → onboarding → create workspace → dashboard → invite teammate → usage page → audit log → logout → protected-route redirect. All 12 checks pass. This is not scripted against mocks — it is the real stack, and it is what surfaced the session-cache bug described below.

## Milestone 2 completed work

### Connector SDK (`packages/connector-sdk`, new uv workspace member)
- Provider-neutral `BaseConnector` ABC (`estimate_cost`, `search`, `health_check`), `SearchQuery`/`SearchPage`/`BusinessRecord` dataclasses, a connector error taxonomy (`ConnectorAuthError`/`ConnectorQuotaError`/`ConnectorRateLimitError`/`ConnectorTransientError`/`ConnectorPermanentError`), and a string-keyed registry (`connector_sdk.registry.get_connector`).
- `MockConnector` — **clearly labeled fictional data**, deterministically generated from a hash of the query + page number (so the same query always returns the same sample businesses), priced at 1 credit per result. This is the only connector Milestone 2 ships; real provider connectors (Google Places, etc.) are later-milestone work.

### Campaign domain (`apps/api/app/modules/campaigns`, `app/modules/campaign_jobs`)
- `Campaign`, `CampaignFilter`, `CampaignUsageEstimate`, `CampaignEvent` (append-only status-change log), `CampaignError` (append-only per-task error log), `CampaignJob`, `CampaignTask` — RLS-enabled and FORCE'd like every Milestone 1 tenant-owned table; entity count deliberately consolidated from the original architecture's larger list (ADR-0008).
- A 12-status state machine (`draft → estimating → ready → queued → running → {pausing, cancelling, completed, partially_completed, failed}`, `pausing → paused`, `paused → {queued, cancelling}`, `cancelling → cancelled`) with a single writer (`state_machine.transition`) that rejects illegal transitions and records every transition to `CampaignEvent`.
- Services: `create_campaign`, `compute_estimate` (free, no credits reserved), `launch_campaign` (checks the `max_concurrent_campaigns` entitlement server-side, reserves credits via the Milestone 1 two-phase reservation ledger, creates the job + first task), `pause_campaign`, `resume_campaign`, `cancel_campaign` (synchronously finalizes and releases/commits the reservation when cancelling from `paused`, since there's no in-flight task for a worker to observe the cancel on — see `_finalize_cancelled_synchronously`), `delete_campaign`, `get_progress`.
- Full HTTP surface (`/campaigns`, `.../estimate`, `.../launch`, `.../pause`, `.../resume`, `.../cancel`, `.../progress`, `.../events`, `.../errors`) — every route requires a specific permission (`campaigns.view`/`.create`/`.start`/`.pause`/`.cancel`/`.delete`) via the same `require_permission` dependency chain as Milestone 1, tenant context flows entirely server-side (never trusted from the client), never exposes connector credentials to the browser (there are none for the mock connector, and the pattern generalizes).

### Celery task chain (`apps/worker/worker/campaign_tasks.py`)
- One Celery task per page (`run_campaign_task`), chained by having each successful page enqueue the next one — not a single long-running task, so pause/cancel/retry all operate between pages, never mid-page.
- **Idempotent**: `lock_task_for_processing` only transitions a task `pending → running`; a duplicate at-least-once Celery delivery for an already-claimed task is a no-op.
- **Per-tenant concurrency limit**: a Redis-backed TTL'd slot pool (`campaign_jobs/concurrency.py`, 2 slots/tenant) rather than a raw counter, so a crashed worker's held slot self-heals via TTL expiry instead of leaking forever.
- **Retries**: transient/rate-limit connector errors retry with exponential backoff (up to 8 attempts) before permanently failing the task; auth/quota/permanent connector errors fail immediately, no wasted retries.
- **Pause/cancel responsiveness**: the campaign's status is checked both immediately after claiming a task (before any connector call) and immediately after a page succeeds — whichever check first observes `pausing`/`cancelling` finalizes the campaign instead of running/enqueuing another page.
- **Credit reconciliation**: on completion, cancellation, or permanent failure, the reservation taken at launch is committed for the *actual* number of businesses found (never the estimate) or released if none were found — auditable via the same `CreditTransaction` ledger from Milestone 1.
- The API and worker are a strict producer/consumer pair: `apps/api` publishes via a plain Celery client (`app.core.celery_client`) using `send_task` by string name, and cannot import `apps/worker`'s task functions — only the worker depends on the API package, never the reverse.

### Frontend (`apps/web`)
- `/campaigns` — campaign list plus a create-and-estimate form (industry/location/rating/review-count/phone/website filters, result limit), clearly labeled as using the mock connector.
- `/campaigns/[id]` — detail view with estimate/launch/pause/resume/cancel/delete actions gated by campaign status, a live-polling progress panel (2s interval while non-terminal, stops automatically once the campaign reaches a terminal status), an error list, and a full status-change history timeline.
- `packages/ui`'s existing `Button`/`Card`/`Banner`/`TextField` components and the established react-hook-form + zod form pattern were reused as-is — no new UI primitives were needed.

### Tests
- **Backend (`apps/api/tests/test_campaign_engine.py`, 10 tests)**: state-machine illegal-transition rejection, credit reservation on launch, the `max_concurrent_campaigns` entitlement blocking a second concurrent campaign, pause/cancel status-precondition enforcement, the paused-cancel synchronous-reservation-release path, permission enforcement for a read-only role, unknown-connector rejection, and the `lock_task_for_processing`/`acquire_tenant_slot`/`release_tenant_slot` idempotency and concurrency primitives directly.
- **Worker (`apps/worker/tests/test_campaign_tasks.py`, 5 tests, new test package)**: a full multi-page campaign run to completion with correct credit reconciliation, duplicate-task-delivery idempotency, pause stopping the chain between pages with the reservation left open, and cancel both with no progress (full release) and with partial progress (partial commit, partial release) — driving the actual `_run_campaign_task_async` coroutine directly rather than mocking it.
- **Live end-to-end verification** (not part of the checked-in suite, done by hand against the real running stack): a full browser session (Playwright + real Chromium) through register → verify → onboarding → create campaign → estimate → launch → live progress polling → completion, and a separate httpx-based script exercising pause→resume and cancel-with-no-progress/cancel-with-partial-progress against the live API, worker, Postgres, and Redis. This is how the two real bugs below were found — they did not show up in isolated unit-style testing.

## Milestone 3 completed work

### Google Places connector (`packages/connector-sdk/connector_sdk/google_places.py`)
- `GooglePlacesConnector` implements `BaseConnector` against Google's real Places API (New) (`https://places.googleapis.com/v1`) — **Text Search** (the primary path, matching `SearchQuery`'s text-based location filters), **Place Details** and **Nearby Search** (both real, working, callable methods — see ADR-0010 for why neither is on the default `search()` path today), minimal per-call **field masks**, **pagination** via an opaque cursor that carries both Google's own page token and this connector's own running result count (needed because the worker's task chain enforces `result_limit` purely off `SearchPage.has_more`, exactly like `MockConnector`), an **error taxonomy mapping** (auth/permission → `ConnectorAuthError`, rate-limit vs. quota-exhausted 429s distinguished by message content, 5xx/network → `ConnectorTransientError`, malformed-query 400s → `ConnectorPermanentError`, page-token-related 400s → `ConnectorTransientError` since Google's page tokens have a documented short activation delay), an **API-call counter** (`api_calls_made`) for usage measurement, **source attribution** (`source="google_places"`, the real Google place ID, the real Google Maps URL), **business normalization** that never fabricates a missing field (a place missing even its display name falls back to a label built from its own real place ID, never an invented name), and a real **health check**.
- Registered in `connector_sdk.registry` under `"google_places"`, alongside `"mock"` — campaigns can set `source_key: "google_places"` today through the same API surface Milestone 2 built, with no orchestration-layer changes needed.
- Follows the ADR-0009 lesson: `httpx.AsyncClient` is bound to the event loop that creates it, exactly like asyncpg/redis-py, so this connector opens a fresh client per request rather than caching one at instance scope (instances live in the module-level registry, reused across the worker's per-task event loops).

### Tests (`packages/connector-sdk/tests/test_google_places.py`, 22 tests, new test package)
- Mocked-adapter tests (`httpx.MockTransport`, per the milestone's own explicit requirement) covering: successful Text Search normalization, missing-optional-field handling (never fabricated), address-component parsing into region/city/area, pagination across two pages with correct cursor encoding, `result_limit` enforcement even when Google reports more results available, client-side phone/website/review-count filtering, `estimate_cost` making no network call, a missing API key only raising when the connector is actually invoked (not at construction), every mapped error status code (401/403/429×2/500/503), both `INVALID_ARGUMENT` branches (with vs. without a page token), both `health_check` outcomes, and both `get_place_details`/`search_nearby`'s real request construction.

### ⚠️ What was not verified
**No live call was made against the real Google Places API.** No Google Cloud API key was available in this environment. Everything above about Google's actual request/response contract is implemented from Google's published API documentation and tested against mocked HTTP responses shaped to match that documentation — genuine test coverage of this connector's own logic, but not proof that a real call to Google's servers succeeds. See ADR-0010 and **Known limitations** below for what's needed to close this gap, and please read it before pointing a real campaign at this connector.

## Milestone 4 completed work

### Prerequisite fix: real Business persistence (`apps/api/app/modules/businesses`)
Milestone 2's task chain only ever stored discovery results as an opaque per-page JSON blob (`CampaignTask.result_snapshot`) — there was no addressable `Business` row anywhere for Milestone 4's enrichment to attach to. This gap was found and fixed as part of this milestone, not deferred:
- `Business` — one row per real-world business, consolidating six of the original architecture's Business Data Model entities (`BusinessIdentifier`/`Category`/`Location`/`Contact`/`Website`/`SocialProfile`) into columns, plus a `field_provenance` JSONB column recording, per field, its source/source-record/confidence/collected-at (never a fabricated placeholder for a field the source didn't provide). See ADR-0011 for the full reasoning, including why `BusinessSnapshot`/`BusinessMergeHistory` are deliberately deferred to Milestone 5.
- `BusinessSourceRecord` — one row per (tenant, source, source-native-id) discovery event, uniquely keyed so re-discovering the same business (e.g. the same Google place ID found by a second campaign) updates the existing record and resolves to the same `Business` row rather than creating a duplicate.
- `upsert_business_from_discovery` (`app.modules.businesses.repositories`) is now called from `worker.campaign_tasks` for every discovered business, alongside (not replacing) the existing `result_snapshot` audit copy.
- `Business.email` is structurally enrichment-only: discovery's own field list (`_DISCOVERY_FIELDS`) excludes it, since neither `MockConnector` nor `GooglePlacesConnector` return an email at all — there is no code path by which discovery could fabricate one.
- New endpoints: `GET /businesses/{id}`, `GET /campaigns/{id}/businesses` (permission `leads.view`).

### Safe website crawler (`apps/worker/worker/crawler`)
- `safety.safe_get` — the one function every crawl request goes through. Scheme allowlist (http/https only); resolve-and-validate always runs first against real DNS, rejecting private/loopback/link-local (covers cloud metadata endpoints)/multicast/reserved/unspecified addresses for both IPv4 and IPv6; connects to the literal validated IP (not by hostname) to defend against DNS rebinding, except when an environment proxy is configured, in which case it connects by hostname through that trusted proxy (an HTTP CONNECT tunnel needs the real hostname — this sandbox's own mandatory egress proxy rejects raw-IP tunnels); redirects are followed manually, one hop at a time, with the same checks re-applied to every target, capped at 5 hops; response body is streamed with a hard 5 MB cap enforced per chunk, not after full download; strict connect/read timeouts. See ADR-0012 for the full design and its proxy-aware tradeoff.
- `robots.RobotsChecker` — fetches and parses `robots.txt` through the same `safe_get`, defaulting to "everything allowed" if it's unreachable.
- `fetcher.crawl_site` — a bounded, same-domain crawl of a fixed candidate page set (homepage, `/contact`, `/contact-us`, `/about`, `/about-us`, `/booking`, `/reservations`, `/order`, `/menu`, `/services`), capped at 6 pages, respecting robots.txt and a per-domain minimum request interval (1.5s, or robots.txt's own `Crawl-delay` if longer). Scheme/reachability is probed via `/robots.txt` specifically (not the homepage), so the crawler's very first request to a site is never a real content page fetched before robots rules are loaded, and the homepage isn't fetched twice.
- `detectors` — pure functions over one page's parsed HTML (BeautifulSoup): contact email (mailto: links preferred over regex-matched plain text), phone (tel: links), WhatsApp links, booking-platform links (Calendly/OpenTable/Resy/Square Appointments/Acuity/Setmore), ordering-platform links (Uber Eats/DoorDash/Grubhub/Toast/ChowNow/Square Online), Facebook/Instagram/LinkedIn business links, missing mobile viewport, weak page metadata (short title / no description), outdated copyright year, missing contact form. Every detector reports only what it genuinely found on that specific page — never an inferred or fabricated value.

### Enrichment pipeline (`apps/worker/worker/enrichment_tasks.py`, `apps/api/app/modules/enrichment`)
- `BusinessEnrichment` (one row per crawl run: status, pages crawled, timestamps, error message) and `EnrichmentEvidence` (one row per detector finding: detector type, exact source URL, structured result, confidence, collection timestamp, supporting snippet) — satisfying the architecture's explicit evidence-storage requirement.
- `run_business_enrichment` (Celery task, its own `queue.enrichment` queue, separate from `queue.search` so a backlog of one never starves the other) crawls the business's website, runs every detector against every crawled page, and persists the result. Whole-crawl "missing X" signals (`missing_whatsapp`, `missing_online_booking`, `missing_online_ordering`, `missing_contact_method`) are computed here — not by any single detector — since they're claims about the *entire* crawl, and are only ever recorded when the site was genuinely reachable (an unreachable site gets `website_unavailable` instead of five claims about content nobody saw).
- The single highest-confidence `contact_email` finding across the whole crawl becomes `Business.email`, with its own provenance entry (`source: "enrichment"`) — the only place this field is ever written.
- New endpoints: `POST /businesses/{id}/enrich` (permission `leads.enrich`, new permission granted to Administrator/Campaign Manager/Sales Manager), `GET /businesses/{id}/enrichment`, `GET /businesses/{id}/evidence`.
- Follows the ADR-0009 per-task event-loop isolation rule a third time (after `GooglePlacesConnector` and now this crawler) — no cached `httpx.AsyncClient` at module/instance scope anywhere in the crawler or the task.

### Tests
- **`apps/worker/tests/test_crawler_detectors.py`** (20 tests) — pure-function tests against static HTML fixtures, no network.
- **`apps/worker/tests/test_crawler_safety.py`** (13 tests) — SSRF-blocking tests use **real DNS resolution**, no mocking, against real blocked targets (`127.0.0.1`, `localhost`, the `169.254.169.254` metadata address, a private `10.x` address, `file://`, `ftp://`); fetch-mechanics tests (redirects, redirect-to-unsafe-target blocking, size cap, status handling) use an injected `httpx.MockTransport` against `example.com` used purely as a DNS target.
- **`apps/worker/tests/test_crawler_fetcher.py`** (8 tests) — `crawl_site` orchestration: candidate-path fetching, page-count cap, robots.txt disallow enforcement, missing-robots.txt default-allow, unreachable-host handling, https→http fallback with `ssl_failure` flagging, no-duplicate-URL-visits.
- **`apps/worker/tests/test_enrichment_tasks.py`** (5 tests) — the full pipeline driven directly against real Postgres with a mocked crawl transport: successful run persisting evidence and setting `Business.email`, no-website immediate failure, unreachable-site producing only `website_unavailable`, `missing_contact_method` firing correctly when genuinely absent, duplicate-delivery no-op for a non-pending enrichment.
- **`apps/worker/tests/test_campaign_tasks.py`** (now 6 tests) — two new tests added: a completed campaign persists individual, deduplicated `Business` rows (not just JSON blobs), and re-discovering the same businesses via a second campaign updates the existing rows rather than duplicating them.
- A genuine, real-DNS test of `safe_get` blocking every SSRF target class was also run ad hoc against live targets before being checked into the suite above, to confirm the resolver-based defense works against real network resolution, not just its own mocked assumptions about `ipaddress` behavior.
- While writing `test_crawler_fetcher.py`, a real duplicate-request bug was found and fixed: `_probe_scheme` originally probed scheme/reachability by fetching the homepage (`/`), which meant the homepage was fetched twice per crawl (once to probe, once as the first real candidate page) and, worse, fetched once *before* robots.txt was even loaded — ignoring a potential `Disallow: /`. Fixed by probing via `/robots.txt` instead, which is always exempt from robots-compliance rules by definition and settles both problems at once.

### ⚠️ What was not verified
**No live crawl was made against a real external website.** This sandbox's egress policy blocks general internet access (confirmed directly — both a raw request to a real domain and this crawler's own direct-IP-connect strategy were rejected by the proxy with policy-level 403s, the same class of restriction Milestone 3 hit for the Google Places API). SSRF-blocking is verified against real DNS resolution; fetch mechanics, crawl orchestration, and the full enrichment pipeline are verified against a real Postgres database with a mocked HTTP transport. See ADR-0012 and **Known limitations** for what's needed to close this gap before relying on this crawler against real business websites in production.

## Milestone 5 completed work

### Deduplication (`apps/api/app/modules/businesses/dedup.py`, `normalize.py`)
- `Business.merged_into_id` (new, self-referential composite FK, same-tenant-enforced), `BusinessDuplicateCandidate`, `BusinessMergeHistory` — the deferred-from-Milestone-4 entities ADR-0011 explicitly reserved room for.
- **Matching**, checked in the architecture's exact priority order (identifier → domain → phone → name+address → conservative fuzzy), stopping at the first tier with a hit: `google_place_id` equality, `canonical_domain` equality, a new indexed `normalized_phone` column equality, exact name+address match (same-city-scoped), and a stdlib-`difflib`-based fuzzy name similarity check (also same-city-scoped, `SequenceMatcher.ratio() >= 0.88`).
- **One confidence threshold** (`AUTO_MERGE_CONFIDENCE_THRESHOLD = 0.85`) decides auto-merge vs. human review — all four exact tiers score above it (1.00/0.95/0.90/0.88); fuzzy matching's confidence is deliberately capped (`similarity × 0.75`, max 0.75) so it can *never* reach the threshold, structurally guaranteeing "never silently merge uncertain records."
- **Merges are soft, field-combining, and precisely reversible**: the losing `Business` row is never deleted, only marked `merged_into_id`; its source records/enrichment/evidence are reassigned onto the winner with the exact moved row IDs recorded in `BusinessMergeHistory.moved_records`; fields the loser knows with strictly higher confidence fill gaps or replace lower-confidence values on the winner (reusing Milestone 4's `field_provenance` "never overwrite higher-confidence data silently" rule), with the winner's pre-merge value recorded in `field_changes` for exact undo.
- `BusinessDuplicateCandidate` rows are deduplicated by pair (smaller UUID always in slot `a`), never re-proposed once rejected, and upgraded in place if a stronger match type is found for the same still-pending pair later.
- Runs **synchronously, inline** in `worker.campaign_tasks` right after each discovery upsert — deliberately not a background job (unlike enrichment's real network crawl, matching here is cheap indexed-equality/bounded-scan work against data already in Postgres).
- New endpoints: `GET /businesses/{id}/duplicates`, `GET /businesses/{id}/merge-history`, `GET /duplicate-candidates` (tenant-wide, filterable by status), `POST /duplicate-candidates/{id}/confirm`, `POST /duplicate-candidates/{id}/reject`, `POST /merges/{id}/undo` — the review/merge/undo actions reuse the pre-existing `leads.edit` permission.

### Lead scoring and intelligence (`apps/api/app/modules/leads/`)
- `Lead` (thin wrapper around a canonical Business, `status` defaulting to `"new"` — the full status workflow is Milestone 6's job), `LeadScore` (append-only/versioned, `algorithm_version = "v1"`, a `factors` JSONB breakdown), `LeadOpportunity`, `LeadRecommendation`.
- **The scoring algorithm is the architecture's own worked example**, replicated almost exactly: 7 factors summing to 100 (category+location match /20, business status+reviews /15, contact availability /15, commercial opportunity /20, WhatsApp presence /10, enrichment confidence /10, freshness /10), each with a real-value-derived explanation string and an evidence dict — never an unexplained number.
- **Opportunity detection never invents a problem** — every opportunity is a direct 1:1 read of an `EnrichmentEvidence` row, a direct `Business` field observation (`no_website`, `low_review_activity`), or a whole-crawl absence check (`missing_social_links`), each with an `evidence_reference` pointing at exactly what was observed.
- **Recommended services are a data-driven rule table** (`OPPORTUNITY_RECOMMENDATIONS`), keyed by generic opportunity types, not restaurant-specific branches — satisfying the architecture's explicit "do not hardcode restaurants into core architecture" requirement directly.
- Re-scoring **replaces** stale opportunities/recommendations (upsert-by-type, delete what's no longer detected) rather than accumulating duplicates across runs, while a lead's `LeadScore` history is preserved (a new row every time, never overwritten).
- Runs **synchronously, in-request** (`POST /businesses/{id}/score`) — pure computation over already-persisted data, no network call, so no background job is warranted (new permission `leads.score`).

### Tests
- **`apps/api/tests/test_deduplication.py`** (20 tests) — every match tier's true-positive case (auto-merges correctly), the architecture's explicitly required false-positive guard (a conservative fuzzy match creates a candidate, never auto-merges) and false-negative guards (dissimilar names in the same city produce no match; matching names in *different* cities produce no match, proving the city-scoping works as intended), cross-tenant isolation, full merge mechanics (field combination by confidence, source-record/enrichment/evidence reassignment), undo-merge (exact reversal, double-undo rejected), and the candidate review workflow (confirm performs the merge, reject leaves both distinct and is never re-proposed, reviewing an already-reviewed candidate is rejected).
- **`apps/api/tests/test_lead_scoring.py`** (9 tests) — no-website opportunity detection, score bounds/factor-sum invariants, category+location matching with and without an originating campaign filter, evidence-derived missing-signal opportunities (and that a *positive* signal like `contact_email` never itself becomes an opportunity), low-review-activity detection, re-scoring reusing the same `Lead` while appending score history, re-scoring replacing (not accumulating) stale opportunities, and recommendation confidence correctly averaging across its supporting opportunities.
- **`apps/worker/tests/test_campaign_tasks.py`** — two Milestone 4 tests updated (not weakened): a real data collision was found by the suite itself once dedup went live (the mock connector's limited 10×10 name-word-pool can, across 45 draws, produce two "different" fake businesses sharing the same generated name/domain — a genuine domain match, correctly auto-merged), so the hardcoded "exactly 45 rows" assertions were replaced with the real invariants ("no duplicate rows," "no two canonical businesses share a domain," "re-discovery never creates new rows") — see ADR-0013's Consequences section for the full account.
- Full monorepo verification: 64/64 (api) + 52/52 (worker) + 22/22 (connector-sdk) = 138/138 passing; ruff and mypy clean across all three packages; `alembic check` reports no drift.

### ⚠️ What was not verified
Nothing new here — unlike Milestones 3 and 4, this milestone has no external-network or third-party-API dependency to flag. Every code path (matching, merging, undo, scoring, opportunity detection, recommendation mapping) is pure computation and database logic, and all of it is exercised directly against a real, separate Postgres test database — there is no mocked-vs-live gap to carry forward.

## Milestone 6 completed work

### Prerequisite fix: `GET /tenants/members` (`apps/api/app/modules/tenancy`)
Assignment needs a picker of who a lead can be assigned to, and no endpoint listed a tenant's active members (Milestone 1's team page only ever needed pending *invitations*). Added `list_active_members_for_tenant` (joins `Membership`+`User`+`Role`) and `GET /tenants/members` (permission `users.view`, already in the Milestone 1 catalog).

### Deduplication fix: `Lead` now follows its `Business` on merge (`apps/api/app/modules/businesses/dedup.py`)
Milestone 5's `merge_businesses` predates `Lead` and never accounted for it — building the lead list on top of merge-aware `Business` data surfaced this directly. Fixed: if only the losing business has a `Lead`, it's reassigned onto the winner (`Lead.business_id = winner.id`) — since every child of a `Lead` keys off `lead_id`, not `business_id`, moving the one row carries its entire history (scores, opportunities, notes, tags, status/assignment history) along for free, and the move is recorded in `BusinessMergeHistory.moved_records["lead"]` for the same precise `undo_merge` every other moved record type gets. If *both* businesses already have independent `Lead` rows, the loser's is deliberately left untouched (never deleted or silently blended) and simply excluded from the lead list — reconciling two sets of independently-authored history is a real, deferred feature, not a merge side effect. See ADR-0014.

### Lead list, detail, and workspace actions (`apps/api/app/modules/leads`)
- **`GET /leads`** — server-side pagination (`page`/`page_size`, capped at 100), server-side sorting (name/score/created_at/status/rating/review_count, either direction), and advanced filtering (status, tag, category, city/country/area, assigned/unassigned, min/max score, opportunity type, free-text search) — one query joining `Business` with a window-function subquery for each lead's latest `LeadScore.total_score`, filtered to canonical (non-merged-away) businesses only.
- **`GET /leads/{id}`** — the full lead detail: business info, latest score breakdown, opportunities, recommendations, notes, tags, status history, assignment history, and any duplicate candidates involving the underlying business.
- **Status changes** (`POST /leads/{id}/status`) — validated against the architecture's 10-value status list, but deliberately **no transition state machine** (unlike campaigns' explicit graph) — real sales workflows are non-linear, and the architecture specifies no transition rules for leads. Every change is recorded in `LeadStatusHistory` regardless of direction. See ADR-0014.
- **Assignment** (`POST /leads/{id}/assign`, `.../unassign`) — `Lead.assigned_to_user_id` is the fast current-state column; `LeadAssignment` is an append-only history (reassigning to a different user closes the open entry and opens a new one; reassigning to the same user is a no-op).
- **Notes** (`POST`/`GET /leads/{id}/notes`) and **tags** (`POST /leads/{id}/tags`, `DELETE .../tags/{tag}`) — tags are plain, lowercased, deduplicated strings (no separate vocabulary table — not asked for).
- **Bulk actions** (`POST /leads/bulk/status`, `.../assign`, `.../tags`) — apply one action to many leads in one transaction, each permission-checked exactly like its single-lead counterpart.
- **Saved views** (`GET`/`POST /saved-views`, `DELETE /saved-views/{id}`) — a named, reusable filter/sort state, tenant-shared, deletable by its creator or anyone with `leads.edit`.
- No new permissions beyond what Milestones 4-5 already added — assignment/status/tags/notes/saved-views all reuse the Milestone 1 catalog's already-forward-looking `leads.assign`/`leads.change_status`/`leads.edit`/`leads.view`.

### A real routing bug found and fixed: bulk routes shadowed by `/{lead_id}`
`POST /leads/bulk/status` and `POST /leads/{lead_id}/status` are both two-segment POST paths — Starlette matches routes in registration order, and `{lead_id}` matches any string including the literal `"bulk"`. Had the `/{lead_id}` routes been registered first, `/leads/bulk/status` would have 422'd trying to parse `"bulk"` as a UUID, never reaching the bulk handler. Fixed by registering every literal-segment route before any `/{lead_id}/...` route, with an explanatory comment in `routes.py`, and regression-tested with an HTTP-level test that specifically distinguishes "routed correctly, lead not found (404)" from "routed to the wrong handler (422)".

### Frontend (`apps/web`)
- `/leads` — filterable/sortable/paginated table with bulk selection (select-all-on-page, per-row checkboxes), a bulk action bar (change status, add tag) that appears when leads are selected, and saved views (apply, or save the current filter state under a name).
- `/leads/[id]` — business info (phone/email/website/rating/address), status control + history, assignment control + history, score breakdown (every factor with its explanation and progress bar), opportunities and recommendations, duplicate candidates, tags (add/remove), and notes (add + chronological list).
- Added to the tenant nav (`TenantShell.tsx`).

### Tests
- **`apps/api/tests/test_lead_workspace.py`** (25 tests) — list pagination/sorting/filtering (status, tag, score range, merged-business exclusion), status changes (history recording, no-op same-status, invalid-value rejection, non-linear transitions), assignment (history recording, reassignment closing the prior open entry), notes (add/list, empty-body rejection), tags (idempotent case-insensitive add, remove), bulk actions (status/assign/tag applied to every lead in one call), saved views (create/list/delete, creator-only vs. `leads.edit`-override ownership enforcement), and the `dedup.merge_businesses` Lead-reassignment extension (moves when unambiguous, leaves untouched when both sides already have a Lead, undo reverses precisely).
- **`apps/api/tests/test_lead_workspace_api.py`** (8 tests) — HTTP-level: the bulk-route-ordering fix (a bulk request against a random lead ID reaches the bulk handler and 404s, rather than 422'ing on UUID parsing), permission enforcement (a Read-Only Viewer can list/view but is denied on every mutating action), `GET /tenants/members`, and saved views over HTTP.
- **Live end-to-end verification** (not part of the checked-in suite, done by hand against the real running stack): registered a real user, launched a real mock campaign, drove it to completion via a live Celery worker, scored 15 discovered businesses into leads via the real API, then used a live Chromium browser (Playwright) against the actual `next dev` server to load `/leads`, filter by tag, select multiple leads for the bulk-action bar, open a lead's detail page, change its status, assign it, add a tag, and add a note — every mutation genuinely persisted and re-rendered correctly on reload. This is what caught the missing business-info section on the detail page (the initial `LeadDetailResponse` only exposed `business_id`, not the business's own contact fields) before it shipped.
- Full monorepo verification: 97/97 (api) + 52/52 (worker) + 22/22 (connector-sdk) = 171/171 passing; ruff and mypy clean across all three Python packages; `alembic check` reports no drift; frontend `pnpm lint` and `pnpm typecheck` both clean.

## Milestone 7 completed work

### Object storage client (`apps/api/app/core/storage.py`)
Thin `boto3` wrapper (already a declared dependency since Milestone 1, unused until now): tenant-prefixed object keys, `upload_bytes` (called only from the Celery task, never an API request handler), and `presigned_download_url` (regenerated fresh per download request, never stored — see ADR-0015). Bucket creation is deliberately not the app's responsibility; a missing bucket surfaces as a clearly-failed export, not a silently auto-created one.

### `Export`/`ExportError` (`apps/api/app/modules/exports`)
`Export` is both the background-job status tracker (`pending`→`processing`→`completed`/`failed`) and its own audit record (requester, selection, timestamps, row/error counts, object key) — no dependency on the generic `AuditLog` table, consistent with every other campaign/lead-domain entity. `selection` persists a *replayable spec* (explicit `lead_ids`, or a `filters` object shaped exactly like `leads.repositories.LeadListFilters`), re-resolved against current data by the Celery task at execution time rather than a frozen snapshot. `ExportError` records one row per lead that failed to resolve (deleted, or merged away since the export was requested) — this is what makes "partial completion" real: one bad lead never fails the whole export.

### XLSX/CSV generation (`apps/api/app/modules/exports/data.py`, `workbook.py`)
- `data.py` assembles the architecture's exact 31-column schema per lead, batching every lookup (scores, opportunities, recommendations, assignment, notes, source provenance, social-profile evidence) across the whole export rather than per-row — the same "batch, don't N+1" discipline Milestone 6's `get_tags_for_leads` established, extended with new batched functions in `leads`/`businesses`/`enrichment`/`identity`/`campaigns` repositories.
- `workbook.py` builds a **streaming** (`Workbook(write_only=True)`) four-sheet XLSX — Leads (styled headers, frozen header row, autofilter, wrapped long-text cells, hyperlinked URL columns, per-column widths), Campaign Summary (real per-campaign counts of this export's rows, not a template), Scoring Rules (the live `OPPORTUNITY_RECOMMENDATIONS` table + `LEAD_STATUSES` vocabulary, read directly from `leads.scoring` so it can never drift out of sync), and Errors (every unresolved lead id with a specific message) — and a matching CSV. **Formula-injection protection** (`sanitize_cell_value`) is one function applied to every string cell in both formats: a leading `=`/`+`/`-`/`@`/tab/CR gets an apostrophe prefix, the standard OWASP-recommended defense.
- Two columns — Opening Hours, Verification Status — are always empty: neither has a real data source anywhere in this codebase (no connector field, no detector, `LeadVerification` still unbuilt), so they stay present in the spec's column order but never fabricated. See ADR-0015.
- A real interop bug found and fixed: write-only XLSX worksheets only serialize `freeze_panes` if it's set *before* the first row is appended — setting it afterwards (the natural order in non-streaming openpyxl code) is silently dropped on save. Fixed by moving every `freeze_panes` assignment to immediately after sheet creation; regression-tested by reopening a generated workbook and asserting it round-trips.

### Celery export task (`apps/worker/worker/export_tasks.py`, `queue.export`)
`run_export` mirrors `worker.enrichment_tasks.run_business_enrichment`'s shape exactly: two-phase tenant lookup (bypass GUC, then real tenant context), duplicate-delivery no-op guard, bounded retry with exponential backoff, clean `failed` finalization after retries are exhausted. Resolves the export's persisted selection, assembles rows, builds the file, uploads it, and records the result — with per-lead resolution failures becoming `ExportError` rows rather than failing the whole job.

### API routes (`POST`/`GET /exports`, `GET /exports/{id}`, `GET /exports/{id}/errors`, `GET /exports/{id}/download`)
`leads.export` (already in the Milestone 1 catalog, unused until now) gates creating an export; `exports.view` (also already present) gates every read. Download returns a JSON `{url, expires_in_seconds, filename}` rather than proxying the file — the browser navigates directly to the signed object-storage URL.

### Frontend (`apps/web`)
- `/exports` — a list of the tenant's exports with live status/row-count/error-count/size columns, polling every 3s while anything is still `pending`/`processing`, and a Download button once an export completes (fetches a fresh signed URL and navigates the browser to it directly — no proxy through the Next.js app).
- `/leads` gained an export-format selector (XLSX/CSV), an "Export selected" action in the bulk action bar (uses the current checkbox selection as explicit `lead_ids`), and an "Export all matching filters" action in the filter card (replays the current filter state as the export's `filters`) — both `POST /exports` and surface a success banner linking to `/exports`.
- Added to the tenant nav (`TenantShell.tsx`).

### Tests
- **`apps/worker/tests/test_export_tasks.py`** (4 tests) — the full pipeline against real Postgres and a real (moto-backed) S3 server: an XLSX export that reopens and validates the generated workbook (sheet names, header row, real cell values including formula-injection-protected business names, freeze panes, campaign summary counts, scoring rules content — the architecture's explicit "workbook validation tests" requirement), a CSV export's formula-injection protection, partial completion (an unresolvable lead id becomes an `ExportError` while the export still completes), and the duplicate-delivery no-op guard.
- **`apps/api/tests/test_exports.py`** (7 tests) — selection resolution (`lead_ids` mode and `filters`-replay mode, the latter proven to use the exact same filtering `list_leads` itself uses), request persistence, and download-URL gating (`ConflictError` before completion, a real signed URL once completed) — kept fast and S3-independent by monkeypatching `presigned_download_url` (the URL-signing logic itself is exercised for real in the worker test).
- **`apps/api/tests/test_exports_api.py`** (7 tests) — HTTP-level: permission enforcement (`leads.export` for create, `exports.view` for list/get; a Sales Representative is denied both, an Analyst is allowed both), request validation (invalid format, mutually-exclusive `lead_ids`+`filters`), and download-before-completion returning 409.
- **Live end-to-end verification**: no MinIO binary is installable in this sandbox (no Docker daemon; `dl.min.io` blocked by the egress proxy) — `moto`'s `ThreadedMotoServer` (a real local HTTP server implementing genuine S3 API semantics, not a mock at the `boto3` layer) stood in, both for the automated test suite and for a full manual pass: registered a user, verified email via a live SMTP capture, created a tenant, launched a real mock-connector campaign to completion via a live Celery worker, scored the 15 discovered businesses into leads via the real API, requested a bulk-selected XLSX export and a filters-based CSV export, watched both complete via the real Celery worker, fetched the real presigned download URLs and confirmed the files' actual byte content (reopened the XLSX with openpyxl; confirmed real, evidence-derived data in every column), and drove the actual `/leads` bulk-selection-to-export flow and the `/exports` list/download UI in a live headless-Chromium (Playwright) browser against the real `next dev`/`uvicorn` servers.
- Full monorepo verification: 111/111 (api) + 56/56 (worker) + 22/22 (connector-sdk) = 189/189 passing; ruff and mypy clean across all three Python packages; `alembic check` reports no drift; frontend `pnpm lint`, `pnpm typecheck`, and `next build` all clean.

## Acceptance criteria (from the approved architecture)

| Criterion | Status |
|---|---|
| Project starts locally | ✅ Backend/worker verified directly; full Docker Compose stack not verified in this build environment (see limitations) |
| Migrations run | ✅ Verified from a clean database, twice |
| Seed data runs | ✅ Verified, and idempotent (re-run produces no duplicates) |
| Registration works | ✅ Backend tests + live Playwright run |
| Login and logout work | ✅ Backend tests + live Playwright run |
| Email verification flow works | ✅ Backend tests + live Playwright run (real SMTP capture) |
| Password-reset flow works | ✅ Backend tests (session revocation verified) |
| Invitations work | ✅ Backend tests + live Playwright run |
| Tenant switching works | ✅ Backend tests |
| Role enforcement works | ✅ Backend tests (permission-denied paths verified, not just happy path) |
| Entitlements work | ✅ Backend tests (`max_team_members` and `max_concurrent_campaigns` limits both verified) |
| Credit transactions work | ✅ Backend tests + a live Celery/Redis dispatch of the expiry sweep and the full campaign reserve/commit/release cycle |
| Tenant isolation tests pass | ✅ Including a raw-DB-role RLS bypass attempt |
| Platform roles remain separated | ✅ DB-level composite FK + trigger, not just app code |
| Audit records are created | ✅ Backend tests + live Playwright run |
| Campaigns can be created, filtered, estimated | ✅ Backend + worker tests, live Playwright run |
| Campaigns launch and reserve credits server-side | ✅ Backend tests, live E2E |
| Background job processing works (page fan-out) | ✅ Worker tests, live Celery/Redis dispatch to completion |
| Pause/resume/cancel all work, including mid-run | ✅ Worker tests + live httpx E2E for both zero-progress and partial-progress cancel |
| Task retries and idempotency work | ✅ Worker tests (duplicate delivery no-op); retry backoff logic implemented, exercised implicitly (no connector-error injection test yet — see unresolved risks) |
| Per-tenant concurrency limits enforced | ✅ Backend tests (slot exhaustion/release directly) |
| Every score/estimate is explainable | ✅ `EstimateResponse` exposes `estimated_credits`/`estimated_results`/`calculated_at`; `LeadScore.factors` exposes per-factor score/max/explanation/evidence — see Milestone 5 below |
| Backend tests pass | ✅ 111/111 (api) + 56/56 (worker) + 22/22 (connector-sdk) = 189/189 |
| Frontend lint passes | ✅ |
| Frontend type checking passes | ✅ |
| Production builds pass | ✅ `next build` succeeds; API/worker have no separate "build" step (Python) |
| Google Places: Text Search, Place Details, field masks, pagination | ✅ Implemented against Google's documented contract; mocked-adapter tests only — **not verified live** (see above) |
| Google Places: quota management, API usage measurement | ✅ Error-taxonomy mapping for quota/rate-limit responses; `api_calls_made` counter — not exercised against real quota behavior |
| Google Places: source attribution, business normalization | ✅ Mocked tests verify no fabricated fields; real-data shape not confirmed live |
| Google Places: provider health checks, mocked adapter tests | ✅ `health_check()` implemented; 22 mocked-adapter tests, all passing |
| Website enrichment: safe crawler, SSRF protection, robots handling | ✅ Real-DNS-verified SSRF blocking (loopback/private/link-local/metadata addresses, disallowed schemes); robots.txt respected, defaulting to allow when unreachable |
| Website enrichment: rate limiting, page limits | ✅ Per-domain minimum request interval (or robots.txt's `Crawl-delay` if longer); hard 6-page-per-site cap; hard 5 MB response-size cap |
| Website enrichment: contact/WhatsApp/booking/ordering/social extraction | ✅ Detector tests against static HTML fixtures; mocked-transport pipeline tests confirm end-to-end extraction into `EnrichmentEvidence` and `Business.email` |
| Website enrichment: technical opportunity detection | ✅ Missing mobile viewport, weak page metadata, outdated copyright year, missing contact form/method/booking/ordering/WhatsApp — all detector-tested |
| Website enrichment: evidence storage | ✅ `EnrichmentEvidence` stores source URL, detector type, structured result, confidence, collection timestamp, supporting snippet per the architecture's exact requirement |
| Website enrichment: live crawl against a real external website | ⚠️ **Not verified** — this sandbox's egress policy blocks general internet access (same class of gap as Milestone 3's Google API key) — see ADR-0012 |
| Deduplication: identifier/domain/phone/address matching | ✅ Each tier's true-positive case tested against real Postgres; all auto-merge above the 0.85 confidence threshold |
| Deduplication: conservative fuzzy matching | ✅ Never auto-merges (confidence capped below the auto-merge threshold by construction); tested |
| Deduplication: duplicate candidates, merge history, undo merge | ✅ Candidates created for every below-threshold match; every merge reversible via recorded `moved_records`/`field_changes`; tested (including double-undo rejection) |
| Deduplication: false-positive/false-negative test scenarios | ✅ Explicitly tested — see `test_deduplication.py` in the Milestone 5 section below |
| Lead scoring: explainable, versioned scoring engine | ✅ 7-factor/100-point algorithm (`algorithm_version="v1"`), append-only history, every factor carries an explanation + evidence |
| Lead scoring: confidence scoring | ✅ Every match/opportunity/recommendation carries a real, evidence-derived confidence value |
| Lead scoring: opportunity detection, recommended services | ✅ Evidence-based only (never fabricated); data-driven, industry-neutral recommendation rule table |
| Lead scoring: scoring explanations | ✅ `LeadScore.factors` — plain-language explanation + evidence dict per factor |
| Lead workspace: lead list, filtering, sorting, pagination | ✅ Server-side on all three; tested + live-verified in a real browser |
| Lead workspace: lead detail | ✅ Business info, score breakdown, opportunities/recommendations, duplicate candidates, notes, tags, status/assignment history — tested + live-verified |
| Lead workspace: assignments, notes, tags, statuses | ✅ All four implemented with audit trails (assignment/status history); tested + live-verified with real mutations persisting and re-rendering |
| Lead workspace: bulk actions | ✅ Bulk status change, bulk assign, bulk tag — tested + live-verified (bulk-route-ordering bug found and fixed, see ADR-0014) |
| Lead workspace: saved views | ✅ Create/list/delete with creator-or-`leads.edit` ownership enforcement; tested + live-verified |
| Lead workspace: duplicate review | ✅ Surfaced on lead detail (candidates list); confirm/reject/undo endpoints already existed from Milestone 5 |
| Lead workspace: permission-aware interface | ✅ Every mutating action gated by a specific permission; a Read-Only Viewer role explicitly tested to be denied every mutation while retaining view access |
| Exports: XLSX exports, CSV exports | ✅ Both formats, sharing one row-assembly layer and one formula-injection-sanitization function; tested (including workbook-reopen validation) + live-verified |
| Exports: export templates (Leads/Campaign Summary/Scoring Rules/Errors sheets) | ✅ All four sheets real, not placeholders — Campaign Summary and Scoring Rules read live data, Errors lists real per-lead failures |
| Exports: background export jobs | ✅ Celery task on its own `queue.export`, streaming XLSX generation so memory stays bounded regardless of export size |
| Exports: object storage, signed URLs, expiry | ✅ Tenant-prefixed S3 keys; presigned URL regenerated fresh (15-minute TTL) per download request rather than stored |
| Exports: export audit records, status tracking | ✅ `Export` row is both — status lifecycle (`pending`→`processing`→`completed`/`failed`) plus requester/selection/counts/timestamps, the same "entity's own row is the audit trail" pattern as `CampaignEvent`/`LeadStatusHistory` |
| Exports: workbook validation tests | ✅ `apps/worker/tests/test_export_tasks.py` reopens the generated XLSX with openpyxl and asserts real structure/content, not just that generation didn't throw |
| Exports: CSV/formula-injection protection | ✅ One sanitization function applied uniformly to every string cell in both XLSX and CSV; tested and live-verified (including the expected international-phone-number false positive, documented in ADR-0015) |

## Architecture decisions
See `docs/adr/0001` through `0015`. Summary: shared-schema+RLS multi-tenancy, server-side sessions, `uv`/`pnpm` tooling, campaign-level credit-reservation granularity, MFA scaffolded only, no billing provider selected yet, a documented RLS ordering rule + `platform_bypass` escape-hatch pattern (0007), campaign entity consolidation vs. the original architecture's larger entity list (0008), a documented per-task event-loop isolation rule for the worker's async DB/Redis clients (0009), the Google Places connector's design plus its explicit live-verification gap (0010), the Business entity consolidation and the Milestone 2 persistence gap it fixes (0011), the SSRF-safe crawler's design plus its own explicit live-verification gap (0012), the deduplication engine's confidence-threshold design plus the explainable lead-scoring algorithm (0013), the Lead Workspace's design — no lead-status state machine, assignment/tag/saved-view design, the dedup-merge Lead-reassignment fix, and the bulk-route-ordering fix (0014), and the Exports design — the `Export` row as its own audit/status record, replayable (not frozen) selection, signed-URL-per-request storage, streaming XLSX generation, uniform formula-injection protection, and the never-fabricated Opening Hours/Verification Status columns (0015).

## Known limitations

1. **Docker Compose stack not verified end-to-end in this build environment.** This session's outbound network egress policy blocks Docker Hub image pulls (`production.cloudfront.docker.com` returns a 403 policy denial), so `docker compose up` could not be run here. All verification instead ran the same services natively: PostgreSQL 16 and Redis were already installed in this sandbox and used directly; the FastAPI app, Celery worker, and Next.js dev server were run directly via `uv run` / `pnpm dev`. The `docker-compose.yml` and Dockerfiles are believed correct (they mirror the exact configuration verified natively) but **you should run `docker compose up` yourself before relying on it** — that is the one meaningful gap between "verified" and "should work."
2. **MFA is scaffolded, not enrollable** (ADR-0005) — by design, per your approval.
3. **No billing provider integration** (ADR-0006) — by design, per your approval; plans/credits are seed data today.
4. **RLS discipline is manual today.** The ordering rule in ADR-0007 (`set_tenant_context` before any RLS-protected query) is not enforced by a linter or CI check — a future service function could reintroduce the same class of bug if the rule isn't followed. Milestone 2's worker code hit the exact same class of bug again (`worker.campaign_tasks._run_campaign_task_async`'s first lookup needed `set_platform_bypass` before its first read, same as ADR-0007's examples) before being fixed — this remains a manual-discipline risk, not an automated one.
5. **No CI/CD pipeline yet.** GitHub Actions workflows (lint/test/build/scan on push) have not been created.
6. **Object storage is now exercised (Milestone 7), but never against a real MinIO server.** No MinIO binary is installable in this sandbox (no Docker daemon; no internet access to fetch one — confirmed directly, see ADR-0015). `moto`'s `ThreadedMotoServer` — a real local HTTP server implementing genuine S3 API semantics, not a mock at the `boto3` layer — stood in for both the automated test suite and a full manual live-verification pass. `s3_endpoint_url`/credentials/bucket configuration is exactly as `core/config.py` already specified; a real MinIO (or AWS S3) deployment should work identically, but has not itself been exercised. **Before relying on exports in a real deployment**: point `S3_ENDPOINT_URL` at a real MinIO/S3 endpoint, provision the bucket out-of-band (the app deliberately never auto-creates it), and run one real export end-to-end as a smoke test.
7. **Frontend uses hand-written types** (`apps/web/lib/types.ts`), not OpenAPI-generated ones — reasonable at this API-surface size; `packages/shared-types` is reserved for generated types later (see its README).
8. **`google_places` has never made a real call to Google's API (Milestone 3, ADR-0010).** No Google Cloud API key was available during implementation. The connector is built against Google's documented Places API (New) contract and covered by 22 mocked-HTTP-transport tests, but that is not the same as proof it works against Google's real servers — if any assumption about Google's actual response shape is wrong in a way the mocked tests didn't anticipate, it will only surface on first live use. **Before launching any real campaign against this connector**: obtain a Google Cloud API key with the Places API (New) enabled and billing configured, set `GOOGLE_PLACES_API_KEY`, and run a manual smoke test (a single real `search()` call, inspected by a human) before pointing a real tenant's campaign at it.
9. **`google_places` is not exposed in the frontend campaign-creation form.** Only `mock` is offered there today — deliberate, per ADR-0010, since offering a connector that can only fail without a real key would be poor UX, not a missing feature.
10. **No automated test exercises a real connector error path end-to-end through the worker's retry logic** (auth/quota/rate-limit/permanent failure and the retry backoff that follows). Milestone 3's mocked-adapter tests verify `GooglePlacesConnector` itself raises the right error type for each Google API error shape, but nothing yet drives `worker.campaign_tasks.run_campaign_task`'s actual retry/backoff loop end-to-end with an injected connector failure. A fault-injecting test connector (or a flag on `MockConnector` to simulate failures) is recommended as an early follow-up.
11. **The dev sandbox's own long-running processes (Postgres, Redis, the SMTP capture server, the Celery worker, the API/web dev servers) were repeatedly reaped during idle gaps in this session** and had to be restarted more than once mid-verification. This is a property of this particular sandboxed environment, not the application, but it's worth knowing if you see "connection refused" locally after leaving a dev environment idle — check that all four services are actually still running before assuming something is broken.
12. **The SSRF-safe crawler has never crawled a real external website (Milestone 4, ADR-0012).** This sandbox's egress policy blocks general internet access outright — confirmed directly (a raw request to a real domain and this crawler's own direct-IP-connect strategy were both rejected by the proxy with policy-level 403s). SSRF-blocking itself is verified against real DNS resolution (not mocked); fetch mechanics and the full crawl/detector/enrichment pipeline are verified against a real Postgres database with a mocked HTTP transport. **Before relying on this crawler against real business websites**, smoke-test it against a small set of real, known-safe external sites from an environment without this sandbox's restrictive egress policy.
13. **No frontend UI exists yet for triggering enrichment or viewing evidence.** Milestone 4's scope (per the original architecture) is backend-only (crawler, detectors, evidence storage); `POST /businesses/{id}/enrich` and the evidence/enrichment-status endpoints exist and are tested, but nothing in `apps/web` calls them yet — a `/campaigns/[id]` business list with an "Enrich" action is natural follow-up UI work, not part of this milestone's own line items.
14. **Milestone 5's duplicate-candidate-review/merge/undo endpoints now have a frontend home.** The lead detail page's "Duplicate candidates" section lists candidates involving the lead's business, but confirming/rejecting a candidate or undoing a merge is still done via the raw `POST /duplicate-candidates/{id}/confirm|reject` / `POST /merges/{id}/undo` endpoints (no button wired up yet) — a small, natural follow-up rather than a gap in the underlying capability, which is fully built and tested.
15. **Deduplication never merges more than one pair per discovery event (ADR-0013, by design, not a bug).** If three or more businesses are genuinely the same real place, the first (re)discovery resolves the strongest pair it finds; the remaining pairs converge over subsequent (re)discoveries rather than all at once. With only `mock` and `google_places` as sources today, a true 3+-way real-world collision is unlikely in practice, but worth knowing about at higher connector diversity (Milestone 8's CSV import / other connectors).
16. **Fuzzy name matching's same-city scoping means a genuine duplicate discovered with inconsistent city data (e.g. "Dubai" vs "Dubai, UAE" typos, or a business whose city field is simply missing) will not be matched or flagged at all** — no candidate, no merge. This is the conservative-by-design tradeoff working as intended (avoiding false positives across city boundaries) but does mean some real duplicates with messy location data go undetected until enrichment or a future connector supplies cleaner city data.
17. **Lead scoring's `category_and_location_match` factor only looks at the most recently (re)discovering campaign's filter** (`get_latest_campaign_id_for_business`). A business discovered by two campaigns with different target categories/locations is scored against whichever discovered it most recently, not an aggregate — a reasonable v1 simplification, not incorrect, but worth knowing if a business's score seems to shift after being picked up by a second, differently-targeted campaign.
18. **Scoring is manual, per-business (`POST /businesses/{id}/score`), with no bulk or automatic trigger.** A campaign's discovered businesses don't automatically become scored leads — each has to be scored individually via the API (the live-verification pass scripted this for 15 businesses by hand). A "score all businesses from this campaign" bulk action or an automatic post-discovery scoring trigger is natural follow-up work, not built in Milestone 5 or 6.
19. **Reconciling two independent `Lead` rows that both survive a business merge (both sides pre-existing) is unbuilt** (ADR-0014, by design). The data is never lost — the loser's `Lead` and everything attached to it stays fully intact and queryable by ID — but no UI or endpoint surfaces "these two leads probably describe the same business" or lets a human merge their notes/tags/history into one.
20. **The Lead Workspace's saved-view "apply" replays filters entirely client-side** — a saved view is just a stored `filters` JSON blob matching the list endpoint's own query-parameter shape; there's no server-side validation that a saved view's filters still reference a status/category/city that exists (e.g. a saved view built around a `category` that a tenant no longer uses just returns zero rows, not an error). Acceptable today; would matter more if saved views became shareable across tenants (they aren't).
21. **Exports are never charged credits.** The captured build list for Milestone 7 has no mention of metering exports, and neither does the seeded subscription-plan feature catalog (`max_team_members`, `max_concurrent_campaigns` are the only two limits today). This was a deliberate choice not to invent a requirement, not an oversight — if a future milestone wants exports metered, it needs its own feature/limit added to the catalog first.
22. **Two export columns (Opening Hours, Verification Status) are always empty, by design (ADR-0015).** Neither has a real data source anywhere in this codebase — no connector field, no crawler detector, and `LeadVerification` (limitation #19's own cousin) still doesn't exist. If a future milestone adds either data source, populating these columns is a small, additive change to `exports/data.py`, not a schema migration.
23. **`Export.expires_at` is set but nothing consumes it yet.** It marks when the underlying object *could* become eligible for storage cleanup, but no scheduled job actually deletes expired export objects — exported files persist in the bucket indefinitely today. A `queue.maintenance`-style periodic cleanup task (mirroring `expire_stale_reservations`) is natural follow-up work, not built in Milestone 7.
24. **`list_all_lead_ids_matching_filters` (the "export everything matching my filters" path) fetches up to 50,000 lead ids in one query rather than true keyset pagination.** Reasonable at any tenant scale this system has actually been exercised at; a tenant with more leads than that would need this reworked into real batched pagination before its filtered exports would complete correctly.

## Unresolved risks

- **`google_places` has never been called live (ADR-0010).** Everything about this connector's correctness against Google's real API rests on documentation-reasoning plus mocked-HTTP tests, not a live call. Treat it as unverified until a real key is supplied and a manual smoke test is run — do not launch a real tenant's campaign against it first.
- **The website enrichment crawler has never crawled a real external website (ADR-0012) — the equivalent open risk for this milestone.** Same shape of gap as the Google Places connector: correct by documentation-reasoning and mocked-transport tests, not by a live crawl. If a real website's actual behavior (redirect chains through a CDN, unusual robots.txt syntax, a non-UTF-8 encoding, a slow server near the timeout boundary) differs from what the mocked tests anticipate, it will only surface on first live use.
- **Connection-pool GUC leakage class of bug** (ADR-0007): fixed everywhere it was found by manual audit, but the codebase has no automated guard against a *future* service function making the same mistake — and Milestone 2 proved this risk is real by reintroducing it once (see limitation #4 above). Recommend a lightweight integration test pattern (assert a fresh session with no context set returns zero rows for every RLS table) as a standing regression test.
- **Per-task event-loop isolation** (ADR-0009): the worker's `run_db_task` helper is the only thing preventing every new Celery task from silently inheriting a previous task's closed-loop database/Redis/HTTP connections — now proven to matter a third time by the crawler's own per-fetch-client discipline (ADR-0012), after `GooglePlacesConnector` (ADR-0010). Like the RLS ordering rule, this is a discipline documented in ADRs and code comments, not something a linter enforces — a future async client added the naive way (a cached instance-scoped `httpx.AsyncClient`, a persistent connection of any kind) would reintroduce exactly this bug, and it would only surface once a worker process handles a second task, making it easy to miss in a quick manual check.
- **Single shared Postgres instance**: no read replica, no connection-pool sizing exercise under real background-job write load now that the campaign engine exists. A real concern once campaign volume grows.
- **Rate limiting is IP/account-keyed only**, no distributed abuse detection. Adequate for now.
- **No connector-error-path test coverage through the worker's own retry loop** (see limitation #10) — `GooglePlacesConnector` itself is tested to raise the right error types, but nothing yet drives `run_campaign_task`'s retry/backoff/permanent-failure handling end-to-end with an injected failure.
- **`Business.field_provenance` is JSONB, not a normalized table (ADR-0011).** Fine for every current read pattern (always "the whole provenance record for this business"), but a future feature needing to query/filter provenance across businesses by field or source would need it moved into a real table at that point.
- **The mock connector's limited name-generation word pool can produce coincidental cross-business collisions (see the Milestone 5 section's test-fix note and ADR-0013's Consequences).** Not a risk in the real system (real business names/domains essentially never collide by chance), but worth remembering if a future test against `mock` data shows an unexpected merge — check whether it's a genuine word-pool collision before assuming a dedup bug.
- **No connector diversity yet to exercise cross-source deduplication for real.** Both existing sources (`mock`, `google_places`) already dedup within themselves via `BusinessSourceRecord`'s own (tenant, source, source_native_id) upsert key (Milestone 4) — Milestone 5's dedup engine is what actually gets exercised when the *same* real business is discovered through *two different sources* (e.g. Google Places and a future CSV import), which cannot happen yet with only one real-data source in the system. The matching logic itself is fully tested against directly-constructed same-tenant business pairs (see `test_deduplication.py`), just not yet proven against a genuine two-source real-world collision.
- **The Starlette route-ordering hazard that caused the `/leads/bulk/*` bug (ADR-0014) is a general class of risk, not fully eliminated by fixing this one instance.** Any future literal-segment route added under a router that also has a `/{id}`-shaped route at the same position needs the same "register literal routes first" discipline — documented in a code comment at the point of the fix, but (like the RLS ordering rule and per-task event-loop isolation) not enforced by a linter or automated check. A route-collision test pattern (assert every literal-segment sibling route resolves correctly, not just the parameterized one) would be a reasonable standing regression test to add.
- **Object storage has never been exercised against a real MinIO/S3 server (see limitation #6 above) — the same shape of gap as the Google Places connector and the SSRF crawler.** `moto`'s real local S3-API server is functionally equivalent for everything `app.core.storage` actually does (upload, presign), but it is not proof a real MinIO deployment's own quirks (bucket-policy requirements, clock-skew sensitivity in signature verification, TLS configuration) won't surface something unexpected on first real use.
- **No storage-cleanup job exists for completed exports' underlying objects** (limitation #23) — exported files accumulate in the bucket indefinitely. Not a correctness risk today, but a real storage-cost/retention concern once export volume grows.

## Pending approvals
None outstanding. Milestone 7's scope (Exports, per the original architecture) was implemented under the standing "Proceed"-equivalent instruction ("Milestone 7"). ADR-0015 documents the full design — the `Export` row as its own audit/status record, replayable selection, signed-URL-per-request storage, streaming XLSX generation, uniform formula-injection protection, the never-fabricated Opening Hours/Verification Status columns, and the deliberate no-credit-charge decision — and is called out here for transparency, same pattern as prior milestones' ADRs.

## Next action
Awaiting your review of Milestone 7. When ready, let me know how you'd like to proceed — including whether you'd like Milestone 8 started next, per the original architecture's milestone order.

---

## Complete file inventory (created or modified in Milestone 1)

See the **Milestone 2 file inventory** below for everything added/changed since Milestone 1 shipped.

### Root
`package.json`, `pnpm-workspace.yaml`, `pyproject.toml`, `.gitignore`, `.env.example`, `docker-compose.yml`

### Infrastructure
`infrastructure/docker/postgres/init/01-init-roles.sh`, `infrastructure/docker/api/Dockerfile`, `infrastructure/docker/worker/Dockerfile`, `infrastructure/docker/web/Dockerfile`, `infrastructure/scripts/setup-local-db.sh`

### Backend — `apps/api`
`pyproject.toml`, `.env.example`, `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/5be9811cd917_*.py`, `alembic/versions/8a1f2c3d4e5f_*.py`, `alembic/versions/fe3f382fcffa_*.py`,
`app/main.py`, `app/dependencies.py`,
`app/core/{config,db,security,exceptions,middleware,rate_limit,logging,mail,cookies,model_registry}.py`,
`app/modules/identity/{models,schemas,repositories,services,routes}.py`,
`app/modules/tenancy/{models,schemas,repositories,services,routes}.py`,
`app/modules/permissions/{models,catalog,repositories}.py`,
`app/modules/subscriptions/{models,schemas,repositories,routes}.py`,
`app/modules/entitlements/service.py`,
`app/modules/usage/{models,schemas,repositories,services,routes}.py`,
`app/modules/audit/{models,schemas,service,routes}.py`,
`app/modules/platform_admin/{models,schemas,repositories,services,routes}.py`,
`app/seed/seed_data.py`,
`tests/{conftest,helpers,test_auth,test_tenancy_and_permissions,test_tenant_isolation,test_credit_wallet,test_platform_admin}.py`

### Worker — `apps/worker`
`pyproject.toml`, `worker/{celery_app,queues,beat_schedule,tasks}.py`

### Frontend — `apps/web`
`package.json`, `tsconfig.json`, `next.config.ts`, `postcss.config.mjs`, `eslint.config.mjs`, `.env.example`, `.env.local`, `proxy.ts`,
`app/layout.tsx`, `app/page.tsx`, `app/providers.tsx`, `app/globals.css`,
`app/(auth)/login/page.tsx`, `app/(auth)/register/page.tsx`, `app/(auth)/verify-email/page.tsx`, `app/(auth)/forgot-password/page.tsx`, `app/(auth)/reset-password/page.tsx`, `app/(auth)/invitations/accept/page.tsx`,
`app/onboarding/page.tsx`,
`app/(tenant)/layout.tsx`, `app/(tenant)/_components/TenantShell.tsx`, `app/(tenant)/dashboard/page.tsx`, `app/(tenant)/team/page.tsx`, `app/(tenant)/usage/page.tsx`, `app/(tenant)/audit/page.tsx`,
`lib/{api,types,session}.ts`

### Shared packages
`packages/ui/package.json`, `packages/ui/src/{Button,TextField,Card,Banner,index}.tsx|ts`,
`packages/shared-types/README.md`, `packages/config/README.md`

### Docs
`docs/project-status.md`, `docs/adr/0001` through `0007`

---

## Complete file inventory (created or modified in Milestone 2)

### Root
`pyproject.toml` (workspace members + ruff `src` list updated for `packages/connector-sdk`)

### New package — `packages/connector-sdk`
`pyproject.toml`, `connector_sdk/{__init__,errors,types,base,mock,registry}.py`

### Backend — `apps/api`
`pyproject.toml` (added `gridkeep-connector-sdk` dependency),
`app/main.py` (registered `campaigns_router`; defensive `model_registry` import),
`app/core/{celery_client,rate_limit}.py` (new producer-only Celery client; added `reset_redis_connection` for worker use),
`app/core/model_registry.py` (import campaign/job models),
`app/modules/campaigns/{models,repositories,schemas,services,state_machine,routes}.py` (new module),
`app/modules/campaign_jobs/{models,repositories,concurrency}.py` (new module),
`app/modules/tenancy/services.py` (fixed: new tenants now receive the trial plan's `monthly_credit_grant` at creation — a real bug found via live E2E testing, not a Milestone 2 feature per se),
`app/seed/seed_data.py` (added `max_concurrent_campaigns` plan feature to all 4 plans),
`alembic/versions/43cc58f21f97_*.py` (campaign engine tables + RLS),
`tests/test_campaign_engine.py` (new, 10 tests),
`tests/test_tenancy_and_permissions.py` (updated one assertion for the credit-grant fix above)

### Worker — `apps/worker`
`pyproject.toml` (added `gridkeep-connector-sdk` dependency, `pytest-asyncio`/`mypy` dev deps, pytest config),
`worker/celery_app.py` (registered `campaign_tasks`, routing, `model_registry` import),
`worker/campaign_tasks.py` (new — the page-fan-out task chain),
`worker/async_utils.py` (new — `run_db_task`, the per-task event-loop isolation fix, ADR-0009),
`worker/tasks.py` (switched to `run_db_task`),
`tests/conftest.py` (new test package), `tests/test_campaign_tasks.py` (new, 5 tests)

### Frontend — `apps/web`
`lib/types.ts` (added `Campaign`/`CampaignFilter`/`CampaignDetail`/`CreateCampaignRequest`/`CampaignEstimate`/`CampaignProgress`/`CampaignEvent`/`CampaignErrorEntry`),
`app/(tenant)/_components/TenantShell.tsx` (added the Campaigns nav item; fixed active-nav-highlight to match nested routes),
`app/(tenant)/dashboard/page.tsx` (updated the stale "campaigns arrive in a later milestone" copy),
`app/(tenant)/campaigns/page.tsx` (new — list + create-and-estimate form),
`app/(tenant)/campaigns/[id]/page.tsx` (new — detail view, live progress polling, actions, history)

### Docs
`docs/project-status.md`, `docs/adr/0008-campaign-entity-consolidation.md` (new), `docs/adr/0009-worker-per-task-event-loop-isolation.md` (new)

---

## Complete file inventory (created or modified in Milestone 3)

### `packages/connector-sdk`
`pyproject.toml` (added `httpx` runtime dependency, `pytest`/`pytest-asyncio`/`ruff`/`mypy` dev deps, pytest config — new test infrastructure for this package),
`connector_sdk/google_places.py` (new — the real Google Places connector),
`connector_sdk/registry.py` (registered `google_places` alongside `mock`),
`connector_sdk/__init__.py` (exported `GooglePlacesConnector`),
`tests/test_google_places.py` (new, 22 tests — this package's first test suite)

### Root
`.env.example` (updated the `GOOGLE_PLACES_API_KEY` comment to reflect it's now active, and clarified it's worker-only, not needed by the API process)

### Docs
`docs/project-status.md`, `docs/adr/0010-google-places-connector.md` (new)

---

## Complete file inventory (created or modified in Milestone 4)

### Backend — `apps/api` (new Business persistence + enrichment modules)
`app/modules/businesses/{models,repositories,schemas,routes}.py` (new),
`app/modules/enrichment/{models,repositories,schemas}.py` (new),
`app/modules/campaigns/routes.py` (added `GET /campaigns/{id}/businesses`),
`app/modules/permissions/catalog.py` (added `leads.enrich` permission, granted to Administrator/Campaign Manager/Sales Manager),
`app/core/celery_client.py` (added `enqueue_business_enrichment`),
`app/core/model_registry.py` (registered the four new models),
`app/main.py` (registered `businesses_router`),
`alembic/versions/3d4875d6ea04_*.py` (new — `businesses`, `business_source_records`, `business_enrichments`, `enrichment_evidence` tables + RLS)

### Worker — `apps/worker` (new crawler + enrichment task)
`worker/crawler/{safety,robots,fetcher,detectors}.py` (new),
`worker/enrichment_tasks.py` (new — the `run_business_enrichment` Celery task),
`worker/campaign_tasks.py` (now also persists a `Business`/`BusinessSourceRecord` per discovered result, alongside the existing `result_snapshot`),
`worker/celery_app.py` (registered `worker.enrichment_tasks`, routed to the new `queue.enrichment`),
`pyproject.toml` (added `beautifulsoup4` dependency),
`tests/test_crawler_detectors.py` (new, 20 tests),
`tests/test_crawler_safety.py` (new, 13 tests),
`tests/test_crawler_fetcher.py` (new, 8 tests),
`tests/test_enrichment_tasks.py` (new, 5 tests),
`tests/test_campaign_tasks.py` (2 new tests for Business-row persistence and re-discovery upsert behavior)

### Docs
`docs/project-status.md`, `docs/adr/0011-business-entity-consolidation.md` (new), `docs/adr/0012-crawler-ssrf-safety.md` (new)

---

## Complete file inventory (created or modified in Milestone 5)

### Backend — `apps/api` (new deduplication + leads modules)
`app/modules/businesses/normalize.py` (new — shared name/phone/address/domain normalization, split out to avoid a circular import between `repositories.py` and the new `dedup.py`),
`app/modules/businesses/dedup.py` (new — matching, auto-merge/candidate decision, merge, undo),
`app/modules/businesses/models.py` (added `Business.merged_into_id` + composite self-FK, `BusinessDuplicateCandidate`, `BusinessMergeHistory`; added indexes on `city`/`google_place_id`; renamed `_DISCOVERY_FIELDS` to public `DISCOVERY_FIELDS`),
`app/modules/businesses/repositories.py` (added dedup-supporting queries: duplicate-candidate/merge-history lookups, `get_latest_campaign_id_for_business`; `list_businesses_for_campaign` now filters `merged_into_id IS NULL`; `upsert_business_from_discovery` now also sets `normalized_phone`),
`app/modules/businesses/schemas.py` (added `merged_into_id` to `BusinessResponse`),
`app/modules/businesses/routes.py` (added `duplicates_router`/`merges_router`; new endpoints: `POST /businesses/{id}/score`, `GET /businesses/{id}/lead`, `GET /businesses/{id}/duplicates`, `GET /businesses/{id}/merge-history`, `GET /duplicate-candidates`, `POST /duplicate-candidates/{id}/confirm`, `POST /duplicate-candidates/{id}/reject`, `POST /merges/{id}/undo`),
`app/modules/leads/{models,repositories,schemas,scoring,routes}.py` (new module — `Lead`, `LeadScore`, `LeadOpportunity`, `LeadRecommendation`, the scoring engine, and read-only lead/score/opportunity/recommendation endpoints),
`app/modules/permissions/catalog.py` (added `leads.score` permission, granted to Administrator/Campaign Manager/Sales Manager; merge/candidate-review actions reuse the existing `leads.edit`),
`app/core/model_registry.py` (registered the six new models),
`app/main.py` (registered `duplicates_router`/`merges_router`/`leads_router`),
`alembic/versions/01a4e2835a3e_*.py` (new — `business_duplicate_candidates`, `business_merge_history`, `leads`, `lead_scores`, `lead_opportunities`, `lead_recommendations` tables + RLS; `businesses.merged_into_id`/`normalized_phone` columns + new indexes)

### Worker — `apps/worker`
`worker/campaign_tasks.py` (calls `businesses_dedup.process_new_business_for_duplicates` right after each discovery upsert),
`tests/test_campaign_tasks.py` (two Milestone 4 tests updated to assert the real invariants instead of a hardcoded count that a legitimate mock-data domain collision now breaks — see ADR-0013)

### Tests
`apps/api/tests/test_deduplication.py` (new, 20 tests),
`apps/api/tests/test_lead_scoring.py` (new, 9 tests)

### Docs
`docs/project-status.md`, `docs/adr/0013-deduplication-and-lead-scoring.md` (new)

---

## Complete file inventory (created or modified in Milestone 6)

### Backend — `apps/api`
`app/modules/tenancy/repositories.py` (added `list_active_members_for_tenant`),
`app/modules/tenancy/routes.py` (added `GET /tenants/members`),
`app/modules/tenancy/schemas.py` (added `MemberResponse`),
`app/modules/businesses/dedup.py` (extended `merge_businesses`/`undo_merge` to reassign a `Lead` onto its winner when unambiguous, or leave it untouched when both sides already have one — see ADR-0014),
`app/modules/leads/models.py` (added `Lead.assigned_to_user_id`; new `LeadAssignment`, `LeadStatusHistory`, `LeadNote`, `LeadTag`, `SavedLeadView` models),
`app/modules/leads/repositories.py` (added `list_leads` — the paginated/sorted/filtered query — plus status-history, assignment, note, tag, and saved-view CRUD functions),
`app/modules/leads/services.py` (new — status-change/assignment/note/tag/bulk-action orchestration, saved-view ownership enforcement),
`app/modules/leads/schemas.py` (added list/detail/note/tag/status/assignment/bulk/saved-view request and response schemas),
`app/modules/leads/routes.py` (added `GET /leads` (list), upgraded `GET /leads/{id}` to a full detail response, added status/assign/unassign/notes/tags endpoints plus `/leads/bulk/*` and `/leads/meta/statuses` — registered *before* the `/{lead_id}` routes to avoid the route-shadowing bug described in ADR-0014 — and a `saved_views_router`),
`app/core/model_registry.py` (registered the five new models),
`app/main.py` (registered `saved_views_router`),
`alembic/versions/a3024f96410c_*.py` (new — `lead_assignments`, `lead_status_history`, `lead_notes`, `lead_tags`, `saved_lead_views` tables + RLS; `leads.assigned_to_user_id` column + index/FK)

### Frontend — `apps/web`
`lib/types.ts` (added `Business`, `Member`, `Lead`, `LeadScore`/`ScoreFactor`, `LeadOpportunity`, `LeadRecommendation`, `NoteEntry`, `StatusHistoryEntry`, `AssignmentEntry`, `DuplicateCandidate`, `LeadListItem`/`LeadListResponse`, `LeadDetail`, `SavedView`, `LEAD_STATUSES`),
`app/(tenant)/_components/TenantShell.tsx` (added the Leads nav item),
`app/(tenant)/leads/page.tsx` (new — filterable/sortable/paginated list, bulk selection + bulk actions, saved views),
`app/(tenant)/leads/[id]/page.tsx` (new — business info, status/assignment controls + history, score breakdown, opportunities/recommendations, duplicate candidates, tags, notes)

### Tests
`apps/api/tests/test_lead_workspace.py` (new, 25 tests),
`apps/api/tests/test_lead_workspace_api.py` (new, 8 tests — including the bulk-route-ordering regression test)

### Docs
`docs/project-status.md`, `docs/adr/0014-lead-workspace.md` (new)

---

## Complete file inventory (created or modified in Milestone 7)

### Backend — `apps/api` (new exports module + object storage)
`app/core/storage.py` (new — `boto3` S3 client wrapper: tenant-prefixed keys, `upload_bytes`, `presigned_download_url`),
`app/core/celery_client.py` (added `enqueue_export`),
`app/core/model_registry.py` (registered `Export`, `ExportError`),
`app/modules/exports/__init__.py`, `models.py` (new — `Export`, `ExportError`), `repositories.py` (new — CRUD + status transitions), `data.py` (new — batched row assembly, the 31-column schema, `humanize`), `workbook.py` (new — XLSX/CSV generation, `sanitize_cell_value`, the four-sheet workbook builder), `schemas.py` (new — `CreateExportRequest`/`ExportFiltersRequest`/`ExportResponse`/etc.), `services.py` (new — `request_export`, `resolve_lead_ids`, `get_download_url`), `routes.py` (new — `POST`/`GET /exports`, `GET /exports/{id}`, `GET /exports/{id}/errors`, `GET /exports/{id}/download`),
`app/modules/leads/repositories.py` (added `list_leads_for_export`, `list_all_lead_ids_matching_filters`, `get_latest_scores_for_leads`, `get_opportunities_for_leads`, `get_recommendations_for_leads`, `get_open_assignments_for_leads`, `get_latest_notes_for_leads` — all batched),
`app/modules/businesses/repositories.py` (added `list_latest_source_records_for_businesses`, `list_latest_campaign_ids_for_businesses`),
`app/modules/enrichment/repositories.py` (added `SOCIAL_DETECTOR_TYPES`, `list_social_evidence_for_businesses`),
`app/modules/identity/repositories.py` (added `list_users_by_ids`),
`app/modules/campaigns/repositories.py` (added `list_campaigns_by_ids`),
`app/main.py` (registered `exports_router`),
`pyproject.toml` (added `openpyxl` as a real dependency; `moto[s3,server]` as a dev dependency),
`alembic/versions/865e52821072_*.py` (new — `exports`, `export_errors` tables + RLS)

### Worker — `apps/worker`
`worker/export_tasks.py` (new — `run_export`, mirroring `enrichment_tasks.run_business_enrichment`'s shape),
`worker/celery_app.py` (registered `worker.export_tasks`, routed `run_export` to `queue.export`),
`pyproject.toml` (added `moto[s3,server]` as a dev dependency)

### Frontend — `apps/web`
`lib/types.ts` (added `ExportFormat`, `ExportStatus`, `ExportRecord`, `ExportListResponse`, `ExportDownload`),
`app/(tenant)/_components/TenantShell.tsx` (added the Exports nav item),
`app/(tenant)/exports/page.tsx` (new — export list with live status polling and download),
`app/(tenant)/leads/page.tsx` (added export-format selector, "Export selected" bulk action, "Export all matching filters" action, and a success banner linking to `/exports`)

### Tests
`apps/worker/tests/test_export_tasks.py` (new, 4 tests — full pipeline against real Postgres + moto-backed S3, including workbook-reopen validation),
`apps/api/tests/test_exports.py` (new, 7 tests — selection resolution, request persistence, download-URL gating),
`apps/api/tests/test_exports_api.py` (new, 7 tests — HTTP-level permission enforcement and request validation)

### Docs
`docs/project-status.md`, `docs/adr/0015-exports.md` (new)
