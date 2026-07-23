# GRIDKEEP Project Status

_Last updated: 2026-07-23 (Milestone 2 complete)_

## Current Milestone

**Milestone 2: Operator and Infrastructure Registry** — implementation complete, validated,
not yet handed off for Milestone 3. Milestone 1 (Secure Platform Foundation) is complete and
was independently audited with every Critical/High/Medium/Low finding fixed and re-verified
(see the audit section below, preserved for history).

## Milestone 2: Operator and Infrastructure Registry

Built on top of Milestone 1's foundation, per the approved architecture's Milestone 2 scope
(operator onboarding/contracts, regions/jurisdictions, data centres/edge sites, clusters/node
pools/accelerators/storage/network capabilities, capacity snapshots, operator-agent
registration, certificate lifecycle, mock operator connector).

### What was built
- **Schema** (migrations `0012`-`0015`): a platform-curated `jurisdictions`/`regions`
  taxonomy (no RLS — global reference data, same reasoning as `roles`/`permissions`);
  operator-owned `operator_contracts`, `data_centres`, `edge_sites`, `clusters`,
  `node_pools`, `accelerators`, `storage_pools`, `network_capabilities` (every one RLS-scoped
  with the same self-scope + platform-bypass policy pair every Milestone 1 operator table
  uses); `operator_agents`, `agent_certificates`, `capacity_snapshots`; a singleton
  `platform_ca` table.
- **`internal/platform/pki`**: a real, working local development certificate authority
  (`crypto/x509`, ECDSA P-256) — generates and durably persists its own root key pair
  (AES-256-GCM-encrypted at rest under `PKI_CA_ENCRYPTION_KEY`, same required-with-no-fallback
  pattern as `MFA_ENCRYPTION_KEY`), signs agent CSRs while ignoring any identity the CSR
  itself claims, verifies ECDSA signatures. Explicit Vault-PKI stand-in — see
  `docs/adr/0007-local-development-certificate-authority.md`.
- **`internal/modules/registry`**: CRUD for the full location + technical inventory chain
  (regions/jurisdictions read by any authenticated user, written under the new
  `platform.regions.manage`; data centres/edge sites/contracts/clusters/node pools/
  accelerators/storage pools/network capabilities read by any operator member, written under
  the existing `operator.regions.manage`/`operator.locations.manage`/
  `operator.clusters.manage`/`operator.profile.manage` permissions seeded but unenforced in
  Milestone 1). Every write that references a parent resource validates server-side that the
  referenced ID actually belongs to the caller's own operator before accepting it.
- **`internal/modules/agents`**: operator-agent registration (single-use bootstrap token,
  shown once), certificate bootstrap (`POST /api/v1/agent-bootstrap` — token + CSR in, signed
  certificate out, token consumption and cert issuance commit atomically together), agent
  revocation, and signed capacity-snapshot ingestion
  (`POST /api/v1/agents/{agentID}/capacity-snapshots` — ECDSA-signature-authenticated, not
  session-authenticated, since an agent is not a user; the signature check is the actual
  authorization control here, in application code, before any row is read or written).
- **`cmd/mockconnector`**: a real CLI performing the entire bootstrap → CSR → certificate
  issuance → signed capacity-snapshot submission chain with real generated keys and real
  signatures against a running control-api — only the capacity *facts* it reports are
  fabricated (labeled `is_fictional_demo_data: true`), since there is no real GPU cluster
  behind it yet.
- **CSRF exemption mechanism**: `httpserver.CSRFProtect` now accepts a path-prefix exemption
  list (used for the two machine-authenticated agent routes, which carry no session cookie
  and so have no ambient browser credential for CSRF to protect against) — every
  session-authenticated route's CSRF behavior is unchanged.
- **Frontend**: `/dashboard/operator/[operatorId]/infrastructure` — region catalogue, data
  centres (list + create), clusters (list + create), operator agents (list, register with a
  one-time bootstrap-token banner, revoke), capacity snapshots (read-only). Linked from the
  operator overview page. Node pools, accelerators, storage pools, network capabilities, edge
  sites, and operator contracts remain API-only for now (see Known Limitations) — a
  deliberate scope decision, not an oversight.
