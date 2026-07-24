# Incident response runbook

This is the platform operator's own incident-response process for the
gridkeep control plane -- not to be confused with `internal/modules/
assurance`'s customer-facing incident tracking (`/incidents`,
`/operators/{operatorID}/incidents`), which is a tenant/operator-facing
SLA feature scoped by RLS to a single tenant or operator
(`docs/architecture/slo-validation.md` draws the same distinction for
SLOs). A platform incident may well involve creating or referencing
entries in that system as part of customer communication, but the
process below is broader: it also covers incidents that are entirely
internal (infrastructure, security) and never surface there.

## Severity

| Sev | Definition | Examples |
|---|---|---|
| 1 | Full outage, or any confirmed cross-tenant data exposure | control-api unreachable platform-wide; RLS bypass confirmed in production |
| 2 | Partial outage, or SLO burn-rate alert firing (`docs/architecture/slo-validation.md`'s >0.1% 5-minute error-rate query) | one AZ down; login error rate spiking; a single tenant/operator locked out |
| 3 | Degraded but functioning, no SLO breach yet | elevated p99 latency below SLO threshold; a background job (worker) falling behind |
| 4 | No customer impact | a single pod crash-looped and self-recovered; a CI security scan finding on an image not yet deployed |

Any suspected cross-tenant or cross-operator data exposure is **always**
at least Sev 1, regardless of how small the blast radius looks initially
-- see the dedicated playbook below.

## General lifecycle

1. **Detect** -- alert (Prometheus/Alertmanager on the queries in
   `docs/architecture/slo-validation.md`), a report, or a scheduled
   check-in noticing an anomaly.
2. **Triage** -- assign severity, open an internal incident record (a
   ticket/channel; this is process, not a feature this codebase
   implements for platform-internal incidents).
3. **Mitigate** -- stop the bleeding first (rollback, revoke, scale,
   failover). Root-causing can wait; user impact cannot.
4. **Resolve** -- confirm the mitigating action actually worked against
   the same signal that fired in step 1, not just "looks fine now."
5. **Postmortem** -- for Sev 1/2: what broke, why, what fixed it, and
   whether it reveals a gap in one of this milestone's own audit/testing
   documents (`docs/security/*-audit.md`, `docs/testing/chaos-testing.md`)
   that should be updated or turned into a new regression test, the same
   way this milestone repeatedly did during its own audits.

## Playbook: elevated error rate / SLO burn

1. Confirm against the actual PromQL in `docs/architecture/slo-validation.md`
   (`http_requests_total`/`http_request_duration_seconds` from
   `internal/platform/metrics`) -- don't act on a single dashboard glance.
2. Check the most recent deploy: `helm history gridkeep -n gridkeep`. If
   the timing lines up, `helm rollback` immediately
   (`docs/deployment/production-deployment.md`'s rollback section) --
   don't wait for root cause on a Sev 1/2.
3. If no recent deploy, check dependency health: RDS/ElastiCache/MSK
   status in the AWS console, then the specific playbooks below.
4. If the error is `500 INTERNAL_ERROR` with no further detail in the
   response body, that's expected behaviour, not a bug to "fix" in the
   response -- control-api never leaks internal error detail to callers
   (`docs/security/application-security-audit.md`). Get detail from
   `kubectl logs`, not the HTTP response.

## Playbook: database outage or degraded RDS

Expected behaviour during a real Postgres outage, confirmed by the actual
drill in `docs/testing/chaos-testing.md`: writes/reads fail with a clean
`500 INTERNAL_ERROR`, the process does not crash, and `/healthz` **stays
green** (known blind spot -- it never checks DB connectivity). Do not
trust pod `Ready` status as a signal here; check RDS directly.

1. Check RDS status/Multi-AZ failover state in the AWS console or
   `aws rds describe-db-instances`. Multi-AZ (enabled by default --
   `infrastructure/terraform/modules/database`) fails over automatically
   on an AZ-level failure; a full-cluster/region event does not
   self-heal and needs the DR runbook below.
2. If RDS is healthy but connections are being refused/exhausted, check
   `pg_stat_activity` for a connection-count problem before assuming an
   outage.
3. If this is a genuine full data-loss event (not just unavailability),
   stop here and switch to
   `docs/disaster-recovery/backup-and-restore-runbook.md` -- this
   playbook is for "the database is unreachable," not "the database's
   data is gone."

## Playbook: Redis/cache outage

Confirmed by `TestEntitlementsSurviveRedisOutage`
(`apps/control-api/internal/app/chaos_test.go`) and
`docs/testing/chaos-testing.md`: the entitlements cache
(`subscriptions.Service`, the only consumer of Redis in this codebase --
sessions and rate-limiting are Postgres-backed, not Redis) transparently
falls back to Postgres on a Redis outage. A Redis outage alone should
**not** cause user-facing errors, only increased load on Postgres and
slightly higher entitlement-check latency. If you're seeing errors (not
just latency) during a Redis incident, the actual cause is elsewhere --
don't stop investigating just because Redis is down.

Mitigation: restore the ElastiCache replication group (automatic failover
is enabled by default --
`infrastructure/terraform/modules/cache`'s `automatic_failover_enabled`).
No application-level action is needed to restore correctness; only to
restore the performance the cache exists for.

## Playbook: suspected cross-tenant or cross-operator data exposure

This is the most severe class of incident this platform can have --
sovereignty (tenant/operator isolation) is the platform's core promise.
Always Sev 1.

1. **Do not** attempt to "fix" anything by hand-editing rows or RLS
   policies live. First determine scope: which tenant(s)/operator(s),
   which table(s), and whether it's a data-at-rest issue (a row visible
   that shouldn't be) or a data-in-transit issue (a response containing
   another tenant's data).
2. Cross-reference `docs/security/tenant-isolation-audit.md` and
   `docs/security/operator-isolation-audit.md` immediately -- check
   whether the affected table is one of the documented "owner+grant-gated"
   marketplace tables (where visibility is *supposed* to widen under a
   grant) versus a plain two-policy RLS table (where it never should).
   A grant working as designed is not an incident; a policy gap is.
3. If it's a genuine gap: the fix is a migration adding/correcting an RLS
   policy, following the exact pattern every existing policy in this
   codebase uses (`NULLIF(current_setting('app.X', true), '')::uuid`,
   `FORCE ROW LEVEL SECURITY`) -- never a workaround at the application
   layer, since RLS is this platform's fail-closed backstop specifically
   because application-layer checks can be missed.
4. Pull the audit trail (`internal/modules/audit`) for every access to
   the affected rows during the exposure window -- this is what
   determines actual (not theoretical) blast radius and who needs to be
   notified.
5. Notification/compliance obligations are a business decision outside
   this document's scope, but do not close this incident without
   explicitly deciding that question, not defaulting to silence.
6. Postmortem is mandatory regardless of severity-after-mitigation:
   update the relevant audit document's finding list and add a
   regression test proving the specific gap is closed, the same way
   `TestPrivateCapacityOfferMarketplaceRLSDeniesNonGrantedTenant` was
   added this milestone specifically because the audit found no direct
   database-layer test for marketplace-grant RLS.

## Playbook: compromised operator agent or cluster-agent certificate

1. Revoke immediately:
   `POST /operators/{operatorID}/agents/{agentID}/revoke` or the
   `cluster-agents/{clusterAgentID}/revoke` equivalent
   (`internal/modules/agents`, `docs/runbooks/operations.md`).
2. **Known gap**: there is no test proving a revoked certificate is
   rejected on an already-established connection mid-session (informational
   finding, `docs/security/operator-isolation-audit.md`). Assume the
   revoked identity may still be trusted until it next attempts a fresh
   signature-verified request and is rejected, or until network-level
   access is cut off separately (security group / NetworkPolicy).
3. Audit every control message and capacity snapshot signed by that
   identity since suspected compromise (`internal/modules/agents`,
   `control_messages` / `capacity_snapshots` tables) before trusting any
   of it.
4. Re-issue a new certificate through the normal bootstrap flow once the
   operator's underlying credential material is confirmed clean.

## Playbook: compromised platform/support credential

1. Revoke the specific support-access grant:
   `POST /support-access-grants/{grantID}/revoke`
   (`platform.support_access.grant`, `internal/modules/platformadmin`).
2. Force a password reset for the compromised platform account
   (`ResetPassword`, not `ChangePassword` -- only the former revokes all
   existing sessions, see `docs/runbooks/operations.md`).
3. If the account has TOTP/MFA enrolled and there's any chance the
   second factor is also compromised, disenroll and require re-enrollment
   before restoring access.
4. Audit every action taken under that account/grant during the
   suspected compromise window (`internal/modules/audit`) -- support
   access is deliberately time-boxed and logged for exactly this reason.

## Playbook: bad deployment

See `docs/deployment/production-deployment.md`'s rollback section.
Short version: `helm rollback`, remembering it reverts Kubernetes objects
only, never a database migration -- a bad schema change needs a
forward-fix migration or a restore from backup, not a rollback.

## Playbook: node / cluster degradation

PodDisruptionBudgets (`minAvailable: 1` on every service) and the EKS
managed node group's `update_config.max_unavailable = 1`
(`infrastructure/terraform/modules/eks`) should absorb a single-node
failure without user impact. If pods are pending/unschedulable, check
node group capacity first (`kubectl get nodes`,
`aws eks describe-nodegroup`) before assuming an application-level
problem -- a capacity shortfall looks identical to a crash-loop from the
Service's point of view but has a completely different fix (scale the
node group, not redeploy the application).
