# GRIDKEEP Lead Intelligence — Project Status

## Current milestone
**Milestone 4: Website Enrichment** — implementation complete, including a real Business persistence layer that Milestone 2 was missing and Milestone 4 needed as a prerequisite (see the Milestone 4 section below and ADR-0011). One caveat carried over from Milestone 3's pattern: the SSRF-safe crawler has not been exercised against a real external website in this sandbox (its own egress policy blocks general internet access) — see ADR-0012 and **Known limitations**. Pending your review before proceeding to Milestone 5.

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
| Every score/estimate is explainable | ✅ `EstimateResponse` exposes `estimated_credits`/`estimated_results`/`calculated_at`; lead *scoring* itself is a later milestone |
| Backend tests pass | ✅ 35/35 (api) + 52/52 (worker) + 22/22 (connector-sdk) = 109/109 |
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

## Architecture decisions
See `docs/adr/0001` through `0012`. Summary: shared-schema+RLS multi-tenancy, server-side sessions, `uv`/`pnpm` tooling, campaign-level credit-reservation granularity, MFA scaffolded only, no billing provider selected yet, a documented RLS ordering rule + `platform_bypass` escape-hatch pattern (0007), campaign entity consolidation vs. the original architecture's larger entity list (0008), a documented per-task event-loop isolation rule for the worker's async DB/Redis clients (0009), the Google Places connector's design plus its explicit live-verification gap (0010), the Business entity consolidation and the Milestone 2 persistence gap it fixes (0011), and the SSRF-safe crawler's design plus its own explicit live-verification gap (0012).

## Known limitations

1. **Docker Compose stack not verified end-to-end in this build environment.** This session's outbound network egress policy blocks Docker Hub image pulls (`production.cloudfront.docker.com` returns a 403 policy denial), so `docker compose up` could not be run here. All verification instead ran the same services natively: PostgreSQL 16 and Redis were already installed in this sandbox and used directly; the FastAPI app, Celery worker, and Next.js dev server were run directly via `uv run` / `pnpm dev`. The `docker-compose.yml` and Dockerfiles are believed correct (they mirror the exact configuration verified natively) but **you should run `docker compose up` yourself before relying on it** — that is the one meaningful gap between "verified" and "should work."
2. **MFA is scaffolded, not enrollable** (ADR-0005) — by design, per your approval.
3. **No billing provider integration** (ADR-0006) — by design, per your approval; plans/credits are seed data today.
4. **RLS discipline is manual today.** The ordering rule in ADR-0007 (`set_tenant_context` before any RLS-protected query) is not enforced by a linter or CI check — a future service function could reintroduce the same class of bug if the rule isn't followed. Milestone 2's worker code hit the exact same class of bug again (`worker.campaign_tasks._run_campaign_task_async`'s first lookup needed `set_platform_bypass` before its first read, same as ADR-0007's examples) before being fixed — this remains a manual-discipline risk, not an automated one.
5. **No CI/CD pipeline yet.** GitHub Actions workflows (lint/test/build/scan on push) have not been created.
6. **Object storage (MinIO) is configured but unexercised.** No file-storage feature exists yet (exports are a later milestone), so the S3 client configuration exists in `core/config.py` but was never actually connected to in verification.
7. **Frontend uses hand-written types** (`apps/web/lib/types.ts`), not OpenAPI-generated ones — reasonable at this API-surface size; `packages/shared-types` is reserved for generated types later (see its README).
8. **`google_places` has never made a real call to Google's API (Milestone 3, ADR-0010).** No Google Cloud API key was available during implementation. The connector is built against Google's documented Places API (New) contract and covered by 22 mocked-HTTP-transport tests, but that is not the same as proof it works against Google's real servers — if any assumption about Google's actual response shape is wrong in a way the mocked tests didn't anticipate, it will only surface on first live use. **Before launching any real campaign against this connector**: obtain a Google Cloud API key with the Places API (New) enabled and billing configured, set `GOOGLE_PLACES_API_KEY`, and run a manual smoke test (a single real `search()` call, inspected by a human) before pointing a real tenant's campaign at it.
9. **`google_places` is not exposed in the frontend campaign-creation form.** Only `mock` is offered there today — deliberate, per ADR-0010, since offering a connector that can only fail without a real key would be poor UX, not a missing feature.
10. **No automated test exercises a real connector error path end-to-end through the worker's retry logic** (auth/quota/rate-limit/permanent failure and the retry backoff that follows). Milestone 3's mocked-adapter tests verify `GooglePlacesConnector` itself raises the right error type for each Google API error shape, but nothing yet drives `worker.campaign_tasks.run_campaign_task`'s actual retry/backoff loop end-to-end with an injected connector failure. A fault-injecting test connector (or a flag on `MockConnector` to simulate failures) is recommended as an early follow-up.
11. **The dev sandbox's own long-running processes (Postgres, Redis, the SMTP capture server, the Celery worker, the API/web dev servers) were repeatedly reaped during idle gaps in this session** and had to be restarted more than once mid-verification. This is a property of this particular sandboxed environment, not the application, but it's worth knowing if you see "connection refused" locally after leaving a dev environment idle — check that all four services are actually still running before assuming something is broken.
12. **The SSRF-safe crawler has never crawled a real external website (Milestone 4, ADR-0012).** This sandbox's egress policy blocks general internet access outright — confirmed directly (a raw request to a real domain and this crawler's own direct-IP-connect strategy were both rejected by the proxy with policy-level 403s). SSRF-blocking itself is verified against real DNS resolution (not mocked); fetch mechanics and the full crawl/detector/enrichment pipeline are verified against a real Postgres database with a mocked HTTP transport. **Before relying on this crawler against real business websites**, smoke-test it against a small set of real, known-safe external sites from an environment without this sandbox's restrictive egress policy.
13. **No frontend UI exists yet for triggering enrichment or viewing evidence.** Milestone 4's scope (per the original architecture) is backend-only (crawler, detectors, evidence storage); `POST /businesses/{id}/enrich` and the evidence/enrichment-status endpoints exist and are tested, but nothing in `apps/web` calls them yet — a `/campaigns/[id]` business list with an "Enrich" action is natural follow-up UI work, not part of this milestone's own line items.