- **Seed data**: the two demo operators (Gulf Horizon Telecom Demo, EuroNorth Communications
  Demo) each get one fictional data centre and one fictional cluster; two new global
  jurisdictions/regions (`AE`/`me-central-1`, `DE`/`eu-central-1`). Idempotent — verified by
  running the seed script twice and confirming stable row counts.
- **New permission**: `platform.regions.manage`, granted only to
  `platform_super_administrator` — `docs/security/permission-matrix.md` regenerated from the
  live database.

### Deliberate security decisions worth calling out
- **CSR Subject is never trusted.** `CA.SignCSR` validates only that the CSR's self-signature
  proves possession of the private key, then builds the issued certificate's Subject from the
  `operator_agent.id` the server already resolved from a validated bootstrap token — never
  from anything the CSR claims. Covered by `TestSignCSR_IgnoresClientSuppliedSubject`.
- **Capacity-snapshot cluster ownership is re-validated per submission**, not assumed from the
  agent's registration alone — `registry.ClusterBelongsToOperator` is checked on every
  submission using the operator ID resolved from the agent's own database row (never a
  client-supplied operator ID).
- **Bootstrap tokens are genuinely single-use**: consumption, CSR signing, and certificate
  persistence all commit in one transaction, so a CSR that fails to sign correctly leaves the
  token consumable again for a legitimate retry, while a *successful* bootstrap can never be
  replayed. Unlike the Milestone 1 MFA-challenge bug, there is no fallible "guess" step after
  consumption here to create the same rollback-reuse class of bug — covered by
  `TestAgentBootstrapTokenIsSingleUse`.
- **Revocation is checked on every signature verification**, not just at bootstrap time — a
  revoked agent's still-cryptographically-valid, unexpired certificate is rejected. Covered by
  `TestAgentRevocationBlocksFurtherCapacitySnapshots`.

### Verification performed (not just claimed)
- All new migrations applied cleanly against a real Postgres, both via the automated test
  suite and via a from-scratch `control-api` binary start against an unmigrated database
  (confirmed all 6 new migrations apply in order).
- Fail-closed confirmed live: `control-api` refuses to start with `PKI_CA_ENCRYPTION_KEY`
  unset, and refuses to start (rather than silently generating a new CA) if given a *different*
  key than the one a previously-persisted CA was encrypted under.
- The mock connector CLI was run for real against a live instance (not just its unit-level
  callers): registered a real user, created and activated a real operator, created a real data
  centre and cluster, registered a real agent, ran the built binary against those live values,
  and confirmed via the API that the resulting `capacity_snapshots` row has
  `trust_status: "verified"` with correct attribution.
- The new frontend page was exercised in a real browser (Playwright against the pre-installed
  Chromium): logged in as a real operator owner, confirmed the region catalogue renders,
  created a data centre through the actual form and confirmed it appears in the list, and
  registered an agent through the actual form and confirmed the bootstrap-token banner
  appears.

### Milestone 2 acceptance checklist

| Requirement | Status |
|---|---|
| Architecture summary before implementation | ✅ stated at the start of implementation (design for the local CA, module boundaries, region/jurisdiction taxonomy ownership) |
| Complete files (no snippets) | ✅ every file created/modified in full |
| Migrations | ✅ `0012`-`0015`, all applied and idempotent |
| Seed data updates | ✅ demo operators get fictional data centres/clusters; global region taxonomy seeded; idempotent (verified via two runs) |
| Unit tests | ✅ 6 `internal/platform/pki` tests |
| Integration tests | ✅ 4 registry tests + 4 agents tests, all against a real Postgres via real HTTP |
| Security tests | ✅ cross-operator parent-reference rejection, invalid-signature rejection, bootstrap-token single-use, revoked-agent rejection |
| Frontend tests where applicable | ✅ existing vitest suite still passes; new page covered by real-browser verification (see above) since it is primarily server-interaction, not isolated component logic |
| Formatting / linting / type checking | ✅ gofmt, `go vet`, `golangci-lint` (0 issues), eslint, tsc — all clean across every touched app |
| Production builds | ✅ control-api, seed, mockconnector, worker all build; `next build` succeeds |
| Docker validation | Partial — `docker compose config -q` valid; full runtime validation still blocked by this sandbox's Docker Hub egress policy (same as Milestone 1, see Known Limitations) |
| Migration validation | ✅ fresh-database apply verified live, not just via the test harness |
| Updated documentation | ✅ ADR 0007, `docs/security/permission-matrix.md` regenerated, `docs/operations/local-development.md` updated |
| Updated project status | ✅ this document |
| Created/modified file list | ✅ see commit history on `claude/gridkeep-sovereign-ai-platform-l5ijoz` — one commit per coherent implementation step |
| Limitations | ✅ see Known Limitations below |
| Unresolved risks | ✅ see Unresolved Risks below |
| Next milestone not started | ✅ confirmed — no Milestone 3 (Sovereignty Policy Engine) code exists |

