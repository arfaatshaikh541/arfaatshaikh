# ADR-0027: bulk "score all businesses" action

## Status
Accepted.

## Context
Lead scoring (`POST /businesses/{id}/score`, Milestone 5) has always been
manual and per-business - a campaign's discovered businesses don't
automatically become scored leads, and there was no way to score more
than one at a time. `docs/project-status.md` carried this as known
limitation #18 since Milestone 6: "A 'score all businesses from this
campaign' bulk action or an automatic post-discovery scoring trigger is
natural follow-up work, not built in Milestone 5 or 6."

Milestone 18 closed the last disclosed *bug* (the seeded demo tenant's
unusable email domain). This limitation is the last remaining disclosed
gap that is both a genuine, actionable feature gap (not a by-design
tradeoff) and credential-free - every other open item is blocked on
external credentials or infrastructure this sandbox doesn't have.

## Decision

### A bulk action scoped to a campaign, not an automatic trigger
Of the two options limitation #18 named, this milestone builds the bulk
*action* (`POST /campaigns/{campaign_id}/score-businesses`), not an
automatic post-discovery trigger. An automatic trigger changes campaign
behavior for every tenant unconditionally (every discovered business
becomes a scored Lead the instant it's found, whether or not the user
wants that) and has no natural place to be toggled off - a bigger,
riskier change than the captured requirements justify. An explicit,
user-initiated bulk action is the smaller, safer implementation of the
same limitation, consistent with this project's "don't invent
requirements beyond what's asked" rule; an automatic trigger remains
available as a future, separately-scoped enhancement if wanted.

### Reused `scoring.score_lead` in a loop, no new persistence logic
`app/modules/leads/scoring.py` gained one new function,
`score_businesses_for_campaign(session, campaign_id)`: it calls
`businesses_repo.list_businesses_for_campaign` (the same canonical-only,
non-merged-away query `GET /campaigns/{id}/businesses` already uses) and
runs `score_lead` once per business, returning the full list of
`(lead, score, opportunities, recommendations)` tuples. It does not
commit - callers commit once, after scoring every business, mirroring the
existing single-business route's "pure computation, no network, stays
synchronous" reasoning (ADR-0013). No new tables, no migration - this
milestone is a new service function, one new route, and one new response-
building helper.

### `ScoreLeadResponse.from_score_result` - a small DRY refactor, not new behavior
The single-business route (`POST /businesses/{id}/score`) inlined its own
response-building logic. That logic is now a classmethod,
`ScoreLeadResponse.from_score_result(lead, score, opportunities,
recommendations)`, reused by both the single-business route (refactored,
behavior unchanged, still covered by its own existing tests) and the new
bulk route. This follows the same `from_model`/`from_score_result`
classmethod convention already used throughout `leads/schemas.py` and
`businesses/schemas.py`.

### Route placement: on the campaigns router, permission-gated the same as the single action
`POST /campaigns/{campaign_id}/score-businesses` sits on the campaigns
router next to the existing `GET /campaigns/{id}/businesses`, gated by the
same `leads.score` permission the single-business endpoint already uses -
no new permission was added. Every business a campaign discovered is
scored in one request; a business that already has a `Lead` is simply
re-scored (a new `LeadScore` row, same as calling the single endpoint
again - re-scoring was already idempotent-in-effect before this
milestone).

### Frontend: one button on the campaign detail page
A "Score all businesses" button appears on `/campaigns/[id]` once
`progress.businesses_found > 0` (any point after discovery has found at
least one business, not gated on the campaign reaching a terminal
status - scoring is pure computation over already-persisted data, so
there's no reason to make a user wait for `completed`). Clicking it calls
the new endpoint and shows a "Scored N businesses into leads." success
banner, following the same `runAction`-adjacent pattern (`actionError`/
`pendingAction`) every other action on this page already uses. This is a
deliberately small addition - unlike Milestones 16/17, which each added a
whole new card, this is one button because the "review the result"
surface (the score breakdown, per-lead) already exists in full on
`/leads/[id]`, built in Milestone 6; there is nothing new to render here
beyond confirming the action happened and how many leads it produced.

### Live-verified against the real running stack
Per the standing rule for UI changes, this was driven through a real
`uvicorn`/Celery-worker/`next dev` stack in headless Chromium
(Playwright): registered a fresh user, launched a real mock campaign to
completion via the live worker (8 businesses discovered), confirmed the
"Score all businesses" button is genuinely absent before any business is
discovered and appears once discovery completes, clicked it, watched the
real "Scored 8 businesses into leads." banner, then navigated to `/leads`
and confirmed all 8 businesses appear there as real, individually-scored
leads (distinct scores, not a placeholder). Screenshots of the before/
after states and the resulting lead list were captured and visually
inspected.

## Consequences
- New: `app/modules/leads/scoring.py`'s `score_businesses_for_campaign`;
  `POST /campaigns/{campaign_id}/score-businesses` route;
  `ScoreLeadResponse.from_score_result` classmethod;
  `apps/web/lib/types.ts`'s `ScoreLeadResult` type; the "Score all
  businesses" button on `/campaigns/[id]`.
- Modified (refactor only, no behavior change): `POST /businesses/{id}
  /score` now calls the same new classmethod instead of inlining response
  construction.
- Closes `docs/project-status.md` known limitation #18's bulk-action half
  in full. The automatic-trigger half remains explicitly not built, by
  the same reasoning ADR-0013 and this ADR both give for not inventing
  requirements beyond what was asked.
- New tests: two service-level tests (`test_lead_scoring.py`) proving the
  bulk function scores every canonical business and correctly excludes a
  merged-away business under its own id; one HTTP-level test
  (`test_campaign_engine.py`) proving the route is wired correctly and
  gated by `leads.score` (a Read-Only Viewer is denied).
- A campaign with a very large `result_limit` scored via this endpoint
  runs entirely within one synchronous request/transaction - reasonable
  at the volumes this codebase's own campaigns operate at (tens of
  businesses, matching every prior milestone's own test/verification
  scale), but a future milestone significantly raising typical campaign
  size would need to revisit whether this should become a background job
  instead, the same tradeoff already made once for exports (ADR-0015)
  and CSV import (ADR-0016).
