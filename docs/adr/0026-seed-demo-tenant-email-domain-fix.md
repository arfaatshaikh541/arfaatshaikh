# ADR-0026: fix the seeded demo tenant's unusable email domain

## Status
Accepted.

## Context
Milestone 16's own live-verification pass found that logging in as the
seeded demo tenant's `owner@northstar-demo.gridkeep.local` through the
real `/auth/login` endpoint failed with a generic `422`. The root cause,
traced at the time: Pydantic's `EmailStr` (via `email-validator`) rejects
`.local` as a reserved, special-use TLD at the request-validation layer,
before any service code runs. Every demo-tenant email address seeded
since Milestone 1 (`app/seed/seed_data.py`'s `DEMO_TENANT_USERS` and
`PLATFORM_DEMO_USER`) used this TLD - meaning the entire demo tenant had
apparently never been able to log in through the real API in this
project's history. Every prior milestone's own live-verification pass
worked around it by registering a fresh `@example.com`-style user through
the real signup flow instead of using the seeded accounts, which is
presumably why this went unnoticed for fifteen milestones. It was
disclosed as known limitation #41 and deliberately left unfixed in
Milestone 16, since it was unrelated to that milestone's scope.

No spec text in this session names Milestone 18's scope. This was chosen
because it is the last remaining known limitation that is both genuinely
actionable (a real bug, not a "by design" tradeoff) and credential-free -
every other open item (Google Places live verification, Stripe live
verification, a live crawl, live webhook delivery, a real MinIO/Docker
deployment) is blocked on external credentials or infrastructure this
sandbox does not have.

## Decision

### Change the placeholder domain, not the validation rule
The fix is entirely in `apps/api/app/seed/seed_data.py`: every demo email
address's domain changes from `*.gridkeep.local` /
`gridkeep-platform-demo.local` to `*.gridkeep-demo.example.com` /
`gridkeep-platform-demo.example.com`. `example.com` is RFC 2606's reserved
documentation domain - a real, non-special-use TLD (`.com`) that
`EmailStr` accepts, while the domain itself remains obviously fictional
and is never expected to receive real mail (this codebase's SMTP client is
only ever pointed at a local dev/test capture server, never a real relay,
for every environment this seed script is meant to run in).

The alternative - relaxing or special-casing `EmailStr`'s TLD validation
so `.local` addresses pass - was rejected: it would weaken real input
validation for every real user's registration email to accommodate seed
data, trading a correctness guarantee for convenience. Fixing the seed
data's own placeholder scheme is the smaller, more correct change.

`core/config.py`'s unrelated `smtp_from_email` default
(`no-reply@gridkeep.local`) and `.env.example`'s matching value were left
untouched - that field is typed `str`, not `EmailStr`, is only ever used
as an outbound SMTP "From" header (never round-tripped through any
request validation), and is unrelated to the disclosed bug.

### Existing seeded rows are additive, not replaced
The seed script's idempotency is keyed on natural key (email address per
user). Re-running it after this change does not delete or rename the old
`*.gridkeep.local` rows already present in a database seeded before this
fix - it inserts five new rows under the new domain alongside them. This
is the seed script's existing, by-design behavior (unchanged by this
milestone) and is the correct outcome: a fresh database seeded from
scratch only ever gets the new, working addresses; a database seeded
before this fix keeps its old orphaned rows undisturbed rather than having
data silently renamed out from under it.

### Live-verified with a real login
Restarted the real `uvicorn` server, re-ran the seed script against the
dev database, and sent a real `POST /auth/login` for both
`owner@northstar-demo.gridkeep-demo.example.com` and
`platform-admin@gridkeep-platform-demo.example.com` with the documented
demo password - both returned `200` with a real session cookie, proving
the fix works end-to-end through the actual validation layer that
originally rejected them. The old `owner@northstar-demo.gridkeep.local`
row was also re-tested and still correctly 422s (unrelated orphaned data,
not deleted, not expected to work).

## Consequences
- New: `docs/adr/0026-seed-demo-tenant-email-domain-fix.md`.
- Modified: `apps/api/app/seed/seed_data.py` only - no schema change (no
  migration), no other module touched.
- Closes known limitation #41 in full: the seeded demo tenant can now log
  in through the real API.
- A database that was seeded before this fix (including this sandbox's
  own dev database) retains its old `*.gridkeep.local` rows as inert,
  unreachable leftovers alongside the new working ones - harmless, but
  worth knowing if you're inspecting `users` directly rather than through
  the API.
