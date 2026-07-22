# ADR 0006: Post-Milestone-1 Independent Security Audit Fixes

## Status
Accepted (Milestone 1, audit follow-up)

## Context
An independent adversarial audit of the Milestone 1 implementation (code review plus live
exploitation against a running instance) found one Critical, three High, two Medium, and two
Low findings. All are fixed as part of this ADR; see `docs/project-status.md` for the full
ranked findings list, evidence, and re-test results.

## Decisions

### Critical: MFA challenge brute-force via rollback-undone consumption
`identity.Service.VerifyMFAChallenge` used to mark the challenge `consumed_at = now()` and the
submitted TOTP code invalid in the *same* database transaction; returning `ErrInvalidMFACode`
triggered the function's `defer tx.Rollback(ctx)`, which undid the consumption along with
everything else -- so a wrong guess never actually spent the challenge, and it could be retried
without limit. A live proof-of-concept confirmed this: 50 wrong codes against one challenge, then
the genuinely correct code, still succeeded.

Fix: migration `0010_mfa_challenge_attempts.up.sql` adds `attempt_count` to `mfa_challenges`.
`VerifyMFAChallenge` now durably records each attempt in its own transaction, **committed before
the submitted code is checked** (`incrementMFAChallengeAttempt`), so the attempt survives
regardless of whether the code turns out to be valid. Once `MFA_MAX_ATTEMPTS` (default 5) is
reached the challenge is marked consumed in that same atomic statement and can never be retried
again. A second transaction then validates the code and, only on success, consumes the challenge
and creates the session. A wrong guess also now feeds `login_attempts` (the same table backing
the existing password-lockout), so brute-forcing across many freshly-minted challenges eventually
locks the account instead of resetting the attacker's budget on every new login.

### High: seed script's production gate was a denylist, not an allowlist
`cmd/seed/main.go` only refused to run when `CONTROL_API_ENV` was exactly `"production"`.
`"prod"`, `"staging"`, `"Production"`, or any other misconfigured value sailed through and would
seed known-password demo accounts (including a Platform Super Administrator) into whatever
database `DATABASE_URL` pointed at. Fixed to an allowlist: seeding now requires
`CONTROL_API_ENV` to be exactly `"development"` or `"test"`.

### High: invitation `role_key` had no privilege ceiling
`tenancy.Service.CreateInvitation` and `operators.Service.CreateInvitation` resolved a
client-supplied `role_key` into a role ID with only an existence check -- no verification that
the inviting user's own role actually held every permission the target role grants. In today's
seed data this was not independently exploitable (the only roles permitted to invite --
`enterprise_owner`/`enterprise_admin`, `operator_platform_owner` -- already hold a superset of
every other role's permissions in their scope), but it depended on that coincidence continuing to
hold rather than on an explicit check. Fixed with `rbac.RoleGrantableBy`, which verifies the
target role's permission set is fully contained in the inviter's own role's permission set before
an invitation can be created; a JIT support-access grant (which has no role of its own) is exempt,
since that path is already a separately-reviewed, dual-control, time-boxed, audited mechanism.
Also fixed: an unknown `role_key` now returns 400 instead of a generic 500.

### High: `.env.example` shipped a real, working `MFA_ENCRYPTION_KEY`
The example value was valid, decodable base64 for a real 32-byte AES-256 key -- not an obvious
placeholder -- risking silent reuse if copied verbatim into a real `.env`. Replaced with a string
that is deliberately not valid base64, so `control-api` refuses to start until a real key is
generated (`openssl rand -base64 32`), matching the "fail closed, no insecure default" rule
already applied to every other secret in this codebase.

### Medium: `enterprise_tenants` and `operators` had no Row-Level Security
Every other tenant/operator-owned table (memberships, subscriptions, invitations, audit events)
enforces RLS as a defense-in-depth backstop under the application-layer scope check; these two
profile tables did not. Confirmed via direct `pg_class` inspection and a live psql test: a
transaction scoped to one tenant could still `SELECT` every tenant's row. Migration
`0011_tenant_operator_rls.up.sql` adds the same self-scope (`id = app.tenant_id` /
`id = app.operator_id`) plus platform-bypass policy pair the membership tables already use.

### Medium: `AcceptInvitation` never verified the invited email
Both `tenancy.Service.AcceptInvitation` and `operators.Service.AcceptInvitation` created a
membership for whichever authenticated user held a valid, unexpired invitation token, without
checking that the token was actually addressed to that user's own email. Fixed: both now look up
the accepting user's current email directly from `users` and reject (403) unless it matches the
invitation's target email (case-insensitive).

### Low: CSRF token comparison was not constant-time
`httpserver.CSRFProtect` compared the submitted header against the cookie with plain `!=` despite
`security.ConstantTimeEquals` already existing (and being unit-tested) elsewhere in the codebase.
Fixed to use it.

### Low (hardening, not exploitable in the current architecture): Docker Compose ports, CSP header
`docker-compose.yml` published every dev-stack port to `0.0.0.0`; now bound to `127.0.0.1` so a
shared/cloud dev host doesn't expose Postgres/Redis/etc. to the network by default.
`httpserver.SecurityHeaders` now also sets `Content-Security-Policy: default-src 'none';
frame-ancestors 'none'` -- safe for a JSON-only API that renders no HTML of its own.

## Consequences
- Two new migrations (`0010`, `0011`); both are pure additive schema changes (a new column, RLS
  policies) with no backfill required.
- One new config value, `MFA_MAX_ATTEMPTS` (default 5), following the same env-var-with-safe-
  default pattern as `LOGIN_LOCKOUT_THRESHOLD`.
- `VerifyMFAChallenge` now costs two round-trip transactions instead of one, trading a small
  latency increase for the attempt count being durable independent of the outer transaction's
  outcome -- the only way to close the rollback-reuse bug correctly.
- New test coverage that did not exist before this audit: MFA challenge attempt exhaustion
  (`TestMFAChallengeLockedAfterTooManyFailedAttempts`), the `RoleGrantableBy` privilege-ceiling
  primitive (`TestRoleGrantableBy`), the full invitation create/accept HTTP flow including the
  email-mismatch and unknown-role rejection paths (`invitation_flow_test.go`), and a direct
  database-level proof that `enterprise_tenants` RLS actually blocks cross-tenant reads
  (`TestTenantAndOperatorRowLevelSecurity`). Invitations had zero test coverage before this audit.
