# Security — Milestone 1

This documents what is actually implemented as of Milestone 1, what is
verified, and what remains for later milestones or a pre-launch security
review. It is not a substitute for a professional security audit or
legal review before a real production launch (see "Legal & compliance"
at the bottom).

## Authentication

| Control | Status |
|---|---|
| Password hashing | Argon2id (`argon2-cffi`), tuned parameters in `app/core/security.py` |
| Session tokens | Opaque, 256-bit random (`secrets.token_urlsafe`), stored server-side only as a SHA-256 hash — raw token never persisted |
| Cookies | `HttpOnly`, `SameSite=Lax`, `Secure` in production (`SESSION_COOKIE_SECURE=true`) |
| Session revocation | Logout revokes immediately; password reset revokes every session for that user; verified by automated tests |
| Login throttling | Redis-backed fixed-window limiter, 8 attempts / 15 minutes per (email, IP); verified by automated test |
| Generic auth errors | Login and password-reset-request return identical responses regardless of which specific case failed (unknown email vs wrong password; email exists vs doesn't) — verified by automated tests |
| Email verification | Implemented; not yet a hard gate on any action (tenant admins can decide whether to require it, in a later milestone) |
| 2FA | Not implemented — `users` schema and the auth dependency chain are structured so a second factor can be inserted later without a redesign |

## Authorization

| Control | Status |
|---|---|
| Tenant context | Derived exclusively from the session's `active_tenant_id` + a live `memberships` row — never from client-supplied input (`app/dependencies/tenant.py`) |
| Permission checks | `require_permission(code)` dependency, backend-enforced on every protected route; verified by automated tests (privilege escalation, cross-role access, direct object reference) |
| Platform vs tenant roles | Structurally separate — `is_platform_admin` is a `users` column, never grantable through tenant role management; the tenant-assignable permission catalog never includes `platform.*` codes; verified by automated test |
| Entitlement checks | `require_module`/`require_feature`/`check_usage_limit` dependencies, resolved from the DB every request — never hardcoded in frontend or backend; verified by automated tests |

## Tenant isolation

| Control | Status |
|---|---|
| Backend query scoping | Every tenant-owned repository query filters by `tenant_id` from the resolved `TenantContext` |
| PostgreSQL RLS | Enabled + `FORCE` on every tenant-owned table, defence-in-depth behind the backend checks above — see `docs/database/README.md` |
| Cross-tenant tests | Automated: cross-tenant reads, tenant-switch into a non-member tenant, per-tenant data isolation (users, settings) |

## Input handling & transport

| Control | Status |
|---|---|
| Request validation | Pydantic schemas on every route; malformed input returns a generic `validation_failed` error, never a stack trace |
| SQL injection | SQLAlchemy parameterized queries exclusively; the one place raw SQL is used (`set_config` for RLS context) is bound-parameterized, never string-interpolated |
| CORS | Explicit origin allow-list (`CORS_ALLOWED_ORIGINS`), `allow_credentials=True` scoped to those origins only |
| CSRF | `SameSite=Lax` cookies mitigate the common case; a double-submit CSRF token for state-changing requests is **not yet implemented** — flagged for Milestone 10 hardening, since `SameSite=Lax` alone is a reasonable interim posture for a JSON API with no cross-site form auto-submission surface |
| Security headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, HSTS in production |
| Rate limiting | Implemented for login; not yet applied platform-wide to every endpoint (Milestone 10) |
| API docs exposure | `/docs`, `/redoc`, `/openapi.json` are disabled via `API_DOCS_DISABLED=true` in production |
| Error responses | Global exception handler returns a generic `internal_error` body for any unhandled exception; the real exception is logged server-side only, never returned to the client |

## Secrets

- No secret (DB credentials, `APP_SECRET_KEY`, SMTP/S3 credentials) is
  ever sent to the browser — verified by inspecting every response
  schema in `app/modules/*/schemas.py` and the frontend bundle output.
- `.env.example` marks every value that `REQUIRES EXTERNAL CREDENTIAL`
  in production.
- Dependency vulnerability scanning: not yet wired into CI (flagged for
  Milestone 10) — `npm audit` and `pip-audit` were run manually during
  this milestone (see project status for what was found and fixed).

## Not yet implemented (tracked for later milestones)

- Webhook signature verification / replay protection (no webhooks exist
  yet — Milestone 5+ workflow actions and Milestone 11+ integrations).
- Malware scanning integration point for uploads (Milestone 7, document
  collection).
- Automated dependency scanning in CI.
- Formal penetration test / third-party security review.
- CSRF token (double-submit) for state-changing requests.

## Legal & compliance

This platform's architecture supports data isolation, audit trails, and
consent/retention hooks, but **UAE data protection, industry-specific
(audit/accounting) regulatory requirements, and general privacy law
compliance require review by qualified legal counsel before a real
commercial launch.** Nothing in this codebase should be read as a claim
of legal compliance.