## Unresolved risks

- **`google_places` has never been called live (ADR-0010).** Everything about this connector's correctness against Google's real API rests on documentation-reasoning plus mocked-HTTP tests, not a live call. Treat it as unverified until a real key is supplied and a manual smoke test is run — do not launch a real tenant's campaign against it first.
- **The website enrichment crawler has never crawled a real external website (ADR-0012) — the equivalent open risk for this milestone.** Same shape of gap as the Google Places connector: correct by documentation-reasoning and mocked-transport tests, not by a live crawl. If a real website's actual behavior (redirect chains through a CDN, unusual robots.txt syntax, a non-UTF-8 encoding, a slow server near the timeout boundary) differs from what the mocked tests anticipate, it will only surface on first live use.
- **Connection-pool GUC leakage class of bug** (ADR-0007): fixed everywhere it was found by manual audit, but the codebase has no automated guard against a *future* service function making the same mistake — and Milestone 2 proved this risk is real by reintroducing it once (see limitation #4 above). Recommend a lightweight integration test pattern (assert a fresh session with no context set returns zero rows for every RLS table) as a standing regression test.
- **Per-task event-loop isolation** (ADR-0009): the worker's `run_db_task` helper is the only thing preventing every new Celery task from silently inheriting a previous task's closed-loop database/Redis/HTTP connections — now proven to matter a third time by the crawler's own per-fetch-client discipline (ADR-0012), after `GooglePlacesConnector` (ADR-0010). Like the RLS ordering rule, this is a discipline documented in ADRs and code comments, not something a linter enforces — a future async client added the naive way (a cached instance-scoped `httpx.AsyncClient`, a persistent connection of any kind) would reintroduce exactly this bug, and it would only surface once a worker process handles a second task, making it easy to miss in a quick manual check.
- **Single shared Postgres instance**: no read replica, no connection-pool sizing exercise under real background-job write load now that the campaign engine exists. A real concern once campaign volume grows.
- **Rate limiting is IP/account-keyed only**, no distributed abuse detection. Adequate for now.
- **No connector-error-path test coverage through the worker's own retry loop** (see limitation #10) — `GooglePlacesConnector` itself is tested to raise the right error types, but nothing yet drives `run_campaign_task`'s retry/backoff/permanent-failure handling end-to-end with an injected failure.
- **`Business.field_provenance` is JSONB, not a normalized table (ADR-0011).** Fine for every current read pattern (always "the whole provenance record for this business"), but a future feature needing to query/filter provenance across businesses by field or source would need it moved into a real table at that point.

## Pending approvals
None outstanding. Milestone 4's scope (website enrichment, per the original architecture) was implemented under the standing "Proceed" instruction, including the Business persistence prerequisite it surfaced along the way. ADR-0011 documents that prerequisite's design; ADR-0012 documents the crawler's SSRF-safety design and, explicitly, its unresolved live-crawl-verification gap — same pattern as ADR-0010 for Milestone 3, called out here for transparency rather than requiring separate approval, since it's the recommended default path when general internet access isn't available in this environment.

## Next action
Awaiting your review of Milestone 4. When ready, let me know how you'd like to proceed — including whether you'd like Milestone 5 (Deduplication and Lead Intelligence) started next, per the original architecture's milestone order.

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
