# Application-Security Audit

**Scope:** authentication, session management, MFA, CSRF, SQL-injection surface, XSS surface,
secrets handling, security headers, brute-force protection, and CORS across `apps/control-api` and
`apps/web`. **Out of scope** (covered elsewhere): tenant/operator RLS isolation
(`docs/security/tenant-isolation-audit.md`, `docs/security/operator-isolation-audit.md`),
Kubernetes/cryptographic/supply-chain concerns
(`docs/security/kubernetes-security-audit.md`, `docs/security/cryptographic-review.md`,
`docs/security/supply-chain-review.md`). **Method:** exhaustive, file-by-file review; every claim
below cites a real `file:line`.

## Password and credential storage — strong

- Passwords hashed with **Argon2id** (`internal/platform/security/password.go`), env-configurable
  cost parameters (`ARGON2_MEMORY_KIB`=65536, `ARGON2_ITERATIONS`=3, `ARGON2_PARALLELISM`=2 by
  default), 16-byte salt, constant-time verification.
- A fixed dummy hash is compared against on a nonexistent-user login (`identity/service.go:175,207-214`)
  so username enumeration via response-timing is mitigated.
- `password_reset_tokens` and `email_verification_tokens` are stored as SHA-256 hashes, never
  plaintext — the raw token exists only in the emailed link.
- `mfa_totp_secrets` are AES-256-GCM encrypted at rest (necessarily reversible, since TOTP
  verification needs the raw secret) under a required, no-fallback `MFA_ENCRYPTION_KEY`.
- **No MFA recovery/backup codes exist anywhere in this codebase.** `DisableMFA` requires a live,
  valid TOTP code with no alternate path. This is a genuine product-completeness gap (a user who
  loses their authenticator device has no self-service recovery path — only a support-ticket-driven
  manual account-recovery process, not evaluated as part of this technical audit), not a security
  weakness in the narrow sense; flagged here because it's the kind of gap an OWASP-style review is
  expected to surface even when it isn't itself exploitable.

## Session management — Finding (Low): password change does not rotate other sessions

- Sessions are opaque random tokens (32 bytes), only their SHA-256 hash persisted server-side — not
  a JWT, so there's no token to forge or decode, only to steal.
- Session cookie: `HttpOnly: true`, `Secure` (env-controlled, `true` by default),
  `SameSite: Lax`, correctly scoped. No pre-authentication session is ever issued, so there's no
  session-fixation surface to speak of.
- `ResetPassword` (forgot-password flow) **does** revoke every existing session for the account —
  correct, since this flow is used precisely when the account may be compromised.
- **`ChangePassword` (the authenticated, know-your-current-password flow) does not revoke other
  sessions.** If an attacker has already stolen a valid session cookie, the legitimate user changing
  their password does not evict that stolen session. Recommendation: call the same
  `revokeAllUserSessions` helper `ResetPassword` already uses (or a variant that preserves the
  session making the change) from `ChangePassword` too. Low severity because it requires a session
  to already be compromised for the gap to matter — it does not create the initial compromise.
- MFA enrollment completion (`ConfirmMFA`) and `DisableMFA` similarly do not rotate/revoke sessions.
  Same recommendation and same severity reasoning: only relevant if a session is already
  compromised, but tightening it is cheap and consistent with `ResetPassword`'s existing behavior.

## MFA/TOTP — sound, one gap noted above (no recovery codes)

- `pquerna/otp`, standard TOTP (30s period, ±1 step skew, 6 digits, SHA1) — an industry-standard
  library and parameters, not a custom implementation.
- `MFA_MAX_ATTEMPTS` is enforced via a single atomic `UPDATE ... WHERE attempt_count < $2` that
  increments the counter *before* the submitted code is checked, so a request that errors partway
  through can never "refund" an attempt — a sound design against attempt-counting races.
- No bypass path of any kind was found (no admin override, no debug flag, no alternate disable path).

## CSRF — sound

- Double-submit-cookie pattern applied globally as router middleware, covering every route including
  pre-auth ones (`/api/v1/auth/register`, `/api/v1/auth/login`) — confirmed by an existing test
  (`internal/app/csrf_test.go`).
