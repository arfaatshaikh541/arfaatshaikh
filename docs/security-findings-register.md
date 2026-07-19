# GRIDKEEP Cyber OS — Security Findings Register

Tracks every finding from the independent security audit (an adversarial code review that treated all
prior milestone claims, tests, and documentation as unverified until directly checked or reproduced
against a live database) and every finding the production-hardening programme surfaces on top of it.

**Status definitions:**

- **open** — not yet addressed.
- **mitigated** — a fix has shipped and is covered by an executable test, but has not yet been confirmed
  by an independent party (a re-audit, a real pentest) — see Milestone 14 of the hardening programme.
- **accepted** — a deliberate decision not to fix, with a documented business/technical reason. Never used
  to silently hide risk; the reason is always written out.
- **transferred** — the risk is now owned by something outside this codebase (a reverse proxy, a cloud
  provider's IAM boundary, an operational process) and is tracked here only so it isn't forgotten.

Do not delete a resolved row. Change its status and add a dated note instead — this file is the audit
trail of the audit trail.

## Critical

| ID | Finding | Status | Milestone | Notes |
|---|---|---|---|---|
| C-01 | Row-Level Security is inert — the application's Postgres role (`gridkeep`, created via `POSTGRES_USER` on the stock image) is an unrestricted superuser that unconditionally bypasses RLS, `FORCE ROW LEVEL SECURITY` notwithstanding. Reproduced live: an INSERT with a mismatched `app.current_tenant_id` succeeded and committed. | open | M3 (Tenant Isolation, PostgreSQL RLS, and Worker Isolation) | The existing `test_rls_rejects_cross_tenant_membership_insert` does not currently exercise what its name claims against this role configuration — verified by direct reproduction, not assumed. **Corroborating evidence found 2026-07-19 while verifying Milestone 29's own changes**: running the full suite against a real local Postgres role built the same way (`initdb -U gridkeep`, matching the Docker image's bootstrap) surfaces three *pre-existing, independent* test failures, all attributable to this same root cause and none caused by Milestone 29's changes: `test_audit.py::test_audit_log_is_append_only_update_has_no_effect` and `::test_audit_log_is_append_only_delete_has_no_effect` (an UPDATE/DELETE that `FORCE ROW LEVEL SECURITY`'s missing policy should silently deny instead succeeds, `rowcount == 1`, not `0`), and `test_attack_surface.py::test_add_domain_already_claimed_by_another_tenant_conflicts` — the latter is a genuine functional bug, not just a test assertion: `modules/attack_surface/service.py:add_domain`'s own docstring explicitly documents relying on RLS to scope its pre-check SELECT to the caller's tenant; because RLS doesn't actually filter anything for this role, a cross-tenant domain claim sees the other tenant's row and returns the wrong error message ("already added to your workspace" instead of "already claimed by another workspace") — it still correctly refuses the claim (no cross-tenant domain hijack occurs, since the same code path denies the operation either way), but for the wrong stated reason, which is itself evidence the isolation the code believes it has isn't there. All three are expected to resolve on their own once M3 ships the least-privilege role — none required a code change to "fix" as part of Milestone 29, and none should be "fixed" by patching the test or the error-message logic before M3, since that would paper over the actual cause. |
| C-02 | No production credential-vault adapter exists. `core/config.py`'s own comment points at `modules/credential_vault/adapters/production.py`, which does not exist. `get_vault_adapter()` is hardcoded to always return the local adapter regardless of environment, and the local adapter's default master key is a public string committed in this repository. | open | M5 (Credential Vault, KMS, Secrets, and Connector Security) | Milestone 29 adds a fail-closed boot check for the *shipped default key specifically* (see H-02 below) — this does not build the real KMS-backed adapter itself; that remains open under C-02 until M5. |

## High

| ID | Finding | Status | Milestone | Notes |
|---|---|---|---|---|
| H-01 | No rate limiting on `POST /api/auth/mfa/verify-login` — a wrong TOTP/backup-code guess doesn't invalidate the MFA challenge token, allowing unlimited guesses against a 6-digit (10^6) space within the token's 10-minute TTL. | open | M2 (Authentication, Sessions, MFA, and Account Recovery) | |
| H-02 | Cookie `Secure` flag, HSTS presence, and `/api/docs` exposure all keyed off a single `ENVIRONMENT` env var with an insecure (`development`) default and no fail-closed guard. | **mitigated (2026-07-19, Milestone 29)** | M1 | Fixed by: (1) `core/config.py` — a `model_validator(mode="after")` refuses to construct a `production` `Settings` object while any of `VAULT_LOCAL_MASTER_KEY`, `OBJECT_STORAGE_ACCESS_KEY`/`SECRET_KEY`, `DATABASE_URL`/`DATABASE_MIGRATION_URL`, `CORS_ALLOW_ORIGINS`, `REDIS_URL`, or `ALLOW_INSECURE_COOKIES_FOR_LOCAL_DEV` still carries its shipped development value. (2) Session/CSRF cookies are now `Secure` **by default in every environment** (`modules/identity/routes.py:_cookie_secure_kwargs`) — the only way to get an insecure cookie is the new, narrowly-named `allow_insecure_cookies_for_local_dev` opt-out, which the same validator refuses to allow in production. (3) `Strict-Transport-Security` is now sent unconditionally by `SecurityHeadersMiddleware`. Verified by `tests/security/test_production_config.py` (9 cases) and `tests/security/test_security_headers.py` (4 cases, including a real HTTP round-trip asserting `Secure`/`HttpOnly` appear in the literal `Set-Cookie` header). API-docs exposure (`main.py:42-44`) was already correctly gated on `is_production` before this milestone — confirmed unchanged and correct, not re-fixed. **Not yet independently re-verified — status will move to a plain `mitigated` reference in M13's regression suite and to fully closed only after M14's external audit.** |

## Medium

| ID | Finding | Status | Milestone | Notes |
|---|---|---|---|---|
| M-01 | Unsanitized user-supplied filename interpolated directly into the `Content-Disposition` header on evidence file download (`modules/compliance/service.py`, `modules/compliance/routes.py`) — a `"` in the filename can break header quoting. | open | M6 (API, Browser, and Application-Layer Hardening) | |
| M-02 | Seven dependency CVEs are permanently waived in CI (`--ignore-vuln`/`--ignore-unfixable`) with a documented reason but no recurring re-review process. | open | M10 (CI/CD, Dependencies, Provenance, and Supply-Chain Security) | |

## Low

| ID | Finding | Status | Milestone | Notes |
|---|---|---|---|---|
| L-01 | `forgot-password` always returns 200 (correct anti-enumeration behaviour), but real SMTP dispatch latency only occurs when the account exists — a minor timing side-channel. | open | M2 (opportunistic fix, not primary scope) | |

## Programme-level (not from the original audit — surfaced while building the hardening programme itself)

| ID | Finding | Status | Milestone | Notes |
|---|---|---|---|---|
| P-01 | `docker-compose.production.yml`'s `api` service would have silently inherited the base file's `ALLOW_INSECURE_COOKIES_FOR_LOCAL_DEV: "true"` (Compose merges `environment:` maps key-by-key, unlike `ports`/`volumes`, which this file resets with `!reset`) — caught while empirically verifying the overlay with `docker compose config`, before it ever reached a running container. | mitigated (2026-07-19, Milestone 29) | M1 | Fixed by explicitly setting `ALLOW_INSECURE_COOKIES_FOR_LOCAL_DEV: "false"` in `docker-compose.production.yml`'s `api` environment block, rather than relying solely on `core/config.py`'s boot-time refusal as the only backstop. Verified by running `docker compose -f docker-compose.yml -f docker-compose.production.yml config` with the full set of required production variables and confirming the merged output. |

## External validation status

No independent, third-party penetration test or security audit has been performed on this codebase as of
this register's creation. Every "mitigated" status above reflects internal implementation plus an
executable test — not external confirmation. Do not represent any "mitigated" finding as "resolved" or
"fixed" to a customer or auditor without qualifying that it is internally verified only, pending
Milestone 14.
