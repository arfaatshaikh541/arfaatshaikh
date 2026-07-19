# GRIDKEEP Lead Intelligence — Project Status

## Current milestone
**Milestone 10: CI/CD pipeline and RLS/route hardening** — implementation complete, backend-only (this milestone has no frontend surface). No spec text named Milestone 10 directly; ADR-0001 and ADR-0007 each explicitly deferred "a CI check for this" to "Milestone 10, not yet built" (RLS migration coverage, and the RLS context-ordering rule respectively), matching the standing "No CI/CD pipeline yet" known limitation. Delivered: a GitHub Actions CI/CD pipeline (`.github/workflows/ci.yml`, five jobs — api/worker/connector-sdk/web/security-scan — matching exactly the verification commands run by hand at the end of every prior milestone); a schema-introspecting RLS coverage test (every table with a `tenant_id` column verified to have real RLS enabled, forced, and a policy that actually enforces tenant matching — not just "a policy exists"); and a generic route-shadowing regression test (the exact bug class that hit this codebase twice by hand, ADR-0014 and ADR-0016, now guarded against a third recurrence anywhere in the app, not just the two known instances). Both new tests were verified to actually catch a real regression — not just pass vacuously — by temporarily breaking RLS/route ordering on a real database and confirming failure, then reverting. The composed CI workflow itself has not been run by a real GitHub Actions runner (no Docker daemon in this sandbox, the same disclosed gap as Docker Compose in Milestone 1), though every individual command it runs was verified for real. See ADR-0018. Pending your review before proceeding to Milestone 11.

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

## Milestone 8 completed work

### Credential encryption (`apps/api/app/core/security.py`)
`encrypt_credential`/`decrypt_credential` use `Fernet` (already-a-dependency `cryptography`), keyed by SHA-256-stretching Milestone 1's declared-but-unused `credential_encryption_master_key` config value into a valid 32-byte key. Reversible (unlike a password hash) because a webhook secret must be recovered in full to sign each outgoing delivery. `sign_payload` computes the `HMAC-SHA256` signature sent as `X-Gridkeep-Signature`, over the *exact* bytes the HTTP client sends.

### Integrations / CRM push (`apps/api/app/modules/integrations`, `apps/worker/worker/integration_tasks.py`)
`Integration` (webhook URL, encrypted secret, enabled flag) and `IntegrationDelivery` (one row per push attempt: status, HTTP status, response snippet, error message, attempt count, the exact payload sent). `payload.py` builds the real lead payload from live data (business, latest score, opportunities, recommendations, tags, notes, assignee) — never fabricated. `push_lead_to_integration` (new `queue.crm_push`, finally consumed after being declared since Milestone 2) signs and POSTs through `worker.crawler.safety.safe_post_json` (new — reuses the enrichment crawler's SSRF resolve-and-validate defense rather than duplicating it; does not follow redirects, unlike the crawler's own `safe_get`). A permanent outcome (SSRF check failure) is distinguished from a transient one (timeout, 5xx, connection error) — only the latter retries. `POST/GET /integrations`, `GET/PATCH/DELETE /integrations/{id}`, `POST /integrations/{id}/push/{lead_id}`, `POST /integrations/{id}/push/bulk` (registered *before* the parameterized push route — the same route-ordering hazard ADR-0014 already found once), `GET /integrations/{id}/deliveries`. Gated by `integrations.manage` (create/update/delete) and `integrations.view` (list/read/push) — both already in the Milestone 1 catalog, unused until now; `integrations.view` also newly granted to Campaign Manager and Sales Manager (previously only Owner/Administrator had any `integrations.*`).

### CSV import (`apps/api/app/modules/csv_import`, `apps/worker/worker/csv_import_tasks.py`)
Deliberately does **not** implement `connector_sdk.BaseConnector` — that interface is shaped around paginated remote-API search, not "parse an already-uploaded file." Instead reuses `businesses.upsert_business_from_discovery` → `businesses.dedup.process_new_business_for_duplicates` directly (the same pipeline campaign-discovered businesses flow through), called with `campaign_id=None`. Upload (`POST /imports`, multipart, 10 MB cap) parses headers/sample rows and returns a preview for column mapping (13 mappable fields, deliberately excluding `email` — no CSV source is trusted to supply one, matching `Business.email` being enrichment-only since Milestone 4); `POST /imports/{id}/start` validates the mapping, reserves credits equal to the row count, and enqueues `run_csv_import` (`queue.search` — reused, not a new queue, since this is conceptually "another way businesses enter the system"). Each row runs inside its own `SAVEPOINT` so one bad row doesn't abort the batch; a stable `source_native_id` (SHA-256 of normalized name+address+phone) makes the whole row loop idempotent, so a retry after a mid-batch failure is safe. Credits are committed for only the actually-imported count — failed rows cost nothing. `GET /imports`, `GET /imports/{id}`, `GET /imports/{id}/errors`. Reuses `campaigns.create`/`campaigns.view` rather than a new permission — importing is the same tier of action as launching a campaign.

