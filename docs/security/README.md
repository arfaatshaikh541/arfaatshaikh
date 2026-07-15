# Security — Milestones 1 through 7

This documents what is actually implemented as of Milestone 7, what is
verified, and what remains for later milestones or a pre-launch security
review. It is not a substitute for a professional security audit or
legal review before a real production launch (see "Legal & compliance"
at the bottom).

## Public lead capture surface (Milestone 2)

The only unauthenticated, write-capable endpoint in the platform is
`POST /api/public/capture/{token}/enquiry`. Controls in place:

| Control | Implementation |
|---|---|
| Tenant identification | An unguessable, per-tenant capture token (`tenant_capture_tokens.token`, 24 random bytes) — never the tenant's slug or UUID |
| Honeypot | A hidden `website` field; a real visitor never fills it in. Filled in → identical success response returned, nothing persisted |
| Throttling | Redis-backed, 10 submissions / 10 minutes per (tenant, IP); verified by automated test |
| Idempotency | Optional client-supplied `idempotency_key` — a retried submission returns the same lead rather than creating a duplicate |
| Duplicate detection | Heuristic match on (tenant, email/phone) within a 30-day window — flags rather than silently drops, so no real enquiry is lost |
| Consent | `consent_given` boolean recorded as `consent_status` on the lead |
| Entitlement enforcement | `lead_capture` module and the `leads` usage limit are checked before any row is written, even on this unauthenticated path |
| No tenant internals exposed | The services/qualification-form endpoints behind this token return only public-safe fields (name, description) |

## File uploads (Milestone 2)

| Control | Implementation |
|---|---|
| MIME allow-list | `ALLOWED_ATTACHMENT_CONTENT_TYPES` in `app/modules/crm/service.py` — PDFs, common images, Office documents, plain text only |
| Size limit | 20MB, enforced before any storage write |
| Storage keys | Tenant- and entity-namespaced, UUID-randomised (`build_storage_key`) — never sequential or guessable |
| Downloads | Short-lived (10-minute), single-purpose signed URLs — local dev via a random Redis-backed token redeemed at `GET /api/files/{token}`, production via real S3 presigned URLs (`S3Adapter.get_download_url`). The browser never learns the real storage key |
| Malware scanning | **Partially implemented** as of Milestone 7 — see "Document collection malware scanning" below. CRM's own generic lead attachments (this table) do not yet call the scan hook; only the `documents` module's uploads do |

## Email template rendering (Milestone 3)

| Control | Implementation |
|---|---|
| No template-injection surface | Merge fields use a fixed `{{field}}` whitelist substituted via `re.sub` (`app/modules/communications/service.py::render_template`) — never Jinja2 or any engine with code-execution capability, even though Jinja2 is already a dependency for other purposes. An unknown `{{field}}` is left as literal text, not evaluated |
| Test-send safety | `POST /tenant/communications/templates/{id}/send-test` always sends to the requesting user's own email address (looked up server-side from the session), never a client-supplied recipient — no open-mail-relay / spam risk |
| Soft-fail by design | A disabled `communications` module, a missing active template, or an exhausted `messages` usage limit all cause `send_templated_email` to return `None` rather than raise — a notification failure can never block the core action (lead creation, stage change) that triggered it. Verified by automated tests |
| Delivery retry | Failed sends are logged (`email_delivery_logs`, rendered-content snapshot, not re-rendered from context) and retried by a Celery beat sweep up to a fixed attempt cap — never an unbounded retry loop |

## Public booking surface (Milestone 4)

`POST /api/public/booking/{token}/book` is the second unauthenticated,
write-capable endpoint. It reuses every control already proven for
public lead capture rather than inventing new ones:

| Control | Implementation |
|---|---|
| Tenant identification | The same unguessable per-tenant capture token as public lead capture — no separate booking-specific token |
| Honeypot | Same hidden `website` field convention |
| Throttling | Redis-backed, 10 requests / 10 minutes per (tenant, IP), independent counter from lead capture's |
| Entitlement enforcement | The `booking` module is checked before any row is written, even on this unauthenticated path |
| Double-booking prevention | The same overlap check + row lock used on the authenticated path (`AppointmentRepository.find_overlapping`) runs again server-side immediately before insert — a slot the client saw a moment earlier from a cached `GET /slots` response is never trusted blindly |
| No staff account details exposed | `GET /public/booking/{token}/staff` returns only `id`/`first_name`/`last_name` for staff with configured availability — never email, role, or any other account field |
| Past-date rejection | Both the slot computation and `create_appointment` independently reject anything at or before the current time |

## Availability management authorization (Milestone 4)

