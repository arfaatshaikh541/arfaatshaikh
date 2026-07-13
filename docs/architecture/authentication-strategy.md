# Authentication Strategy

## Password Storage

- Argon2id via `argon2-cffi`, tuned to OWASP-recommended parameters
  (`time_cost=3`, `memory_cost=65536` KiB, `parallelism=4`), wrapped in
  `passlib`-style verify/needs-rehash helpers in `app/core/security.py`.
- Passwords are never logged, never returned in API responses, never
  included in audit log metadata.

## Tokens & Cookies

Two cookies, both `HttpOnly`, `Secure` (in non-local environments),
`SameSite=Lax`:

- `access_token` — short-lived (15 min) signed JWT (`HS256`, secret from
  environment/secrets manager), payload limited to `{sub: user_id, sid:
  session_id, exp, iat}`. No roles/permissions/tenant claims are embedded,
  because those must always be re-derived fresh from the database (see
  tenant isolation strategy) to support instant revocation and role
  changes taking effect immediately.
- `refresh_token` — long-lived (30 days), a high-entropy random opaque
  string (`secrets.token_urlsafe(48)`). Only its SHA-256 hash is stored
  server-side, in the `sessions` table, so a database read alone cannot be
  used to forge a session.

A third, non-`HttpOnly` cookie `csrf_token` is set alongside the auth
cookies; the frontend echoes its value back in an `X-CSRF-Token` header on
every mutating request (`POST/PUT/PATCH/DELETE`). The backend rejects the
request if the header doesn't match the cookie (double-submit pattern).
`GET` requests are exempt (must be side-effect-free), as are
`/api/auth/login`, `/api/auth/refresh`, `/api/auth/logout`,
`/api/auth/forgot-password`, `/api/auth/reset-password`,
`/api/auth/verify-email`, and `/api/invitations/accept` — each of these
either carries no ambient session yet (login, forgot/reset/verify) or the
cookie being read (`refresh_token`) is itself the one-time credential
presented for that exact action rather than ambient authority used to
authorize an unrelated state change. Every other mutating,
cookie-authenticated endpoint (settings, roles, members, invitations
create/revoke, etc.) enforces the check.

## Refresh Rotation & Reuse Detection

- `POST /api/auth/refresh` consumes the current `refresh_token`, verifies
  its hash against an unrevoked, unexpired `sessions` row, then:
  - Marks that session row `revoked_at = now()`.
  - Creates a new session row, links it via `replaced_by_id`.
  - Issues a new `access_token` + `refresh_token` pair.
- If a client presents a refresh token whose session row is already
  `revoked_at IS NOT NULL` (i.e. it was already rotated away), this is
  treated as **token reuse** — a signal of theft — and the entire session
  family for that user is revoked, forcing re-login everywhere. This event
  is written to `audit_logs`.

## Session Revocation

- `POST /api/auth/logout` revokes the current session row and clears
  cookies.
- `GET /api/auth/sessions` / `DELETE /api/auth/sessions/{id}` let a user
  view and revoke other active sessions/devices (settings > security).
- An admin action ("force logout user") revokes all of a user's sessions;
  used e.g. after a role change or suspected compromise.

## Email Verification

- On registration (via invitation acceptance — there is no open public
  self-registration in v1, per the invitation-based membership model), an
  `email_verification_tokens` row is created and an email sent with a
  single-use, hashed, expiring (24h) link. Unverified accounts can log in
  (so they aren't locked out) but are flagged `email_verified_at IS NULL`;
  certain sensitive actions can require verification later if needed.

## Password Reset

- `POST /api/auth/forgot-password` always returns a generic `200` success
  response regardless of whether the email exists, to avoid user
  enumeration. If the user exists, a `password_reset_tokens` row + email
  is created (1h expiry, single use).
- `POST /api/auth/reset-password` validates the token hash + expiry,
  updates the password, revokes **all** existing sessions for that user
  (a reset is a strong signal the old sessions may be compromised).

## Two-Factor Authentication (Architecture Only, v1)

- Schema support only in Milestone 1: `users.two_factor_enabled`,
  `users.two_factor_secret_encrypted` (AES-encrypted TOTP secret, key from
  secrets manager, never returned via API once set).
- Full TOTP enrollment/verification endpoints are out of scope for
  Milestone 1 and are called out as not-yet-implemented in the
  Milestone 1 limitations section rather than half-built.

## Login Rate Limiting

- `login_attempts` table records every attempt (email, IP, success,
  timestamp). `POST /api/auth/login` checks, per email+IP, the count of
  failed attempts in the trailing 15 minutes; beyond 5, it responds `429`
  regardless of whether the credentials would have been correct.
- `users.failed_login_count` / `users.locked_until` provide a
  per-account lockout after repeated failures, independent of IP, so an
  attacker can't defeat IP-based limiting by rotating source addresses.
- All authentication failures return the same generic message
  ("Invalid email or password") — never "user not found" vs "wrong
  password" — to prevent enumeration.

## CORS

- `apps/api` restricts `Access-Control-Allow-Origin` to the configured
  frontend origin(s) from environment config, `allow_credentials=True`
  (required for cookies), and an explicit allow-list of methods/headers.
  No wildcard origins when credentials are allowed (browsers reject that
  combination anyway, but we assert it explicitly in config validation).