### Two systemic Celery-task bugs found during live verification, fixed across five files
**Bug 1**: `push_lead_to_integration`'s exception handling only anticipated two specific exception types; a real `RuntimeError` (a missing environment variable) escaped both, and Celery logged "raised unexpected" without ever recording an error — the delivery stayed `"pending"` forever. Fixed by broadening to `except Exception`, matching the pattern `export_tasks.py`/`csv_import_tasks.py` already used correctly.
**Bug 2** (found while writing a regression test for Bug 1): `except MaxRetriesExceededError:` around `raise self.retry(exc=exc, ...)` never actually catches anything once retries are exhausted, confirmed against the installed Celery version with a standalone repro script — `retry()` re-raises the *original* exception instead when `exc=` was passed, so the "finalize as failed with a clear error" cleanup this pattern was meant to guarantee **never ran on real retry exhaustion, in any of the five task files that used it**: `campaign_tasks.py` (since Milestone 2), `enrichment_tasks.py` (Milestone 4), `export_tasks.py` (Milestone 7), `csv_import_tasks.py` and `integration_tasks.py` (this milestone). Every one of those tasks was silently dying uncaught, with no error recorded, on its final retry attempt — exactly Bug 1's failure mode, just deferred. Fixed in all five by checking `self.request.retries >= self.max_retries` *before* calling `retry()`, which can't have this class of bug regardless of whether `exc=` is passed. `campaign_tasks.py`'s separate `_SlotUnavailable` branch (which didn't pass `exc=`, but also wasn't wrapped in any try/except) had the related exposure of an uncaught `MaxRetriesExceededError` on exhaustion — now also finalizes cleanly. See ADR-0016 for the full account, including why the regression test proving the fix (`test_celery_wrapper_finalizes_as_failed_once_retries_are_exhausted`) stubs the database layer rather than exercising it through a real Celery-wrapped task call.