## Independent Security Audit of Milestone 1 (post-implementation, prior to Milestone 2)

An independent adversarial audit (code review + live exploitation against a running instance,
not trusting the original implementation's claims) found **1 Critical, 3 High, 2 Medium, 2 Low**
findings. Every Critical and High finding is fixed below with complete corrected files; the
Mediums and Lows were fixed too rather than merely noted. Full narrative, root cause, and fix
detail: `docs/adr/0006-post-milestone-1-security-audit-fixes.md`.

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | **Critical** | MFA challenge brute-force: a wrong TOTP guess rolled back the transaction that had marked the challenge consumed, silently un-consuming it — confirmed live (50 wrong guesses, then the correct code, still succeeded) | **Fixed** + regression test + live re-PoC (now fails) |
| 2 | **High** | Seed script's production gate was a denylist (`env == "production"`) — `"prod"`/`"staging"`/typos all bypassed it | **Fixed** (allowlist: `development` or `test` only) |
| 3 | **High** | Invitation `role_key` had no privilege ceiling — an inviter could name any role in scope with only an existence check | **Fixed** (`rbac.RoleGrantableBy`: target role's permissions must be a subset of the inviter's own role's permissions) |
| 4 | **High** | `.env.example` shipped a real, working `MFA_ENCRYPTION_KEY` rather than an obvious placeholder | **Fixed** (replaced with a value that is deliberately invalid base64, so the server refuses to start until a real key is generated) |
| 5 | Medium | `enterprise_tenants`/`operators` had zero Row-Level Security, unlike every other tenant/operator-owned table — confirmed via psql that a tenant-scoped query could read every tenant's row | **Fixed** (migration `0011`, same self-scope + platform-bypass policy pair as the membership tables) |
| 6 | Medium | `AcceptInvitation` never checked that the invited email matched the authenticated accepting user | **Fixed** (both tenancy and operators now verify email match, case-insensitive, before creating the membership) |
| 7 | Low | CSRF token comparison used plain `!=` instead of the already-existing, already-tested `security.ConstantTimeEquals` | **Fixed** |
| 8 | Low | Docker Compose published every port to `0.0.0.0`; no `Content-Security-Policy` response header | **Fixed** (ports bound to `127.0.0.1`; `default-src 'none'` CSP added) |

**What the audit found to be genuinely sound, not just unexamined**: Argon2id password hashing
with random per-password salts and constant-time comparison; atomic single-UPDATE consumption of
email-verification and password-reset tokens (no reuse possible, no rollback-reuse issue — that
pattern only broke for MFA challenges because of the *extra* fallible step, TOTP validation,
inserted between consumption and commit); session fixation (not applicable — every session token
is server-generated); the support-access dual-control constraint (both the Postgres `CHECK` and
the application-level self-approval check were confirmed unbypassable); the append-only audit
trigger (confirmed to hold even under `app.platform_bypass = true`); no SQL injection via string
concatenation anywhere in the codebase; no XSS-enabling patterns in the frontend; no hardcoded
secrets in application source.

**Re-verification after fixes**: every Milestone 1 acceptance check was re-run in full (gofmt,
`go vet`, `golangci-lint`, `go build`, `go test -p 1 ./...` for control-api and worker, `ruff` +
`mypy` + `pytest` for policy-engine, `eslint` + `tsc` + `vitest` + `next build` for web) — all
pass. See updated counts in Test Results below.

## Completed Work (Milestone 1)

### Monorepo & infrastructure
- npm workspace + Go workspace (`go.work`) monorepo scaffold.
- `docker-compose.yml`: Postgres 16, Redis 7, Redpanda, MinIO, Vault (dev mode), Mailpit.
  Config validated (`docker compose config -q`); full runtime validation blocked in this
  session by sandboxed Docker Hub registry access (see Known Limitations).
- `.env.example` covering every environment variable the code actually reads.

### control-api (Go, modular monolith)
- Platform layer: config loader, structured logging (slog), Postgres pool + embedded
  migration runner (`schema_migrations`-tracked, idempotent), Redis client, Argon2id password
  hasher, opaque-token generator, AES-256-GCM-encrypted TOTP manager, SMTP mailer, chi HTTP
  router with request logging, security headers, CORS, double-submit CSRF protection.
- **Identity module**: registration, email verification, Argon2id login, opaque
  DB-backed sessions, password reset (revokes all sessions), login-attempt lockout
  (constant-shape timing to avoid account-existence signal), TOTP MFA (enroll/confirm/
  disable, login challenge flow), step-up re-authentication endpoint.
- **Tenancy module**: enterprise tenant creation (creator becomes Enterprise Owner),
  profile view/update, member roster, email invitations, invitation acceptance.
- **Operators module**: mirrors tenancy (operator starts `pending_application`, only a
  platform administrator can activate it — see `platformadmin`).
- **RBAC module**: role/permission resolution, `RequireEnterprisePermission` /
  `RequireEnterpriseMembership` / `RequireOperatorPermission` / `RequireOperatorMembership` /
  `RequirePlatformPermission` chi middleware implementing the full mandatory authorization
  pipeline (session → membership → scope → role→permission → active-status → JIT
  support-access fallback), each opening a Row-Level-Security-scoped transaction.
- **Subscriptions module**: plan/feature catalogue, per-tenant/operator entitlement
  resolution with a Redis read-through cache (falls back to Postgres on cache miss/outage,
  never to "allow by default").
- **Audit module (`auditlog` + `platform/audit`)**: hash-chained, append-only `audit_events`
  (a `BEFORE UPDATE/DELETE` trigger blocks mutation even for the owning role, independent of
  RLS/grants), scoped read views per tenant/operator/platform.
- **Platform-admin module**: tenant/operator status & trust-level management, subscription
  plan assignment, and **just-in-time support access** with real dual control (a Postgres
  CHECK constraint plus a service-layer re-check both forbid self-approval), fully audited.
- Seed script (`cmd/seed`): fictional demo operators/tenants/users per the product spec,
  idempotent, only runs when `CONTROL_API_ENV` is exactly `development` or `test` (allowlist,
  tightened during the security audit — see below).

### worker (Go)
- Idempotent-consumer pattern (fetch → dedupe → handle-with-retry-and-backoff →
  dead-letter-on-exhaustion → commit) implemented against small interfaces, unit-tested with
  fakes (no live broker required for the tests). Real `kafka-go` adapter wired to Redpanda,
  **not runtime-validated against a live broker in this session** (see Known Limitations).

### policy-engine (Python)
- FastAPI service foundation (`/health`), Milestone 1 scope only — the actual sovereignty
  policy evaluation/simulation engine is Milestone 3 and is explicitly not started.

### web (Next.js 16 / React 19 / TypeScript / Tailwind)
- Pages: home, register, login (+ MFA challenge), verify-email, invitation acceptance
  (enterprise + operator, tried in sequence since a token alone doesn't indicate scope),
  enterprise/operator onboarding, dashboard (tenant + operator membership lists), tenant
  detail (profile, members, invite form gated by client-displayed role, subscription,
  audit log), operator detail (mirrors tenant detail).
- `lib/api.ts`: typed fetch client, CSRF-cookie-aware, `credentials: "include"`.
- Permission-aware UI: admin controls are shown/hidden based on the caller's own role, but
  the server independently re-checks every permission on every request regardless of what
  the client renders (client-side checks are UX only, never a security boundary).

### Fictional demo data
Seeded operators: **Gulf Horizon Telecom Demo** (AE), **EuroNorth Communications Demo** (DE).
Seeded tenants: **Falcon National Bank Demo** (AE), **Atlas Government Services Demo** (AE),
**Helix Manufacturing Demo** (DE). Every seeded row sets `is_fictional_demo_data = true`,
and the tenant/operator detail pages render a visible "Fictional demo data" badge when set.

**(Milestone 2)** Each demo operator also gets one fictional data centre and cluster: Gulf
Horizon Telecom Demo → Dubai DC1 → `gulf-horizon-gpu-cluster-1` (region `me-central-1`);
EuroNorth Communications Demo → Frankfurt DC1 → `euronorth-gpu-cluster-1` (region
`eu-central-1`). Two global jurisdictions (`AE`, `DE`) and regions (`me-central-1`,
`eu-central-1`) are seeded alongside them.

**Demo credentials** (local development only — never reuse, all clearly fictional):
password for every seeded account is `GridkeepDemo!2026`.
- `platform-admin@gridkeep.io` — Platform Super Administrator
- `owner@falcon-national-bank.demo.gridkeep.io` — Enterprise Owner, Falcon National Bank Demo
- `owner@atlas-gov.demo.gridkeep.io` — Enterprise Owner, Atlas Government Services Demo
- `owner@helix-manufacturing.demo.gridkeep.io` — Enterprise Owner, Helix Manufacturing Demo
- `owner@gulf-horizon-telecom.demo.gridkeep.io` — Operator Platform Owner, Gulf Horizon Telecom Demo
- `owner@euronorth-communications.demo.gridkeep.io` — Operator Platform Owner, EuroNorth Communications Demo

## Acceptance Criteria (from the approved Milestone 1 checklist)

| Criterion | Status |
|---|---|
| Monorepo builds; Compose stack starts cleanly | Partial — config valid, runtime blocked by sandbox network policy (see below) |
| Migrations apply cleanly forward | ✅ verified fresh + idempotent re-run |
| Register → verify → login → session → logout | ✅ verified via automated test + live browser (Playwright) |
| Password reset revokes old sessions | ✅ verified via automated test |
| MFA enrollment + login-attempt protection | ✅ verified via automated test |
| Tenant/operator creation, invitation, membership | ✅ verified via automated test + live browser |
| RBAC enforced on a protected route per scope | ✅ verified (tenant/operator/platform) |
| Cross-tenant/cross-operator access denied | ✅ verified via automated test (found and fixed a real bug — see Security Findings) |
| Platform admin cannot see tenant data without a support-access grant | ✅ verified via automated test (full dual-control flow) |
| Subscriptions/entitlements resolve correctly | ✅ verified (plan + feature seeding, cache fallback) |
| Every state-changing action produces an audit event | ✅ verified (hash chain + append-only trigger tests) |
| Fictional seed data loads and is visibly labeled | ✅ verified |
| CI passes: format, lint, type-check, unit+integration tests, container build, migration check | ✅ locally for every component; GitHub Actions workflow written but not yet executed on GitHub (see below) |
| `docs/project-status.md` reflects current milestone truthfully | ✅ this document |
| Complete file list delivered | ✅ see final response |
| Milestone 2 not started at time of writing | ✅ was true when this table was written; Milestone 2 is now complete (see above) — kept verbatim as the historical Milestone 1 acceptance record |

## Commands Executed (representative — all actually run, not claimed)

```
# control-api
cd apps/control-api
gofmt -l .                                    # clean
go vet ./...                                  # clean
golangci-lint run ./...                       # 0 issues (after fixing 14 real findings)
go build ./...                                # clean
go build -o /tmp/control-api-bin ./cmd/server
go build -o /tmp/seed-bin ./cmd/seed
go build -o /tmp/mockconnector-bin ./cmd/mockconnector
TEST_DATABASE_URL=postgres://gridkeep:...@localhost:5432/gridkeep_test?sslmode=disable \
  go test -p 1 ./... -v                       # 48/48 tests pass (Milestone 2)

# worker
cd apps/worker
gofmt -l . && go vet ./... && golangci-lint run ./...   # clean
go build ./... && go test ./...               # 4/4 tests pass

# policy-engine
cd apps/policy-engine
ruff check . && mypy src && python -m pytest -q         # clean, 1/1 test passes

# web
cd apps/web
npx eslint . && npx tsc --noEmit && npx vitest run       # clean, 5/5 tests pass
NEXT_PUBLIC_CONTROL_API_URL=http://localhost:8080 npx next build   # succeeds

# End-to-end (real browser, real backend, real Postgres/Redis, captured real SMTP traffic)
node smoke.js   # register → verify email → login → dashboard → create tenant → tenant detail
# => SMOKE TEST PASSED (run twice, including once after a full DB reset + reseed)
```

## Test Results

- **control-api**: 48 tests across `internal/app` (26: registration, login, lockout, MFA
  including the challenge-brute-force-lockout regression test, invitation create/accept/
  privilege-ceiling/email-mismatch flows, password reset, CSRF, cross-tenant/operator
  isolation, a direct database-level RLS proof for `enterprise_tenants`/`operators`,
  suspended-tenant regression, support-access dual control, 4 registry integration tests,
  4 agents integration tests), `internal/modules/rbac` (1: the `RoleGrantableBy`
  privilege-ceiling primitive), `internal/platform/audit` (3: hash chain, append-only
  trigger, RLS visibility), `internal/platform/security` (12: password hashing, opaque
  tokens, TOTP, constant-time comparison), `internal/platform/pki` (6, new in Milestone 2:
  encrypt/decrypt round-trip, CSR subject-spoofing rejection, malformed-CSR rejection,
  signature verification round-trip and cross-agent rejection) — **all passing**, run
  against a real PostgreSQL 16 test database (no mocks of persistence, RLS, or triggers).
- **worker**: 4 tests (success/commit, duplicate-delivery dedupe, retry-then-dead-letter,
  backoff calculation) — all passing.
- **policy-engine**: 1 test (`/health`) — passing. Full policy-evaluation test suite is
  Milestone 3 scope.
- **web**: 5 tests (API client error/CSRF handling, form validation) — all passing.
- **Browser smoke test** (Playwright, real Chromium, against the fully running stack):
  register → capture real SMTP email → verify → login → dashboard → create tenant → tenant
  detail renders profile/members/Enterprise-Owner membership. Passed twice, run before and
  after a from-scratch DB reset + fresh seed.

## Architecture Decisions

See `docs/adr/`:
- 0001 — modular monolith for the control plane
- 0002 — two-layer (application + PostgreSQL RLS) tenant/operator isolation
- 0003 — session and MFA model
- 0004 — manual zod validation instead of a broken `@hookform/resolvers`+zod-v4 combination
- 0005 — shared test database requires sequential (`-p 1`) package execution
- 0006 — post-Milestone-1 independent security audit findings and fixes
- 0007 — local development certificate authority for operator-agent identity (Milestone 2)

## Known Limitations

1. **Docker Hub registry access is blocked in this sandboxed session** (egress policy denies
   `production.cloudfront.docker.com`). `docker compose config` is syntactically validated;
   full `docker compose up` runtime validation (Postgres/Redis/Redpanda/MinIO/Vault/Mailpit
   actually starting and being reachable together via Compose) has **not** been performed.
   Everything was instead validated against natively-installed Postgres/Redis and a
   protocol-real fake SMTP server. **This must be the first thing re-verified in any
   environment with normal registry access.**
2. **Worker's live Kafka/Redpanda integration is untested against a real broker** for the
   same reason. The consumer's control-flow logic (dedupe, retry, backoff, dead-letter) is
   unit-tested against fakes and is correct; the `kafka-go` wiring itself has not been
   exercised end-to-end.
3. **SSO/SAML/OIDC/SCIM, WebAuthn/passkeys** are architecture-only, as agreed in the
   approved Milestone 1 scope — not implemented.
4. **`packages/ui` and other shared `packages/*`** from the target repository layout were not
   created, since Milestone 1 has exactly one frontend consumer; introducing a shared package
   with a single consumer would be premature abstraction. Revisit when a second frontend
   (operator or platform portal) is built.
5. `apps/scheduler`, `apps/operator-agent`, `apps/cluster-agent`, `apps/settlement-service`
   do not exist yet — correctly deferred to the milestones that build them (2, 5, 6, 7, 11
   per the approved sequence).
6. Entitlements are computed on demand from `subscriptions`/`plan_features` with a short-TTL
   Redis cache, rather than a separately persisted "entitlements" table — a deliberate
   simplification documented inline in migration `0007_subscriptions.up.sql`; revisit only if
   this join becomes a measured hot-path cost at higher milestones.
7. IP address recorded in `login_attempts`/session metadata is `r.RemoteAddr` (the real TCP
   peer), not resolved through `X-Forwarded-For` — correct for this sandbox's direct
   connections, but when control-api is deployed behind a real reverse proxy/load balancer, a
   trusted-proxy-aware IP resolver must be added (see Security Findings #1 below); until then,
   every request will show the proxy's IP, not the client's.
8. **(Milestone 2) The local development CA is not Vault-backed.** A real, working X.509 CA
   exists (`internal/platform/pki`), but the root of trust is a locally-generated,
   database-persisted key pair rather than a Vault-issued intermediate CA — see
   `docs/adr/0007-local-development-certificate-authority.md` for the full reasoning and the
   migration path when Vault integration lands for real.
9. **(Milestone 2) No real operator-agent or cluster-agent daemon exists yet** — correctly
   deferred to Milestone 6 ("Operator and Cluster Agents") per the approved sequence.
   `cmd/mockconnector` proves the control-plane side of the bootstrap/certificate/
   capacity-snapshot APIs work correctly against real cryptography, but does not run inside an
   operator's actual infrastructure or talk to a real Kubernetes API.
10. **(Milestone 2) No dedicated frontend UI for node pools, accelerators, storage pools,
    network capabilities, edge sites, or operator contracts** — the registry API fully
    supports all of them; only the frontend surface was scoped down to the core
    location → cluster → agent → capacity-snapshot chain to keep this milestone's UI
    proportionate. Revisit if a later milestone needs operators to manage these through the
    dashboard rather than the API directly.
11. **(Milestone 2) Certificate revocation is application-level only** (checked against
    `agent_certificates.revoked_at` on every signature verification), not CRL/OCSP-based —
    correct for this architecture, since control-api never terminates TLS itself (see ADR
    0007), but worth remembering if a future milestone introduces a real mTLS terminator in
    front of it, which would need its own revocation-checking story.

## Security Findings — implementation-phase (superseded/complemented by the audit above)

The findings below were found and fixed during the original Milestone 1 implementation, before
the independent audit. They are kept here for history; see the audit table above for the
findings from the subsequent independent review.

1. **Fixed**: `chi/middleware.RealIP` was in the router's middleware chain. It unconditionally
   trusts `X-Forwarded-For`/`X-Real-IP`/`True-Client-IP`, letting any client spoof the IP
   address recorded in `login_attempts` and audit evidence (GHSA-3fxj-6jh8-hvhx). Removed;
   `r.RemoteAddr` is used directly. See Known Limitation #7 for the follow-up needed once a
   real reverse proxy is introduced.
2. **Fixed**: `enterpriseMembershipPermission`/`operatorMembershipPermission` SQL queries
   passed an unused `$3`/`$4` bind parameter never referenced in the query text, which
   PostgreSQL rejects with "could not determine data type of parameter." This turned every
   permission-gated *write* to a tenant/operator (e.g. updating settings, sending an
   invitation) on a **suspended** tenant/operator into a 500 Internal Server Error instead of
   the intended 403 Forbidden — a fail-open-shaped bug (denial-of-service on legitimate
   requests, not a privilege escalation, but still a correctness/availability defect in a
   security-critical path). Found via manual testing, fixed, and now covered by an automated
   regression test (`TestSuspendedTenantBlocksMutationButNotOwnerRead`).
3. **Fixed**: JIT support-access usage was only audited on the `RequireEnterprisePermission`/
   `RequireOperatorPermission` code path, not on the `RequireEnterpriseMembership`/
   `RequireOperatorMembership` (read-only) path — meaning a support engineer *reading* tenant
   data via an approved grant left no audit trail, only *writing* did. Fixed; both paths now
   record `support_access.request_served`. Covered by
   `TestSupportAccessDualControl`'s audit-log assertion.
4. **Verified, no fix needed**: confirmed via a direct psql session that the `audit_events`
   append-only trigger blocks `UPDATE`/`DELETE` even when the connection has
   `app.platform_bypass = true` set (i.e. even the one GUC state that bypasses Row-Level
   Security does not bypass the append-only trigger, since triggers and RLS are independent
   enforcement mechanisms).

## Unresolved Risks

- Docker Compose runtime validation (Risk owner: whoever runs this next in an environment
  with registry access). Impact if wrong: local-dev onboarding instructions in
  `docs/operations/local-development.md` could have an error that only a real `docker compose
  up` would reveal.
- Kafka/Redpanda live integration (same category of risk as above, worker-specific).
- No load/chaos/performance testing yet — explicitly out of scope until Milestone 16.
- `@hookform/resolvers` + zod v4 incompatibility (ADR 0004) is a live upstream bug in
  third-party packages, not something GRIDKEEP can fix; the workaround is stable but should be
  revisited on the next dependency upgrade.
- **MFA brute-force is now bounded, not eliminated instantaneously.** A single challenge is
  capped at `MFA_MAX_ATTEMPTS` (default 5) and every failed attempt feeds the same
  `login_attempts`-based lockout that protects the password step, so an attacker who keeps
  minting fresh challenges will eventually trip `LOGIN_LOCKOUT_THRESHOLD` — but there is a
  window (a handful of guesses per newly-minted challenge, for however many challenges fit
  under the lockout threshold within `LOGIN_LOCKOUT_WINDOW_MINUTES`) before that lockout
  engages. TOTP's 10^6 keyspace makes this impractical over a network today; a future
  milestone should consider also rate-limiting challenge *creation* per account, not just
  attempts against an existing challenge.
- **The invitation privilege-ceiling fix (`rbac.RoleGrantableBy`) is defense-in-depth, not a
  fix for a currently-exploitable path.** In today's seed permission matrix, the only roles
  permitted to invite in each scope (`enterprise_owner`/`enterprise_admin`,
  `operator_platform_owner`) already hold a superset of every other role's permissions in
  that scope, so no privilege escalation was independently reachable before this fix — the
  fix exists so that remains true if the permission matrix or the invite-gating permission
  ever changes, rather than depending on that coincidence.
- **(Milestone 2) Capacity-snapshot ingestion deliberately bypasses RLS via
  `dbpkg.Scope{PlatformBypass: true}`**, since there is no session-derived `app.operator_id`
  GUC for a machine caller — the ECDSA signature check is the real authorization control,
  performed in application code before any row is read or written (see ADR 0007 and
  `agents.Service.SubmitCapacitySnapshot`'s doc comment). This is a deliberate, narrow
  exception to "RLS is always the backstop," and worth extra scrutiny in any future review of
  this specific code path, precisely because it is the only place in the codebase where that
  general rule doesn't apply.
- **No rate limiting on agent-facing routes** (`/api/v1/agent-bootstrap`,
  `/api/v1/agents/{agentID}/capacity-snapshots`) beyond the bootstrap token's own single-use
  property and the certificate signature check — a network-level flood of capacity-snapshot
  submissions against a *valid* agent's endpoint would still cost database writes before
  being rejected only by other means (none currently), though a request without a valid
  signature is rejected before any row is written. Revisit if this becomes a real concern once
  actual operator-agents exist (Milestone 6).

## Pending Approvals

None outstanding for Milestone 1 or Milestone 2. Awaiting explicit approval before any
Milestone 3 (Sovereignty Policy Engine) work begins.

## Next Action

Milestone 2 (Operator and Infrastructure Registry) is complete: schema, the local development
CA, the registry and agents modules, the mock operator connector, frontend pages, seed data,
and documentation are all built, tested, and re-verified. Await explicit approval (per working
rule #4) before starting Milestone 3 (Sovereignty Policy Engine) work. **No Milestone 3 code
has been written.**