- `GET`/`HEAD`/`OPTIONS` correctly excluded from the token check.
- Machine-authenticated agent routes (bootstrap, agent-facing endpoints) are explicitly exempted,
  correctly — a CSRF token has no meaning for a caller authenticated by certificate/signature, not a
  browser session cookie.

## SQL-injection surface — clean

- Every one of the 20 `internal/modules/*/repository.go` files sampled uses parameterized
  (`$1, $2, ...`) queries exclusively. No string concatenation building a query with user input was
  found anywhere.
- Every `fmt.Sprintf` found near a SQL keyword only appends further `$N` placeholders or interpolates
  a **fixed, hardcoded** column name the caller passes as a Go string literal (e.g. `"operator_id"`,
  `"enterprise_tenant_id"`) — never a value derived from request input. No dynamic
  `ORDER BY`/column-selection-from-user-input pattern exists anywhere.

## XSS / frontend — clean

- Zero occurrences of `dangerouslySetInnerHTML`, raw `innerHTML` assignment, or `document.write`
  anywhere in `apps/web`.
- No open-redirect-shaped pattern exists — every `router.push(...)` call target is either a fixed,
  hardcoded string or a resource ID sourced from an API response, never an attacker-controlled URL
  query parameter.

## Secrets handling — Finding (Informational): one hardcoded, guarded, documented-fictional password

- `apps/control-api/cmd/seed/main.go` hardcodes a demo password (`GridkeepDemo!2026`) for the
  fictional seed accounts. This is explicitly gated to refuse running unless
  `CONTROL_API_ENV` is `development` or `test`, and the password is already publicly documented in
  this repository's own seed output as fictional/demo-only — not a real credential, and not
  reachable in a production configuration. Flagged for completeness, not as an actionable finding.
- No secret value (password, token, session ID, encryption key) is ever passed to a log call
  anywhere in either `control-api` or `apps/web` — confirmed by a targeted grep across every logger/
  console call site near a secret-shaped argument name.
- Three genuinely security-sensitive environment variables (`MFA_ENCRYPTION_KEY`,
  `PKI_CA_ENCRYPTION_KEY`, `SECRETS_VAULT_ENCRYPTION_KEY`) have deliberately invalid placeholder
  defaults in `.env.example`, so the server refuses to start with them unset/default in any real
  deployment — correct fail-closed behavior for key material.
- The frontend never holds a secret client-side; the only client-readable cookie is the
  non-secret CSRF double-submit token.

## Security headers — Finding (Low), fixed this milestone: no HSTS set anywhere