### Live verification
Registered a user, imported a 3-row CSV (2 valid, 1 missing-name row correctly rejected with a specific error and correctly excluded from the credit charge), confirmed real `Business` rows in Postgres, scored one into a lead, created a real webhook integration, and pushed the lead to it. The first live attempt surfaced Bug 1 (see above); after both fixes and restarting the worker with `CREDENTIAL_ENCRYPTION_MASTER_KEY` correctly in its environment, a fresh push correctly progressed through all 5 attempts (1 initial + 4 retries, exponential backoff) against `https://example.com/gridkeep-hook` and finalized as `"failed"` with the real, honest error (`403 Forbidden` — this sandbox's egress-restricting proxy, the same restriction already confirmed against httpbin.org/webhook.site in earlier milestones) instead of staying stuck forever with nothing recorded.

### Frontend (`apps/web`)
`/integrations` — create/enable/disable/delete a webhook, per-integration delivery history. `/imports` — upload, column-mapping preview with a sample-rows table, start, polling history with expandable per-row errors. Lead detail page gained a "Push to CRM" card (shown only when at least one enabled integration exists). Both added to the tenant nav.

### Tests
- **`apps/api/tests/test_integrations_api.py`** (6 tests), **`apps/api/tests/test_csv_import_api.py`** (8 tests) — HTTP-level: permission enforcement, request validation, the bulk-route-ordering fix.
- **`apps/worker/tests/test_integration_tasks.py`** (6 tests) — signing against the real DB-round-tripped payload (not the pre-commit in-memory dict, since Postgres JSONB doesn't preserve key order), non-2xx staying `"pending"` for retry, permanent-vs-transient distinction, duplicate-delivery no-op, and the retry-exhaustion regression test for Bug 2.
- **`apps/worker/tests/test_csv_import_tasks.py`** (4 tests) — success + credit commit, partial completion, cross-import dedup (phone-tier auto-merge), duplicate-delivery no-op. Two real bugs found and fixed while writing these: a status guard too strict to allow a legitimate retry, and a `SET LOCAL`/RLS-context drop after a mid-task commit (ADR-0007's bug class, recurring a third time).
- **`apps/worker/tests/test_crawler_safety.py`** (+7 tests, now 20) — `safe_post_json`'s own SSRF-blocking/no-redirect-following/JSON-serialization behavior, independent of the integration task that calls it.
- Full monorepo verification: 125/125 (api) + 72/72 (worker) + 22/22 (connector-sdk) = 219/219 passing; ruff and mypy clean across all three Python packages; `alembic check` reports no drift; frontend `pnpm lint`, `pnpm typecheck`, and `next build` all clean (all 19 routes generated, including the two new ones).

## Milestone 9 completed work

### Real Stripe integration (`apps/api/app/modules/billing`)
`BillingCustomer` (tenant <-> Stripe Customer mapping, created lazily on first checkout/portal use), `BillingSubscription` (a live mirror of Stripe's own subscription object, kept in Stripe's own status vocabulary rather than normalized away), `BillingEvent` (every webhook event received, keyed by Stripe's event id for idempotency — the real audit trail), `InvoiceRecord` (one row per invoice). `create_checkout_session` starts a real Stripe-hosted Checkout Session (`mode="subscription"`) and returns its URL; `create_portal_session` opens the real Stripe Customer Portal. Neither ever itself marks a tenant as upgraded — only `handle_webhook_event`, driven by Stripe's own signed `customer.subscription.*`/`invoice.*` events, ever mutates `TenantSubscription`'s plan/status/period (via new `subscriptions.repositories.update_tenant_subscription_plan`, mutating the tenant's one subscription row in place — previously only ever set once by seed data). `POST /billing/webhook` is the first endpoint in this codebase authenticated by an external HMAC signature rather than this platform's own session/CSRF machinery; it resolves the tenant via `set_platform_bypass` from a unique external key (the Stripe customer/event id), the same narrowly-scoped pattern ADR-0007 already sanctions for invitation-accept-by-token.

### `SubscriptionPlan.stripe_price_id`: real, per-deployment config, never fabricated
A new nullable column — NULL in seed data, since no real Stripe account exists here. `create_checkout_session` fails with a clear `ConflictError` for a plan with no price configured, rather than fabricating one or silently proceeding; the frontend's plan cards read this state (`checkout_available`) and show "Not yet available" instead of an "Upgrade" button. Live-verified in a real browser: a plan with a real price shows "Upgrade" and, with no live Stripe key set, clicking it surfaces the honest "Billing is not configured for this deployment" error — never a fabricated success.

### New endpoints
`POST /billing/checkout-session`, `POST /billing/portal-session` (both `billing.manage`), `GET /billing/plans`, `GET /billing/invoices` (both `billing.view`), `POST /billing/webhook` (unauthenticated by session — Stripe-signature-verified instead). All permission keys and the "Billing Manager" role were already seeded in Milestone 1, unused until now.

### Frontend
The existing `/usage` page (already titled "Usage & Billing") gained a plan-comparison grid, a "Manage billing" button opening the real Customer Portal, and an invoice history table — deliberately not a new nav item, since billing already had a natural home there.

### Tests
`apps/api/tests/test_billing_api.py` (new, 13 tests) — checkout/portal session creation with real Stripe SDK request shapes verified via monkeypatching, config-missing and no-price-configured failures, permission enforcement (Sales Representative denied all three billing endpoints; Billing Manager allowed), and — the significant piece — every webhook test posts a **genuinely, correctly HMAC-signed payload** through the real `stripe.Webhook.construct_event` verification path: invalid-signature rejection, subscription sync into both `BillingSubscription` and `TenantSubscription`, idempotency for a redelivered event, subscription-deleted marking both records canceled, and invoice-paid recording. Full monorepo verification: 138/138 (api) + 72/72 (worker) + 22/22 (connector-sdk) = 232/232 passing; ruff and mypy clean across all three Python packages; `alembic check` reports no drift; frontend `pnpm lint`, `pnpm typecheck`, and `next build` all clean.

## Milestone 10 completed work

### CI/CD pipeline (`.github/workflows/ci.yml`)
Five jobs: `api` (ruff, mypy, `alembic upgrade head`, `alembic check`, pytest — against real `postgres:16`/`redis:7` service containers, role/database setup reusing `infrastructure/scripts/setup-local-db.sh` unmodified so CI can never drift from local dev), `worker` (same shape), `connector-sdk` (no database needed), `web` (ESLint, `tsc --noEmit`, `next build`), `security-scan` (`pip-audit` per Python package via `uv export --no-emit-workspace`, `pnpm audit --audit-level high` — advisory, `continue-on-error: true`, not a merge gate). Every command was run for real against real services before being written into the workflow (all three Python packages' dependency sets came back with zero known vulnerabilities; `pnpm audit --audit-level high` correctly passes with only pre-existing low/moderate findings, none high/critical). The composed workflow has not itself been executed by GitHub Actions — no Docker daemon is reachable in this sandbox.

### RLS coverage check (`apps/api/tests/test_rls_coverage.py`) — closes ADR-0001's named Milestone 10 gap
Introspects the real Postgres schema directly (no hardcoded table list, so it automatically covers any future tenant-owned table): every table with a `tenant_id` column must have RLS enabled, forced, and a policy whose `USING`/`WITH CHECK` clauses both actually reference tenant matching and the `platform_bypass` escape hatch — not just "a policy exists." `platform_audit_logs` is the one deliberate, documented exception (its `tenant_id` is an informational FK, not an ownership column — the table is intentionally platform-only). Verified to catch a real regression: temporarily forcing RLS off and swapping in a `USING (true)` policy on a real table made both tests fail with the expected message; reverting restored a clean pass.

### Route-shadowing regression test (`apps/api/tests/test_route_ordering.py`) — closes the ADR-0014 unresolved risk
Generically guards against the bug class that hit this codebase twice by hand (ADR-0014's `/leads/bulk/status`, ADR-0016's `/integrations/{id}/push/bulk`): introspects the real, fully-assembled FastAPI app's route table and flags any pair of routes sharing an HTTP method whose paths differ in exactly one segment where one has a literal and the other a parameter, unless the literal one is registered first. Verified against synthetic route pairs reproducing both the known-bad and the actual-fixed ordering before being trusted against the real app.

### Tests
`apps/api/tests/test_rls_coverage.py` (new, 2 tests), `apps/api/tests/test_route_ordering.py` (new, 1 test) — no production code changed this milestone, tooling and coverage only. Full monorepo verification: 141/141 (api) + 72/72 (worker) + 22/22 (connector-sdk) = 235/235 passing; ruff and mypy clean across all three Python packages; `alembic check` reports no drift; frontend `pnpm lint`, `pnpm typecheck`, and `next build` all clean (unchanged this milestone).

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
| Backend tests pass | ✅ 141/141 (api) + 72/72 (worker) + 22/22 (connector-sdk) = 235/235 |
| CI/CD pipeline (lint/test/build/scan on push) | ✅ `.github/workflows/ci.yml`, 5 jobs; every command verified for real, composed workflow not yet run by GitHub Actions itself (no Docker daemon in this sandbox) |
| RLS migration coverage enforced automatically | ✅ Schema-introspecting test (`test_rls_coverage.py`), verified to catch a real regression, not hardcoded to known tables |
| Route-shadowing bug class guarded generically | ✅ `test_route_ordering.py` — guards against a third recurrence anywhere in the app, not just the two known fixed instances |
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
| CRM push: outbound webhook integrations, encrypted credentials | ✅ `Fernet`-encrypted webhook secret, never returned by any API response; tested + live-verified |
| CRM push: signed payloads, SSRF-safe delivery | ✅ HMAC-SHA256 over the exact bytes sent; delivery reuses the enrichment crawler's real SSRF resolve-and-validate defense (`safe_post_json`, no redirect-following); tested + live-verified (the SSRF check itself, and the full retry/failure pipeline) |
| CRM push: delivery history, retry, permanent-vs-transient failure handling | ✅ Every attempt recorded (status, HTTP code, response snippet, error, attempt count); SSRF failures never retried, transient failures retry with backoff then finalize as `"failed"` with a real error — the finalize step required a real bug fix this milestone, see ADR-0016 |
| CSV import: upload, column mapping, background processing | ✅ Preview → mapping → background Celery task on `queue.search`, reusing the exact campaign discovery-upsert/dedup pipeline; tested + live-verified |
| CSV import: partial completion, per-row errors, idempotent retry | ✅ Per-row `SAVEPOINT`, per-row error recording, stable `source_native_id` makes a full retry of the row loop safe; tested (including a real `SET LOCAL`/RLS-context bug found and fixed) |
| CSV import: credit charge for only what actually imported | ✅ Reserved at row count, committed at actual imported count — failed rows cost nothing; tested + live-verified |
| Billing: real payment provider integration (Stripe) | ✅ Real Checkout Sessions + Customer Portal, real Stripe SDK calls; tested (mocked-adapter, request-shape verified) + live-verified (honest not-configured failure, plan-availability UI) |
| Billing: `BillingCustomer`/`BillingSubscription`/`BillingEvent`/`InvoiceRecord` entities | ✅ All four implemented per ADR-0006's deferred scope; `BillingEvent` is the full webhook audit trail |
| Billing: webhook-driven subscription/invoice sync | ✅ Webhook is the sole source of truth — a checkout redirect alone never grants a plan change; tested with genuinely HMAC-signed payloads through the real signature-verification path |
| Billing: never fabricate checkout for an unconfigured plan | ✅ `SubscriptionPlan.stripe_price_id` NULL by default; checkout fails clearly, frontend shows "Not yet available" instead of a broken button |

## Architecture decisions
See `docs/adr/0001` through `0018`. Summary: shared-schema+RLS multi-tenancy, server-side sessions, `uv`/`pnpm` tooling, campaign-level credit-reservation granularity, MFA scaffolded only, no billing provider selected yet as of Milestone 1 (0006, closed out by 0017), a documented RLS ordering rule + `platform_bypass` escape-hatch pattern (0007, its named "CI check" gap closed by 0018), campaign entity consolidation vs. the original architecture's larger entity list (0008), a documented per-task event-loop isolation rule for the worker's async DB/Redis clients (0009), the Google Places connector's design plus its explicit live-verification gap (0010), the Business entity consolidation and the Milestone 2 persistence gap it fixes (0011), the SSRF-safe crawler's design plus its own explicit live-verification gap (0012), the deduplication engine's confidence-threshold design plus the explainable lead-scoring algorithm (0013), the Lead Workspace's design — no lead-status state machine, assignment/tag/saved-view design, the dedup-merge Lead-reassignment fix, and the bulk-route-ordering fix (0014), the Exports design — the `Export` row as its own audit/status record, replayable (not frozen) selection, signed-URL-per-request storage, streaming XLSX generation, uniform formula-injection protection, and the never-fabricated Opening Hours/Verification Status columns (0015), the CRM push/CSV import design — the generic-webhook-not-named-connector decision, credential encryption, HMAC signing, SSRF-safety reuse, CSV import's deliberate non-implementation of `BaseConnector`, and the two systemic Celery retry-exhaustion bugs found and fixed across five task files (0016), the billing provider integration — real Stripe Checkout/Portal/webhook, the webhook-as-sole-source-of-truth decision, `SubscriptionPlan.stripe_price_id` as real never-fabricated per-deployment config, and the webhook route as the first HMAC-signature-authenticated (not session-authenticated) endpoint in this codebase (0017), and the CI/CD pipeline plus RLS-coverage/route-shadowing hardening tests — both explicitly named "Milestone 10" gaps in ADR-0001/ADR-0007, verified to catch real regressions rather than pass vacuously (0018).

## Known limitations

1. **Docker Compose stack not verified end-to-end in this build environment.** This session's outbound network egress policy blocks Docker Hub image pulls (`production.cloudfront.docker.com` returns a 403 policy denial), so `docker compose up` could not be run here. All verification instead ran the same services natively: PostgreSQL 16 and Redis were already installed in this sandbox and used directly; the FastAPI app, Celery worker, and Next.js dev server were run directly via `uv run` / `pnpm dev`. The `docker-compose.yml` and Dockerfiles are believed correct (they mirror the exact configuration verified natively) but **you should run `docker compose up` yourself before relying on it** — that is the one meaningful gap between "verified" and "should work."
2. **MFA is scaffolded, not enrollable** (ADR-0005) — by design, per your approval.
3. **No billing provider integration** (ADR-0006) — by design, per your approval; plans/credits are seed data today.
4. **RLS discipline is now automatically checked for *coverage* (Milestone 10, ADR-0018), but *call-site ordering* remains manual.** `apps/api/tests/test_rls_coverage.py` (part of the CI suite) automatically verifies every tenant-owned table has real, working RLS — closing ADR-0001's named gap. What's still unenforced: the ordering rule in ADR-0007 (`set_tenant_context` before any RLS-protected query within a service function's own code) is a call-site property no schema-introspection test can verify — a future service function could still reintroduce the same class of bug if the rule isn't followed at the point it's written. Milestone 2's worker code hit exactly this once (`worker.campaign_tasks._run_campaign_task_async`'s first lookup needed `set_platform_bypass` before its first read) before being fixed.
5. **CI/CD pipeline now exists (Milestone 10, ADR-0018) but has not itself been run by GitHub Actions.** `.github/workflows/ci.yml` covers lint/test/build for all four packages plus an advisory dependency-vulnerability scan — every individual command in it was verified to work for real against real services, but the *composed* workflow has never executed on an actual GitHub Actions runner, since this sandbox has no reachable Docker daemon (the same gap Docker Compose has always had here). Its first real run is the remaining thing to confirm.
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
25. **No real external webhook delivery has been observed succeeding (Milestone 8, ADR-0016).** This sandbox's egress-restricting proxy blocks every outbound target tried (`example.com`, plus `httpbin.org`/`webhook.site` confirmed blocked in earlier milestones) — the same class of gap as the Google Places connector (#8) and the SSRF crawler (#12). What *is* verified live: the SSRF-check-engaging path, correct HMAC signing against the real DB-round-tripped payload, and the full retry-then-finalize pipeline (5 real attempts with real exponential backoff against a real integration, ending in a correctly-recorded `"failed"` status with a real error). Before relying on this in production, run one real webhook delivery against a real receiver from an environment without this restriction.
26. **No automatic push-on-status-change or score-threshold trigger for CRM push.** Every push is a manual, explicit user action (single lead or bulk selection) — there is no rule engine deciding when a lead should auto-push. The captured requirements never specified a trigger condition; inventing one would be adding a requirement, not implementing one.
27. **CSV import's numeric fields (`rating`, `review_count`) are silently dropped, not fabricated or flagged as an error, if a cell fails to parse as a number.** Consistent with "never fabricate a missing field," but different from a missing `name` (which does become a `CsvImportError` row) — worth knowing since a malformed numeric cell doesn't show up anywhere in the import's error list.
28. **A systemic Celery retry-exhaustion bug (ADR-0016, Bug 2) existed in five task files since Milestones 2, 4, and 7, undetected until this milestone's live verification led to inspecting `Task.retry()`'s actual behavior.** `except MaxRetriesExceededError:` around a `retry(exc=exc, ...)` call never caught anything once retries were exhausted — every one of these tasks (`campaign_tasks`, `enrichment_tasks`, `export_tasks`, `csv_import_tasks`, `integration_tasks`) was silently dying uncaught on its final retry, with no error ever recorded, instead of cleanly finalizing as failed. Now fixed everywhere it existed (see the ADR for the exact mechanism and the fix), but it went unnoticed for three prior milestones because no automated test exercised a real Celery-wrapped task through actual retry exhaustion — every existing worker test called the underlying async function directly, bypassing the Celery retry machinery entirely. Recommend treating "does this task's finalize-as-failed path actually run when retries are exhausted" as a standing thing to verify for any *future* Celery task added with this shape, not just trust the pattern by inspection.
29. **No real Stripe account exists in this environment (Milestone 9, ADR-0017) - the same shape of gap as the Google Places connector (#8) and the SSRF crawler (#12).** No live Checkout Session was ever opened against Stripe's real servers, and Stripe never actually delivered a webhook here. What *is* verified for real without needing a live key: webhook signature verification (genuinely HMAC-signed test payloads through the real `stripe.Webhook.construct_event` path) and the exact request shape of every outbound Stripe SDK call (verified via a monkeypatched call boundary). **Before relying on this in production**: create a real Stripe account, set the three Stripe config values, create real Products/Prices and set each `SubscriptionPlan.stripe_price_id`, configure the webhook endpoint in Stripe's dashboard, and run one real checkout end-to-end as a smoke test.
30. **No recurring monthly credit grant is wired to the billing cycle.** `SubscriptionPlan.monthly_credit_grant` still only grants credits once, at tenant creation (Milestone 1 seed data) - a real subscription renewing monthly doesn't yet re-grant credits each period. ADR-0006/the captured build list never specified a recurring-grant trigger mechanism, so none was invented; a `queue.maintenance`-style periodic task (or a webhook-driven grant on `invoice.paid`) is natural follow-up work, not built in Milestone 9.
31. **Only one active `BillingSubscription`/`TenantSubscription` per tenant is modeled.** A tenant with multiple simultaneous Stripe subscriptions (e.g. a base plan plus a separately-billed add-on subscription) isn't representable - `BillingSubscription.tenant_id` is unique. Every plan in this codebase's catalog is a single all-inclusive tier, so this hasn't been a real constraint yet, but would need rework if a future milestone wants multiple concurrent Stripe subscriptions per tenant.

## Unresolved risks

- **`google_places` has never been called live (ADR-0010).** Everything about this connector's correctness against Google's real API rests on documentation-reasoning plus mocked-HTTP tests, not a live call. Treat it as unverified until a real key is supplied and a manual smoke test is run — do not launch a real tenant's campaign against it first.
- **The website enrichment crawler has never crawled a real external website (ADR-0012) — the equivalent open risk for this milestone.** Same shape of gap as the Google Places connector: correct by documentation-reasoning and mocked-transport tests, not by a live crawl. If a real website's actual behavior (redirect chains through a CDN, unusual robots.txt syntax, a non-UTF-8 encoding, a slow server near the timeout boundary) differs from what the mocked tests anticipate, it will only surface on first live use.
- **Connection-pool GUC leakage class of bug** (ADR-0007): the *coverage* half is now automated (Milestone 10's `test_rls_coverage.py` — every tenant-owned table verified to have real, correctly-worded RLS). The *ordering* half — a future service function calling a query before `set_tenant_context`/`set_platform_bypass` within its own code — remains a manual-discipline risk with no automated guard, since it's a call-site property, not a schema property; Milestone 2 proved this specific risk real once already (see limitation #4). A future hardening pass could pursue a custom lint rule (e.g. a ruff/AST plugin flagging any RLS-protected-model query not preceded by a context call in the same function) if this recurs again.
- **Per-task event-loop isolation** (ADR-0009): the worker's `run_db_task` helper is the only thing preventing every new Celery task from silently inheriting a previous task's closed-loop database/Redis/HTTP connections — now proven to matter a third time by the crawler's own per-fetch-client discipline (ADR-0012), after `GooglePlacesConnector` (ADR-0010). Like the RLS ordering rule, this is a discipline documented in ADRs and code comments, not something a linter enforces — a future async client added the naive way (a cached instance-scoped `httpx.AsyncClient`, a persistent connection of any kind) would reintroduce exactly this bug, and it would only surface once a worker process handles a second task, making it easy to miss in a quick manual check.
- **Single shared Postgres instance**: no read replica, no connection-pool sizing exercise under real background-job write load now that the campaign engine exists. A real concern once campaign volume grows.
- **Rate limiting is IP/account-keyed only**, no distributed abuse detection. Adequate for now.
- **No connector-error-path test coverage through the worker's own retry loop** (see limitation #10) — `GooglePlacesConnector` itself is tested to raise the right error types, but nothing yet drives `run_campaign_task`'s retry/backoff/permanent-failure handling end-to-end with an injected failure.
- **`Business.field_provenance` is JSONB, not a normalized table (ADR-0011).** Fine for every current read pattern (always "the whole provenance record for this business"), but a future feature needing to query/filter provenance across businesses by field or source would need it moved into a real table at that point.
- **The mock connector's limited name-generation word pool can produce coincidental cross-business collisions (see the Milestone 5 section's test-fix note and ADR-0013's Consequences).** Not a risk in the real system (real business names/domains essentially never collide by chance), but worth remembering if a future test against `mock` data shows an unexpected merge — check whether it's a genuine word-pool collision before assuming a dedup bug.
- **No connector diversity yet to exercise cross-source deduplication for real.** Both existing sources (`mock`, `google_places`) already dedup within themselves via `BusinessSourceRecord`'s own (tenant, source, source_native_id) upsert key (Milestone 4) — Milestone 5's dedup engine is what actually gets exercised when the *same* real business is discovered through *two different sources* (e.g. Google Places and a future CSV import), which cannot happen yet with only one real-data source in the system. The matching logic itself is fully tested against directly-constructed same-tenant business pairs (see `test_deduplication.py`), just not yet proven against a genuine two-source real-world collision.
- **The Starlette route-ordering hazard that caused the `/leads/bulk/*` bug (ADR-0014) is now generically guarded (Milestone 10, ADR-0018).** `apps/api/tests/test_route_ordering.py` introspects the real app's route table and flags any literal-segment route shadowed by an earlier parameterized sibling — a *third* recurrence anywhere in the app would now be caught automatically, not just the two known-fixed instances (ADR-0014, ADR-0016). Verified against synthetic bad/good orderings before being trusted against the real app.
- **Object storage has never been exercised against a real MinIO/S3 server (see limitation #6 above) — the same shape of gap as the Google Places connector and the SSRF crawler.** `moto`'s real local S3-API server is functionally equivalent for everything `app.core.storage` actually does (upload, presign), but it is not proof a real MinIO deployment's own quirks (bucket-policy requirements, clock-skew sensitivity in signature verification, TLS configuration) won't surface something unexpected on first real use.
- **No storage-cleanup job exists for completed exports' underlying objects** (limitation #23) — exported files accumulate in the bucket indefinitely. Not a correctness risk today, but a real storage-cost/retention concern once export volume grows.
- **No real external webhook delivery has been observed succeeding (limitation #25)** — the same shape of gap as the Google Places connector and the SSRF crawler, for the same reason (this sandbox's egress restrictions). The retry/failure pipeline is proven correct live; a real receiver's actual behavior (response timing, an unusual redirect, a non-JSON error body) has not been observed.
- **The systemic Celery retry-exhaustion bug (limitation #28) was only found by accident, three milestones after the earliest instance was introduced.** Its root cause (Celery's `retry(exc=exc, ...)` re-raising the original exception instead of `MaxRetriesExceededError` once retries are exhausted) is now fixed everywhere it existed and understood well enough to avoid reintroducing, but — like the RLS ordering rule (ADR-0007) and the route-ordering hazard (ADR-0014) — nothing automated stops a *future* task written with the old `try/except MaxRetriesExceededError` shape from reintroducing it. A lint rule or a shared task-wrapper helper enforcing the `if self.request.retries >= self.max_retries` pattern would close this permanently; recommend it as follow-up work.
- **No real Stripe account has ever been exercised (limitation #29)** — the same shape of gap as the Google Places connector and the SSRF crawler. Webhook signature verification and every outbound SDK call's request shape are proven for real; a real Stripe account's own quirks (a webhook event shape this environment's tests didn't anticipate, a Checkout Session edge case) have not been observed.
- **No recurring credit grant on subscription renewal (limitation #30)** — a real Stripe subscription renewing monthly does not currently re-grant that plan's `monthly_credit_grant`. Not a correctness bug (nothing claims this works), but a real gap before this billing integration could support ongoing paid usage the way the credit system's own design implies it eventually should.
- **The CI/CD pipeline has never been run by a real GitHub Actions runner (limitation #5, Milestone 10, ADR-0018)** — the same shape of gap as every other "verified the parts, not the whole" item in this project (Google Places, the SSRF crawler, Stripe), caused here by no Docker daemon being reachable in this sandbox rather than an external API/network restriction. Every individual command the workflow runs was verified for real (real Postgres/Redis services, real `pip-audit`/`pnpm audit` runs against this project's actual dependencies) before being written into the YAML, but the composed workflow's first real execution — including whether the GitHub-hosted runner's own environment (available disk, default tool versions, network egress to PyPI/npm) matches what was assumed here — is still unconfirmed.
- **The RLS *ordering* rule (as opposed to *coverage*, now automated) still has no automated guard (limitation #4, updated Milestone 10).** `test_rls_coverage.py` proves every table's policy is correctly worded; it cannot prove every service function calls `set_tenant_context`/`set_platform_bypass` before its first RLS-protected query, since that's a call-site property within application code, not a database-schema property. This remains exactly the same open risk ADR-0007 originally flagged, now scoped more precisely now that the coverage half is closed.

## Pending approvals
None outstanding. Milestone 10's scope (CI/CD pipeline plus RLS/route hardening, inferred from ADR-0001 and ADR-0007 both explicitly naming "a CI check for this" as "a hardening item for Milestone 10, not yet built") was implemented under the standing "Proceed"-equivalent instruction ("Milestone 10"). ADR-0018 documents the full design — the CI workflow's structure and what was/wasn't verified about its composition, the RLS coverage test's schema-introspection approach and why a data-seeded runtime variant was rejected as vacuous, and the generic route-shadowing test's verified detection logic — and is called out here for transparency, same pattern as prior milestones' ADRs.

## Next action
Awaiting your review of Milestone 10. When ready, let me know how you'd like to proceed — including whether you'd like Milestone 11 started next. No spec text in this session names Milestone 11's scope, unlike Milestone 10 (ADR-0001/ADR-0007) or Milestone 9 (ADR-0006) — if you have a specific next milestone in mind, please share it; otherwise I'd recommend reviewing the accumulated "Known limitations"/"Unresolved risks" lists for the next highest-value gap to close (the strongest remaining candidates: a real live-verification pass against actual Google Places/Stripe/webhook-receiver credentials from an unrestricted network, or closing the RLS *ordering* automation gap noted above).

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

---

## Complete file inventory (created or modified in Milestone 8)

### Backend — `apps/api` (new integrations + csv_import modules)
`app/core/security.py` (added `encrypt_credential`/`decrypt_credential`/`sign_payload`),
`app/core/storage.py` (added `download_bytes`),
`app/core/celery_client.py` (added `enqueue_integration_delivery`, `enqueue_csv_import`),
`app/core/model_registry.py` (registered `Integration`, `IntegrationDelivery`, `CsvImport`, `CsvImportError`),
`app/modules/integrations/{models,repositories,payload,schemas,services,routes}.py` (new — `Integration`, `IntegrationDelivery`; the `/push/bulk`-before-`/push/{lead_id}` route-ordering fix),
`app/modules/csv_import/{models,parsing,repositories,schemas,services,routes}.py` (new — `CsvImport`, `CsvImportError`; upload/preview/mapping/start/list/detail/errors),
`app/modules/businesses/repositories.py` (`upsert_business_from_discovery`'s `campaign_id` parameter type tightened to `uuid.UUID | None`, since CSV import genuinely needs to pass `None`),
`app/modules/permissions/catalog.py` (added `integrations.view` to Campaign Manager and Sales Manager role defaults),
`app/main.py` (registered `integrations_router`, `csv_import_router`),
`alembic/versions/6ab02302f662_*.py` (new — `integrations`, `integration_deliveries` tables + RLS),
`alembic/versions/eda5a5ae04d5_*.py` (new — `csv_imports`, `csv_import_errors` tables + RLS),
`tests/conftest.py` (added `CREDENTIAL_ENCRYPTION_MASTER_KEY` test env var, a shared `moto_s3` fixture),
`tests/test_integrations_api.py` (new, 6 tests),
`tests/test_csv_import_api.py` (new, 8 tests)

### Worker — `apps/worker`
`worker/crawler/safety.py` (added `safe_post_json` — reuses the crawler's SSRF resolve-and-validate defense for outbound webhook delivery; does not follow redirects),
`worker/integration_tasks.py` (new — `push_lead_to_integration`),
`worker/csv_import_tasks.py` (new — `run_csv_import`; the `SET LOCAL`/RLS-context-drop fix; the status-guard-too-strict-for-retry fix),
`worker/campaign_tasks.py`, `worker/enrichment_tasks.py`, `worker/export_tasks.py` (all three: fixed the `except MaxRetriesExceededError` dead-code pattern — see ADR-0016 Bug 2 — by checking `self.request.retries >= self.max_retries` before calling `retry()`; `campaign_tasks.py`'s `_SlotUnavailable` branch also now finalizes cleanly on exhaustion instead of dying uncaught),
`worker/celery_app.py` (registered `worker.integration_tasks`, `worker.csv_import_tasks`; routed `push_lead_to_integration` to the now-finally-consumed `queue.crm_push`, `run_csv_import` to `queue.search`),
`tests/conftest.py` (added `CREDENTIAL_ENCRYPTION_MASTER_KEY` test env var; moved the `moto_s3` fixture here from `test_export_tasks.py` so `test_csv_import_tasks.py` can share it),
`tests/test_crawler_safety.py` (+7 tests for `safe_post_json`, now 20 total),
`tests/test_integration_tasks.py` (new, 6 tests — including the retry-exhaustion regression test for Bug 2),
`tests/test_csv_import_tasks.py` (new, 4 tests)

### Frontend — `apps/web`
`lib/types.ts` (added `Integration`, `IntegrationListResponse`, `IntegrationDeliveryStatus`, `IntegrationDelivery`, `IntegrationDeliveryListResponse`, `CsvImportStatus`, `CsvImportPreview`, `CsvImportRecord`, `CsvImportListResponse`, `CsvImportErrorEntry`, `CsvImportErrorListResponse`),
`lib/api.ts` (added `api.patch`, standalone `uploadFile` for multipart uploads),
`app/(tenant)/_components/TenantShell.tsx` (added the Imports and Integrations nav items),
`app/(tenant)/integrations/page.tsx` (new — create/enable/disable/delete a webhook, per-integration delivery history),
`app/(tenant)/imports/page.tsx` (new — upload → column-mapping preview → start → polling history with per-row errors),
`app/(tenant)/leads/[id]/page.tsx` (added a "Push to CRM" card, shown only when at least one enabled integration exists)

### Docs
`docs/project-status.md`, `docs/adr/0016-integrations-and-csv-import.md` (new)

---

## Complete file inventory (created or modified in Milestone 9)

### Backend — `apps/api` (new billing module + subscriptions extensions)
`pyproject.toml` (added `stripe` as a real dependency),
`app/core/config.py` (added `stripe_secret_key`/`stripe_publishable_key`/`stripe_webhook_secret`/`billing_portal_return_url`/`billing_checkout_success_url`/`billing_checkout_cancel_url`),
`app/core/model_registry.py` (registered `BillingCustomer`, `BillingSubscription`, `BillingEvent`, `InvoiceRecord`),
`app/modules/billing/__init__.py`, `models.py` (new — `BillingCustomer`, `BillingSubscription`, `BillingEvent`, `InvoiceRecord`), `repositories.py` (new), `services.py` (new — `create_checkout_session`, `create_portal_session`, `handle_webhook_event`, the subscription/invoice sync logic), `schemas.py` (new), `routes.py` (new — `POST /billing/checkout-session`, `POST /billing/portal-session`, `GET /billing/invoices`, `POST /billing/webhook`),
`app/modules/subscriptions/models.py` (added `SubscriptionPlan.stripe_price_id`),
`app/modules/subscriptions/repositories.py` (added `get_subscription_for_tenant`, `update_tenant_subscription_plan`, `get_plan_by_stripe_price_id`, `list_active_plans`),
`app/modules/subscriptions/schemas.py` (added `PlanResponse`, `PlanListResponse`),
`app/modules/subscriptions/routes.py` (added `GET /billing/plans`),
`app/main.py` (registered `billing_router`),
`alembic/versions/ceb351a49d48_*.py` (new — `billing_customers`, `billing_subscriptions`, `billing_events`, `invoice_records` tables + RLS; `subscription_plans.stripe_price_id` column),
`tests/test_billing_api.py` (new, 13 tests)

### Frontend — `apps/web`
`lib/types.ts` (added `CheckoutSessionResponse`, `PortalSessionResponse`, `Invoice`, `InvoiceListResponse`, `Plan`, `PlanListResponse`),
`app/(tenant)/usage/page.tsx` (added a plan-comparison grid with real upgrade-availability state, a "Manage billing" button, and an invoice history table — no new nav item, since "Usage & Billing" already existed)

### Docs
`docs/project-status.md`, `docs/adr/0017-billing-provider-integration.md` (new)

---

## Complete file inventory (created or modified in Milestone 10)

### CI/CD
`.github/workflows/ci.yml` (new — `api`/`worker`/`connector-sdk`/`web`/`security-scan` jobs)

### Backend — `apps/api` (hardening tests only, no production code changed)
`tests/test_rls_coverage.py` (new, 2 tests — schema-introspecting RLS enable/force/policy-existence check, and RLS policy-text correctness check),
`tests/test_route_ordering.py` (new, 1 test — generic route-shadowing detector over the real, fully-assembled app route table)

### Docs
`docs/project-status.md`, `docs/adr/0018-ci-cd-and-hardening.md` (new)
