# ADR 0003: Session and MFA Model

## Status
Accepted (Milestone 1)

## Decision
- Passwords: Argon2id via `golang.org/x/crypto/argon2`, cost parameters configurable via
  `ARGON2_MEMORY_KIB` / `ARGON2_ITERATIONS` / `ARGON2_PARALLELISM`, encoded in the stored hash
  string so past hashes remain verifiable if the configured cost changes later.
- Sessions: opaque 256-bit random tokens (raw token to the client via an HttpOnly, SameSite=Lax
  cookie; only the SHA-256 hash is persisted in Postgres). Validated on every request directly
  against the `sessions` table (no JWT, no client-side session state) so revocation is
  immediate and absolute -- reset a password or log out, and the session is unusable on the
  very next request, not just after a token expiry window.
- CSRF: double-submit cookie (`gridkeep_csrf`, non-HttpOnly, echoed by the frontend in
  `X-CSRF-Token`). Verified in `internal/app/csrf_test.go`.
- Login lockout: a `login_attempts` log table counted over a rolling window
  (`LOGIN_LOCKOUT_THRESHOLD` / `LOGIN_LOCKOUT_WINDOW_MINUTES`), checked *before* the password
  comparison even runs, so a locked-out account gets the same generic rejection regardless of
  whether the supplied password happens to be correct.
- MFA: TOTP (RFC 6238) via `github.com/pquerna/otp`, secret encrypted at rest with AES-256-GCM
  (`MFA_ENCRYPTION_KEY`). A successful password check for an MFA-enabled account issues a
  short-lived, single-use MFA challenge token (not a session) that must be exchanged for the
  real session via a valid TOTP code.
- Timing/enumeration: a login attempt against a non-existent email still runs a real Argon2id
  verification against a fixed dummy hash (`nonExistentUserDummyHash`), and password-reset
  requests always return the same generic response whether or not the account exists.

## Consequences
- No JWT means no client-side token replay window after revocation, at the cost of a DB read
  on every authenticated request (`ValidateSession` -- deliberately not RLS-scoped, since
  `sessions` carries no tenant/operator ownership, keeping this hot-path query cheap).
- SSO/OIDC/SAML/WebAuthn/passkeys remain architecture-only per the approved plan; only
  password + TOTP are implemented end-to-end in Milestone 1.