Setting a staff member's weekly availability requires `appointments.manage`
(already broadly granted) plus a business-rule check
(`booking.service.assert_can_manage_availability`): a user may always set
their own hours, but setting someone *else's* requires `users.manage`.
This mirrors how permission-code checks stay in the route layer
throughout the codebase — the service function takes plain booleans
(`actor_can_manage_others`) rather than a permission-context object, so
the business rule itself has no dependency on the permission catalog.
Verified by automated test (a Sales Agent can set their own availability
but not the Tenant Owner's).

## Workflow automation execution safety (Milestone 5)

| Control | Implementation |
|---|---|
| No arbitrary code execution | Workflow actions are a fixed enum (`SEND_EMAIL_TEMPLATE`/`CREATE_TASK`/`CHANGE_STAGE`/`ADD_TAG`) dispatched through an explicit `if`/`elif` chain (`workflow_automation.service._execute_step`) — there is no dynamic action resolution, code-string evaluation, or webhook/external-call action type in this milestone |
| Condition evaluation has no injection surface | `workflow_automation/conditions.py` evaluates a fixed operator enum against a fixed field whitelist (`_DIRECT_FIELDS`), the same pattern as Milestone 3's scoring rules — never a dynamic expression language |
| A failing step can't strand a run | Exceptions raised inside `_execute_step` (e.g. a workflow referencing a since-deleted template) are caught, logged as `FAILED` in `workflow_step_logs`, and the run still advances — a single bad step configuration can't leave a `WorkflowRun` permanently stuck consuming the sweep's attention every cycle |
| Soft-fail by design | A disabled `workflow_automation` module or an exhausted `automation_runs` usage limit causes `evaluate_triggers_for_lead` to return without creating a run — the lead-creation/stage-change/tag/appointment action that fired the trigger is never blocked. Verified by automated tests |
| Cross-tenant isolation | Every workflow/step/run/log table is `tenant_id`-scoped with RLS `FORCE`d, same as every other module; verified by automated test |

## Public proposal acceptance surface (Milestone 6)

`GET /public/proposals/{token}`, `POST /public/proposals/{token}/accept`,
and `POST /public/proposals/{token}/reject` are the third unauthenticated,
write-capable surface (after public lead capture and public booking) —
though the actual write here (accept/reject) can only ever affect the one
proposal the caller already holds a link to, never an arbitrary tenant
resource.

| Control | Implementation |
|---|---|
| Authorization | An unguessable, per-proposal token (`proposals.public_token`, 32 random bytes, `secrets.token_urlsafe` via `generate_opaque_token`) generated only when a proposal is sent — never derivable from the proposal's id, the lead's id, or the tenant's slug |
| No cross-tenant leakage before authorization | `ProposalRepository.get_by_public_token` looks up the row directly by token with no tenant filter (the table is deliberately excluded from RLS — see `docs/database/README.md`); `get_proposal_by_token` calls `set_rls_context` immediately after resolving the tenant, before touching any other RLS-protected table (line items, tenant name) |
| State-machine guards | `accept_proposal`/`reject_proposal` only transition out of `SENT`/`VIEWED` — a proposal already accepted, rejected, or expired cannot be re-accepted or re-rejected by replaying the link; an expired `valid_until` is checked and flips the proposal to `EXPIRED` before the accept can proceed |
| Deliberately NOT gated by the `proposals` module entitlement | Unlike every other public-facing flow in this codebase (public lead capture, public booking), the accept/reject routes skip the module-enabled check entirely — a considered exception, not an oversight: a client must never be blocked from responding to a proposal they already received just because the tenant's subscription state changed after it was sent. The authenticated `GET /tenant/proposals` management routes are still gated normally. Verified by automated test (`test_public_route_not_gated_by_proposals_module_entitlement`) and a live smoke test that disabled the module for a tenant and confirmed the tenant route returned 403 while the public accept route still returned 200 |
| No sensitive data beyond the proposal itself | The public view returns only the proposal's own fields (title, line items, totals, terms, tenant name) — never the lead's contact details, internal id, or any other tenant data |

## Public document upload surface & malware scanning (Milestone 7)

`GET /public/documents/{token}` and `POST /public/documents/{token}/upload`
are the fourth unauthenticated, write-capable surface. Unlike the public
proposal accept/reject routes, the upload route **is** gated behind the
`document_collection` module entitlement — a deliberate divergence from
the Milestone 6 precedent, documented in `DocumentRequest`'s model
docstring: accepting/rejecting a proposal just flips a status flag, but
uploading a file consumes ongoing storage, so a lapsed subscription
should stop new uploads rather than silently keep consuming a resource
nobody's paying for. Verified by automated test and a live smoke test
(module disabled → public view still 200, public upload 403).

| Control | Implementation |
|---|---|
| Authorization | An unguessable, per-request token (`document_requests.public_token`, 32 random bytes), generated at request-creation time — the same raw-token/no-RLS pattern as `Proposal.public_token` |
| MIME allow-list & size limit | `ALLOWED_DOCUMENT_CONTENT_TYPES`/`MAX_DOCUMENT_SIZE_BYTES` in `app/modules/documents/service.py` — duplicated from (not imported from) `crm.service`'s equivalent constants, since `documents` is meant to be the more foundational module going forward; 20MB limit, same as CRM attachments |
| Malware scanning | `documents.service._scan_for_malware` checks uploaded content against the EICAR test signature — the industry-standard string every real antivirus engine (and this check) recognizes, so this is a genuine, functioning safety net, not a stub. It is **not** a substitute for real malware scanning in production: wiring a real engine (a ClamAV daemon via `clamd`, or a cloud AV API) into this exact function **requires external infrastructure this sandbox doesn't have**. Verified by automated test and a live smoke test using the real EICAR string |
| Storage usage enforcement | Every accepted upload increments the `document_storage_mb` usage metric via `check_and_increment_usage`, sized to the file's rounded-up megabyte count; exceeding the plan's limit hard-fails the upload (403 `usage_limit_exceeded`) — unlike the soft-fail communications/workflow pattern, a storage cap must actually block the write |
| Request status guards | The public upload route only accepts uploads while a request is `REQUESTED` or `REJECTED` (re-upload after a rejection) — an `APPROVED` or already-`UPLOADED`-and-pending-review request rejects further public uploads |
| No sensitive data beyond the request itself | The public view returns only the request's own title/description/status — never the lead's contact details or any other tenant data |

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
- A real malware scanning engine for document uploads — Milestone 7 added
  a genuine EICAR-signature check (see "Public document upload surface &
  malware scanning" above), but wiring an actual AV engine (ClamAV or a
  cloud API) requires external infrastructure. CRM's own generic lead
  attachments (Milestone 2) still don't call any scan hook at all.
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
