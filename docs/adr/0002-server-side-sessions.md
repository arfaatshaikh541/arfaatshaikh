# ADR-0002: Server-side database-backed sessions, not JWT

## Status
Accepted (Milestone 1 approval item #2).

## Context
Needed a session mechanism supporting instant revocation (logout,
password reset, support-access expiry) without waiting for a token's
natural expiry.

## Decision
Sessions are opaque random tokens stored client-side in an HttpOnly,
Secure (in production), SameSite=Lax cookie. The server stores a hashed
copy in the `sessions` table along with `expires_at`, `revoked_at`, and
`active_tenant_id`. Every request re-validates against this table.

## Consequences
- Instant, guaranteed revocation: setting `revoked_at` takes effect on
  the very next request, unlike a JWT which remains valid until its own
  expiry unless a separate denylist is maintained.
- Slightly more DB load per request (one extra indexed lookup by
  `token_hash`) - acceptable at Milestone 1 scale; a Redis-backed session
  cache is a future optimization if it becomes a bottleneck.
- Horizontal scaling of the API is unaffected since session state lives
  in Postgres, not in-process memory.

## Verified
Login, logout (session revocation), and password-reset-triggered
session revocation are covered in `tests/test_auth.py`.
