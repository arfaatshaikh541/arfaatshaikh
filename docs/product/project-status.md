# Project status

**Current milestone:** Milestone 10 — Security & Compliance Hardening
**Status:** Complete, verified against a real PostgreSQL + Redis stack. This was the final milestone in the original 10-milestone plan — awaiting your review.
**Last updated:** 2026-07-15

---

## What was built (Milestone 10)

This milestone closes out the three items `docs/security/README.md` had
flagged as deferred since Milestone 1: platform-wide rate limiting
(previously login-only), a double-submit CSRF token for state-changing
requests (previously relying on `SameSite=Lax` alone), and a dependency
vulnerability audit pass.

*Correction while writing this milestone's doc: Milestone 9's entry
claimed "172 total" tests — that was a miscount at the time; the actual
`pytest` run that milestone showed 158 passed. Recorded correctly below.*

### Backend (`apps/api`)
- **New `app/dependencies/security.py`**, holding both new cross-cutting request guards as ordinary FastAPI dependencies — deliberately *not* Starlette middleware, because an exception raised inside `add_middleware`/`@app.middleware("http")` code sits outside the zone `register_exception_handlers` protects and would produce a raw 500 instead of a proper JSON error body; a `Depends()` executes inside that zone.
- **Global rate limiting** (`enforce_global_rate_limit`): a generous, IP-keyed, Redis-backed fixed window (300 requests / 60 seconds by default, both configurable) applied to every `/api/*` route via `api_router`'s own `dependencies=[]` — public and authenticated routes alike, since the public surfaces (lead capture, booking, proposal accept/reject, document upload) are exactly the ones most exposed to basic flooding. This sits *on top of*, not instead of, the pre-existing tighter, action-specific login and portal-login throttles.
- **Double-submit CSRF protection** (`enforce_csrf_protection`): a non-`httponly` `cops_csrf` cookie is now issued alongside every staff and portal session cookie (one shared cookie name across both auth domains — double-submit correctness doesn't require per-domain separation), and every mutating request on an authenticated router must echo it back as an `X-CSRF-Token` header. A cross-site attacker's script cannot read the cookie's value (same-origin policy), so it cannot forge a matching header even for a request the browser does attach the cookie to.
  - **Skipped when no session cookie is present** — this alone correctly exempts login, forgot-password, reset-password, and accept-invitation (no session exists yet at that point) without any special-casing, while still protecting every mutation that does ride on an existing session, including logout.
  - **Public routers are unconditionally exempt**, registered without the CSRF dependency at all — relying on the "no cookie" heuristic alone would produce a false-positive 403 for a staff member testing a public page in the same browser where they also happen to be logged into the tenant admin (the browser attaches same-origin cookies regardless of which page initiated the request).
- **`main.py` router registration restructured** into `public_routers` (no CSRF dependency: lead capture, booking, proposal accept/reject, document upload) and `protected_routers` (CSRF dependency added at `include_router()` time: everything else, including both auth routers, platform admin, and all tenant/portal-content routes). The global rate limiter applies uniformly to both groups via the parent `api_router`.
- **CORS `allow_headers` extended** with `X-CSRF-Token` so the browser's preflight `OPTIONS` request succeeds before the real mutating request goes out.
- **Zero new database migrations or permission codes** — this milestone is entirely a request-guard layer; no schema changed.
- **8 new pytest tests** (166 total, up from 158): CSRF rejection on a missing header and on a wrong header (both while a valid session cookie is present), successful CSRF-protected logout with the correct header, safe methods never being CSRF-checked, the check being skipped with no session cookie at all, a public route staying reachable even with an *unrelated* ambient staff session cookie present, the global limiter tripping at the configured threshold, and the limiter's own enable/disable kill switch.
- **A dependency audit that found and fixed one real issue**: `npm audit` on the frontend reported a moderate-severity XSS advisory ([GHSA-qx2v-qp2m-jg93](https://github.com/advisories/GHSA-qx2v-qp2m-jg93)) in `postcss`, reachable only through a version (`8.4.31`) that Next.js 15.5.20 pins internally for its own build-time CSS processing — not a version we control via `package.json`, and npm's own suggested fix was a nonsensical major downgrade of Next itself (15 → 9). Fixed properly with npm's `overrides` field (`"postcss": "^8.5.10"` in the root `package.json`), which forces the same already-patched `8.5.19` used everywhere else in the tree into Next's internal copy too — required a full `node_modules` + `package-lock.json` regeneration for npm to actually apply it (a plain `npm install` left a stale lockfile-pinned nested entry in place). Verified: `npm audit` now reports zero vulnerabilities, and the full `tsc`/`eslint`/`next build`/`vitest` suite still passes against the overridden version. `pip-audit` against the API's (and worker's, which shares the same virtual environment) full dependency set found zero vulnerabilities — no Python-side changes were needed.

### Frontend (`apps/web`)
- `lib/api-client.ts` gained `getCsrfToken()` (reads the non-`httpOnly` `cops_csrf` cookie) and now automatically attaches `X-CSRF-Token` on every non-`GET` request made through the shared `api` client.
- The three raw `fetch()` calls that bypass `api-client.ts` for `multipart/form-data` file uploads — staff lead attachments, staff document-request uploads, and the client portal's own document upload — were each updated to read and attach the same header. The fourth raw `fetch()` (the fully public, unauthenticated document-upload-by-token page) was deliberately left unchanged, since it's one of the exempt public routes and carries no session cookie to forge in the first place.
- `package.json` gained the `postcss` version override described above (no application code changes).

### Tests & verification
- `ruff check app` — 0 errors. `pytest -q` — 166 passed. `eslint` — 0 errors. `tsc --noEmit` — 0 errors. `next build` — succeeds, 51 routes. `vitest run` — 4 passed.
- `pip-audit` — 0 known vulnerabilities. `npm audit` — 0 vulnerabilities (down from 2 moderate, fixed as described above).
- No new Alembic migrations this milestone (none needed).
- Manually smoke-tested over real HTTP with the API server actually running: logged in as the seeded platform admin and confirmed a mutating request (`POST /auth/logout`) without the CSRF header returned 403 `csrf_token_invalid` and left the session valid; the identical request with the correct header returned 204 and genuinely revoked the session; confirmed `GET /auth/me` (a safe method) never requires the header; confirmed the public capture route succeeds with no session and no CSRF header at all; confirmed the CORS preflight for a cross-origin mutating request now allows `X-CSRF-Token`; and, with the global rate limit temporarily tightened via environment variable to 5 requests/60s, confirmed the first 5 requests to a public route succeeded and the 6th returned 429 `rate_limited` with an accurate `Retry-After`-style message.

## Acceptance criteria — verified

| Criterion (from your Milestone 10 spec) | Verified how |
|---|---|
| Platform-wide rate limiting, not just login | `enforce_global_rate_limit` applied to every `/api/*` route via the parent router; verified live and by automated test |
| CSRF protection for state-changing requests | Double-submit `cops_csrf` cookie + `X-CSRF-Token` header, enforced on every mutating request on every authenticated router; verified live and by automated test |
| Public/unauthenticated flows keep working unmodified | Public routers unconditionally exempt from CSRF; global rate limit still applies to them (they're the most exposed surface); verified live and by automated test |
| Dependency vulnerability audit | `pip-audit` (API + worker) and `npm audit` (frontend) both run; the one real finding was fixed, not just documented; both tools now report zero vulnerabilities |
| No regression to any of the previous 9 milestones' behavior | Full existing 158-test suite passes unmodified against the new request guards — the test client's `conftest.py` fixture was updated to auto-sync the CSRF header exactly the way a real frontend does, so no individual test needed rewriting |

## Known limitations

1. **Dependency scanning is manual, not yet a CI gate.** `pip-audit`/`npm audit` were run by hand this milestone and the one real finding was fixed; wiring either (or both) into the CI pipeline as an automated, blocking or reporting step is a natural, small follow-up — this repository's CI configuration itself was outside this milestone's scope.
2. **The global rate limit is IP-keyed, not user-keyed.** Multiple legitimate users behind the same corporate NAT/proxy share one counter. This is an accepted trade-off for a first pass — a smarter, session-aware limiter (keying authenticated requests by user id instead of IP) is a reasonable future refinement, not a blocker.
3. **No formal penetration test or third-party security review** — out of scope for this sandbox; flagged in `docs/security/README.md` as something to commission before a real commercial launch.
4. **Webhook signature verification** remains unimplemented, since no outbound webhooks exist yet in this codebase (relevant only if a future milestone adds third-party integrations).
5. **The CSRF cookie is shared across the staff and portal auth domains** by design (a single `cops_csrf` cookie name, refreshed by whichever login happened most recently) — this is intentional and doesn't weaken the protection (double-submit correctness only requires that *a* legitimate same-origin script can read and echo the value), but it's worth noting explicitly since every other cookie in the system is domain-specific (`cops_session` vs `cops_portal_session`).
6. **Same environment caveats as Milestones 1–9 carry forward**: Docker Compose itself was not run end-to-end in this sandbox; all verification used the same application code run directly against local PostgreSQL 16 + Redis 7, including a real running `uvicorn` instance for the live HTTP smoke tests. No browser was available to visually confirm the frontend CSRF header is actually attached by real browser `fetch` calls (verified instead by code review of `api-client.ts` plus the equivalent server-side automated/live tests).

## Pending decisions

None new this milestone. Carried forward and still open, none blocking: Milestone 1's tenant-URL routing and production email/storage provider choice; Milestone 7's malware-scanning production integration (ClamAV vs. a cloud AV API); this milestone's own CI-wiring-for-dependency-scanning follow-up (Known limitation 1); and commissioning a formal penetration test before a real commercial launch (Known limitation 3).

## Next action

Milestone 10 was the last milestone in the original 10-milestone plan. Awaiting your review — let me know if you'd like a live walkthrough of any part of the platform, want to discuss what an 11th milestone (further integrations, billing, reporting, etc.) might look like, or consider the build complete for now.
