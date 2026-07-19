# ADR-0024: enrichment trigger and evidence UI

## Status
Accepted.

## Context
Website enrichment (crawl a business's site, run detectors, persist
evidence, surface technical opportunities) has been fully built, tested,
and documented on the backend since Milestone 4 - `POST /businesses/{id}
/enrich`, `GET /businesses/{id}/enrichment`, `GET /businesses/{id}
/evidence` all existed and were covered by real worker tests. But Milestone
4's own scope was explicitly backend-only per the captured architecture,
and `docs/project-status.md` carried "no frontend UI exists yet for
triggering enrichment or viewing evidence... a natural follow-up" as a
known limitation from that point on, unclosed through fifteen further
milestones.

No spec text in this session names Milestone 16's scope. Unlike Milestones
11-15 (all backend/worker), this one was deliberately chosen as a frontend
gap: a fully-built, fully-tested backend capability that a real user
simply cannot reach without calling the raw API by hand. That asymmetry -
more product value sitting idle than any remaining backend gap offered -
was the deciding factor.

## Decision

### One new card on the existing lead detail page, not a new route
`/leads/[id]` already shows a business's contact info, score breakdown,
and opportunities/recommendations - the natural home for "does this
business have a website worth checking, and what did checking it find."
A new "Website enrichment" `Card`, placed directly after the business-info
card, shows:
- The latest enrichment's status (`pending`/`running`/`completed`/`failed`),
  polled every 2s while non-terminal - the same `refetchInterval` pattern
  the campaign detail page already established for progress polling, so
  this is a consistent, not novel, interaction model in this codebase.
- An "Enrich website" (or "Re-enrich website", once one has run) button,
  disabled while a run is already `pending`/`running` and when the
  business has no website on file at all (nothing to crawl - shown as an
  explanatory message instead of a disabled button with no context).
- Once `completed`: pages crawled, when it finished, and every evidence
  row (detector type, source URL as a link, confidence, supporting
  snippet where one was recorded).
- Once `failed`: the real error message, never a fabricated status.

### No new backend code
Every endpoint this UI calls already existed, unchanged, since Milestone 4.
This milestone added two new frontend types (`Enrichment`,
`EnrichmentEvidence`, matching `EnrichmentResponse`/`EvidenceResponse`
field-for-field) and one page's worth of UI - no schema, service, or route
changes anywhere in `apps/api` or `apps/worker`.

### Live-verified against the real running stack, not just typechecked
Per this project's own standing rule for UI changes, this was driven
through a real, running `uvicorn`/Celery-worker/`next dev` stack in a
headless Chromium browser (Playwright), not just `pnpm typecheck`/`pnpm
build`: registered a fresh user (see "What was found" below for why not
the seeded demo account), verified email via a captured SMTP message,
onboarded a workspace, launched a real mock-connector campaign to
completion via the live worker, scored a discovered business with a
website into a lead via the real API, then clicked "Enrich website" on
the actual page and watched it poll from no-status through `completed`,
rendering one real evidence row. Screenshots of both the before and after
states were captured and visually inspected.

### What that live pass found: the fake mock-generated domains don't resolve, and that's fine
`MockConnector`-generated businesses get fabricated `.example.com`-style
websites that were never registered and don't resolve via DNS. Enriching
one of these produces a real `website_unavailable` evidence entry
(confidence 0.9) rather than a crash or a stuck task - the crawler's own
"site unreachable" handling (ADR-0012) is not a failure mode, it's a
normal, correctly-represented outcome, and this UI displays it exactly
like any other evidence row. This is expected and correct; a real
business's real, reachable website would produce richer evidence (contact
methods, social links, missing-viewport findings, etc.) exactly as
`test_enrichment_tasks.py`'s own mocked-transport tests already prove
against fixture HTML.

### An unrelated, real bug found while setting up for this verification: the seeded demo accounts cannot log in
Attempting to log in as the seeded demo tenant's `owner@northstar-demo.
gridkeep.local` through the real `/auth/login` endpoint failed with a
generic `422 The request payload is invalid` - traced to Pydantic's
`EmailStr` (via the `email-validator` package) rejecting `.local` as a
reserved, special-use TLD at the syntax-validation layer, before the
request body is ever passed to any service code. Every demo-tenant email
address seeded since Milestone 1 (`SUBSCRIPTION_PLANS`'s sibling constants
`DEMO_TENANT_USERS`/`PLATFORM_DEMO_USER` in `app/seed/seed_data.py`) uses
this `.local` TLD, meaning **the entire demo tenant has never actually
been able to log in through the real API** - every prior milestone's own
live-verification passes (per their own write-ups) always registered a
fresh `@example.com`-style user through the real signup flow instead,
never the seeded demo accounts, which is presumably why this went
unnoticed for fifteen milestones. This session's own verification did the
same (registered a fresh user) rather than fix the seed data, since it is
unrelated to this milestone's actual scope - recorded here and in
`docs/project-status.md` as a new, disclosed, not-yet-fixed limitation for
a future milestone.

## Consequences
- New: nothing in `apps/api`/`apps/worker`.
- Modified: `apps/web/lib/types.ts` (`Enrichment`, `EnrichmentEvidence`,
  `EnrichmentStatus`), `apps/web/app/(tenant)/leads/[id]/page.tsx` (the
  new card, its queries, and the trigger handler).
- Closes `docs/project-status.md`'s "no frontend UI exists yet for
  triggering enrichment or viewing evidence" known limitation in full.
- New disclosed limitation: the seeded demo tenant's `.local` email
  addresses cannot log in through the real API (`EmailStr` rejects the
  TLD) - found incidentally, not fixed this milestone, since it is
  unrelated to enrichment and a real fix (picking a different placeholder
  domain scheme for seed data) deserves its own small, reviewable change
  rather than being folded into this one.
- The enrichment card's evidence list is a flat, unfiltered rendering of
  every `EnrichmentEvidence` row for the business - reasonable at the
  volume a single crawl produces (a handful of detector findings across a
  handful of pages), but not paginated or grouped by page/detector type;
  worth revisiting if a future milestone's crawl scope grows significantly
  larger than today's fixed candidate-page-set bound (see ADR-0012).