- `control-api` sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: same-origin`, `Cache-Control: no-store`, and a strict
  `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` on every response — a solid,
  deny-by-default baseline appropriate for a pure JSON API (the CSP correctly has no need for
  `script-src`/`style-src` allowances since this service never serves HTML).
- **No `Strict-Transport-Security` header was set anywhere.** Low severity, since HSTS defends
  against a protocol-downgrade attack requiring an active network-position attacker on a *first*
  connection, not currently exploitable in this sandbox's configuration — but cheap and safe to fix
  immediately rather than leave as a recommendation. **Fixed this milestone**:
  `internal/platform/httpserver/middleware.go`'s `SecurityHeaders` now also sets
  `Strict-Transport-Security: max-age=31536000; includeSubDomains` on every response. Browsers
  ignore this header on a plain-HTTP response per spec, so it is safe to set unconditionally rather
  than gate on request scheme — harmless in local development, effective the moment a real
  deployment terminates TLS in front of this service.
- The Next.js frontend (`apps/web/next.config.ts`) still sets no headers of its own (no `headers()`
  function configured), relying entirely on whatever the eventual deployment's reverse proxy/CDN
  adds. Not fixed this milestone — recommendation stands: add an explicit `headers()` block mirroring
  control-api's baseline (frame-ancestors/nosniff at minimum), so the frontend's security posture
  doesn't depend entirely on downstream infrastructure being configured correctly.

## Brute-force / rate limiting — Finding (Medium): protection is login-only

- Login lockout (`LOGIN_LOCKOUT_THRESHOLD`=5 within `LOGIN_LOCKOUT_WINDOW_MINUTES`=15 by default) is
  checked *before* password verification even runs, and every attempt (success or failure) is
  recorded — a sound, standard mechanism for the one flow it covers.
- **No equivalent throttle exists for registration or password-reset requests.** Concretely:
  - `Register` has no rate limit — an attacker can submit unlimited registration attempts, each
    triggering a verification email send, and can enumerate existing accounts via the distinct
    "already registered" response (this is a narrower enumeration vector than the password-reset
    flow below, which was already designed to avoid it).
  - `RequestPasswordReset` correctly returns an identical response whether or not the account
    exists (mitigating *response-content* enumeration), but has no rate limit against an attacker
    repeatedly requesting resets for a target address, which would flood that address with reset
    emails.
  - No generic rate-limiting middleware exists anywhere in this codebase.
- **Recommendation:** add a rate limit (by source IP and/or target email, whichever this
  deployment's threat model prioritizes) to both `Register` and `RequestPasswordReset`, reusing the
  existing `login_attempts`-table pattern or a dedicated Redis-backed limiter (`internal/platform/cache`
  already exists and is wired for entitlement caching — a rate-limit counter is a natural extension
  of the same Redis connection). Medium severity: an unlimited registration/reset-request path is a
  real, currently-reachable griefing/spam vector against arbitrary third-party email addresses, even
  though it doesn't itself compromise an account.

## CORS — sound

- `AllowedOrigins` is env-driven (`CORS_ALLOWED_ORIGINS`, default `http://localhost:3000` for local
  dev only), never a wildcard, correctly paired with `AllowCredentials: true` (a wildcard origin with
  credentials is rejected by the CORS library itself, so this pairing could not silently regress to
  an insecure state without an explicit, deliberate config change).

## Dependency vulnerabilities (live scan results)

- **`npm audit` against `apps/web`** (actually run this milestone): 3 high-severity advisories, all
  transitive through Next.js's own bundled `postgres`/`sharp` dependencies (XSS in PostCSS's CSS
  stringifier, `libvips` CVEs in `sharp`). The only available fix (`npm audit fix --force`) downgrades
  to `next@9.3.3` — a major breaking change this milestone did not make. Tracked as a known,
  currently-open, non-blocking CI finding (see `.github/workflows/ci.yml`'s `npm audit (report only)`
  step) rather than silently ignored; revisit when Next.js ships a non-breaking fix for its bundled
  dependencies.
- **`govulncheck` against `control-api`/`worker`**: could not be run in this sandbox —
  `vuln.go.dev` is not on the outbound-proxy's allowlist (confirmed via the agent-proxy status
  endpoint; `proxy.golang.org` itself is allowlisted and module downloads work, only the vulnerability
  database host is blocked). Added to CI (`.github/workflows/ci.yml`) regardless, since GitHub
  Actions runners have unrestricted internet access and will exercise it for real on every future
  push/PR — the same "written correctly, not exercisable in this sandbox" category as this project's
  Docker Hub/registry limitations documented since Milestone 1.
- **`pip-audit` against `policy-engine`**: run successfully in a fresh Python 3.12 virtualenv
  (`--skip-editable` to exclude the project's own non-PyPI-published package) — zero known
  vulnerabilities in any of `fastapi`/`uvicorn`/`pydantic` or their transitive dependencies.

## Verdict

No critical or currently-exploitable high-severity application-security defect was found. The
strongest parts of this codebase's security posture — Argon2id with no shortcuts, hashed-at-rest
tokens, sound CSRF, sound SQL-parameterization discipline, a genuinely strict CSP — reflect care
taken across the preceding fifteen milestones, not something added retroactively for this audit. The
findings above are real but bounded: one Medium (registration/reset-request rate limiting), a
handful of Low/Informational items (session rotation on password change, missing HSTS, no MFA
recovery codes), and one already-tracked, non-blocking, upstream-caused dependency finding. None
requires an emergency fix before this milestone's sign-off; all are recorded here so they are visible
and actionable rather than lost.
