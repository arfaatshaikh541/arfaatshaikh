# GRIDKEEP production readiness review

Capstone review at the close of Milestone 16 (Production Hardening), the
last of the 16 milestones in this project's architecture brief. This
document is the single place to look for "is this ready, and if not,
what's left" -- it consolidates findings scattered across two dozen other
documents rather than repeating their detail. Read the linked document for
the full writeup of anything summarized here.

## What GRIDKEEP is

A sovereign AI network exchange control plane: enterprise tenants place
AI/ML workloads onto operator-provided infrastructure under
policy-as-code sovereignty constraints, with placement, deployment,
attestation, network services, billing, bilateral capacity agreements, a
cross-tenant AI model exchange, and energy-aware scheduling all built as
extensions of one modular-monolith Go control-api, never a sprawl of
microservices. Sixteen milestones built this incrementally; this document
does not re-derive that history -- see `docs/project-status.md` for the
per-milestone build log.

## Milestone-by-milestone completeness

| # | Milestone | Status |
|---|---|---|
| 1 | Identity, tenancy, RBAC, subscriptions, audit foundation | Complete |
| 2 | Operator/infrastructure registry (regions, data centres, clusters) | Complete |
| 3 | Sovereignty policy engine (policy-as-code, dual-control publish) | Complete |
| 4 | Workload and model registry, artefact storage | Complete |
| 5 | Placement and capacity engine | Complete |
| 6 | Operator and cluster agents (delegated, cert-authenticated) | Complete |
| 7 | Secure deployment orchestration, envelope-encrypted workload secrets | Complete |
| 8 | Confidential computing and attestation gating | Complete |
| 9 | Network and edge services | Complete |
| 10 | Service assurance: SLOs, incidents, alerts (tenant/operator-facing) | Complete |
| 11 | Usage, billing, and settlement | Complete |
| 12 | Federated capacity exchange (bilateral agreements, degraded mode) | Complete |
| 13 | AI model exchange (cross-tenant marketplace) | Complete |
| 14 | Energy-aware scheduling | Complete |
| 15 | Enterprise/operator/platform portal completeness, accessibility, RTL | Complete |
| 16 | Production hardening (this milestone) | Complete |

Every milestone's own `docs/project-status.md` section records its test
suite, migration validation, and seed data. Nothing in Milestone 16 revisited
or re-scoped functionality from Milestones 1-15 except where an audit found
a genuine, in-scope gap (see the risk register below).

## What has been proven for real in this milestone

Unlike a document-only hardening pass, Milestone 16 backed nearly every
claim with something that actually ran:

- **Tenant/operator isolation**: every RLS policy inventoried against the
  actual migrations; a new raw-database-layer test
  (`TestPrivateCapacityOfferMarketplaceRLSDeniesNonGrantedTenant`) closed
  the one gap the audit found in direct proof of marketplace-grant RLS.
- **Application security**: `TestSecurityHeadersPresent` and a live audit
  of every repository query, every frontend render path, and every secret
  source.
- **Disaster recovery**: a real drill -- dropped a database, restored a
  537 KB `pg_dump`, confirmed byte-identical row counts across 108 tables,
  and ran the full `internal/app` test suite against the restored database
  to prove functional, not just row-count, correctness. Found and fixed two
  real Postgres-role bugs in the process (`FORCE ROW LEVEL SECURITY`
  blocking `pg_dump` as the app role; schema-creation privilege separate
  from `BYPASSRLS`).
- **Performance/load**: real `hey`-driven load against the actual
  `internal/app` router behind a real `httptest.Server` -- 17,729 req/s on
  `/healthz`, 64.9 req/s on the Argon2id-gated login path (by design, not a
  bug), ~1,100-1,200 req/s on an authenticated, DB-backed endpoint.
- **Chaos testing**: a real Redis-outage regression test
  (`TestEntitlementsSurviveRedisOutage`) plus a real, manually executed
  Postgres-outage drill (`sudo service postgresql stop`/`start`) confirming
  clean `500`s and no crash -- and finding the real `/healthz` blind spot.
- **Helm**: validated with a real, self-built `helm` binary --
  `helm lint --with-subcharts` (9 charts, 0 failed) and `helm template`
  producing all 20 expected Kubernetes objects, reproducibly.
- **Terraform**: validated with a real, self-built `tofu` (OpenTofu)
  binary against the **actual AWS/random/tls provider plugins**
  (downloaded directly from `releases.hashicorp.com` and served through a
  filesystem-mirror workaround, since the registry's discovery API is
  blocked in this sandbox) -- `tofu validate` passed, and `tofu plan`
  proceeded through every local resource before failing only at the AWS
  STS call that requires a real account. This caught a genuine bug (an
  `aws_security_group` description exceeding AWS's 255-character limit).

## What remains structurally sound but not live-verified

Consistent with every prior milestone's honest disclosure of the same
class of sandbox limitation (Docker Hub egress since Milestone 1):

- **Docker builds**: all four Dockerfiles are hand-verified, not
  build-verified -- this sandbox's Docker daemon cannot start
  (`ulimit: error setting limit (Operation not permitted)`).
- **CI/CD's new supply-chain steps** (Trivy, Syft SBOM, cosign signing,
  govulncheck): written and reviewed, will run for real the first time
  this repository executes on GitHub Actions, whose runners have both a
  Docker daemon and unrestricted internet.
- **A live `terraform apply`**: never run against a real AWS account from
  this sandbox. IAM permissions, service quotas, region capacity for the
  chosen instance types, and MSK's broker-count-per-AZ constraint are all
  unverified until a real apply happens.
- **A live Helm deploy against a real cluster**: `helm template` output has
  been reviewed object-by-object, but no `helm upgrade --install` has run
  against an actual API server.
- **The full deployment sequence** in
  `docs/deployment/production-deployment.md` (bootstrap → apply → bridge
  secrets → helm upgrade → smoke test → rollback): documented and
  cross-checked against real code, never executed start-to-finish.

None of this is a gap in the *work* -- it's an honest boundary of what a
sandboxed environment with no cloud credentials, no Docker daemon, and a
restricted egress allowlist can prove. The first real exercise of all of
the above happens the first time this repository is deployed from an
environment that has those things.

## Consolidated risk register

Every open (non-informational, non-fixed) finding from this milestone's
audits, in one place:

| Severity | Finding | Status | Source |
|---|---|---|---|
| Medium | `support_access_grants` has no RLS despite a scope-shaped column identical in purpose to every other scoped table | Open, not exploitable today (app-layer checks still gate access), defense-in-depth gap | `docs/security/tenant-isolation-audit.md` Finding 1, shared by `docs/security/operator-isolation-audit.md` Finding 1 |
| Medium | Zero content validation on Kubernetes manifests/quotas/network policies/security contexts in `internal/platform/clusteradapter` -- everything is an opaque `map[string]any` | Open. Not exploitable today (no real `client-go` integration exists anywhere in this codebase), but **must be closed before any real Kubernetes client integration is added** | `docs/security/kubernetes-security-audit.md` |
| Medium | `Register` and `RequestPasswordReset` have no rate limiting (only `Login` does) -- real, unbounded registration/reset-request spam vector | Open, tracked, not fixed this milestone (scoped as its own follow-up rather than an audit-remediation-sized change) | `docs/security/application-security-audit.md` |
| Low-Medium | `/healthz` is liveness-only, never checks Postgres/Redis -- confirmed to stay "healthy" through a real total DB outage in the chaos drill | Open, tracked in the Helm chart's own values.yaml comment and every M16 runbook/deployment doc that references it | `docs/testing/chaos-testing.md` |
| Low | `ChangePassword` does not revoke other active sessions (unlike `ResetPassword`, which does) | Open, workaround documented (`docs/runbooks/operations.md`: force a `ResetPassword` instead) | `docs/security/application-security-audit.md` |
| — (found this milestone, outside the audits) | The three application encryption keys (`MFA_ENCRYPTION_KEY`/`PKI_CA_ENCRYPTION_KEY`/`SECRETS_VAULT_ENCRYPTION_KEY`) have no re-encryption tooling -- rotating one without a data migration breaks existing encrypted rows | Open, documented as a hard prerequisite before ever rotating one in production | `docs/runbooks/operations.md` |
| Informational | Operator/cluster-agent certificate revocation is checked in application code, not cryptographically enforced at the transport layer; no test proves a revoked certificate is rejected on an already-established connection mid-session | Open, informational -- documented playbook assumes revoked-but-still-trusted until reconnect | `docs/security/operator-isolation-audit.md` Findings 2 and 3 |
| Informational | No explicit TLS configuration anywhere in application code (deliberately left to the terminating layer -- ALB/Ingress/RDS `rds.force_ssl`) | Accepted as-is; Terraform's `database` module sets `rds.force_ssl=1` specifically to close this at the DB-connection layer | `docs/security/cryptographic-review.md` |
| Informational | `network_service_offers`/`price_books` remain blanket "any tenant, status=active" visibility, unlike `capacity_offers`/`model_versions` | Confirmed intentional via migration 0036's own header comment; worth revisiting if the product intent changes, not a bug today | `docs/security/tenant-isolation-audit.md` Finding 3 |
| Informational | One hardcoded (but guarded, clearly-fictional) demo password in `cmd/seed/main.go` | Accepted -- seed data is never run against a production database | `docs/security/application-security-audit.md` |

**Fixed this milestone** (for completeness, not part of the open register):
missing raw-DB-layer RLS test for marketplace grants; no HSTS header; the
`pg_dump`/`pg_restore` role-privilege bugs found during the DR drill; the
control-api rolling-update migration race (added `maxSurge: 1`).

## Go/no-go assessment

**Ready to deploy to a real AWS environment and exercise the full pipeline
for the first time.** Nothing in the risk register above blocks a first
production deployment -- every open finding is either genuinely
not-yet-exploitable (no real K8s client, no real transport-layer agent
connections yet), has a documented operational workaround, or is an
accepted, intentional trade-off.

**Before onboarding real tenant data or real operator infrastructure**,
treat the following as launch-blocking, not backlog:
1. Add Kubernetes manifest content validation
   (`docs/security/kubernetes-security-audit.md`) **before** wiring
   `internal/platform/clusteradapter` to a real `client-go` client --
   today's opaque-map validation is fine only because nothing real is
   being sent to a real cluster yet.
2. Add rate limiting to `Register`/`RequestPasswordReset` before this
   platform is reachable from the public internet with real user
   registration open.
3. Run the full deployment sequence in
   `docs/deployment/production-deployment.md` against a real, disposable
   AWS environment at least once, end-to-end, before it is ever run
   against the real production account -- this validates the one thing
   this sandbox structurally cannot: that `terraform apply` and
   `helm upgrade` actually succeed together, not just independently.

Everything else in the risk register is safe to carry as tracked
technical debt into initial operation.

## Confirmation

This document closes Milestone 16, the last of the 16 milestones defined in
this project's architecture brief. No Milestone 17 work exists or has been
started -- per this project's standing rule, work stops here pending
explicit approval for whatever comes next (a Milestone 17, if the brief is
extended, or the project's conclusion). `docs/project-status.md`'s
Milestone 16 section is the final, complete build record and full file
manifest for this milestone.
