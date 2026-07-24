# Operational runbook

Day-to-day operating procedures for the gridkeep control plane
(control-api, worker, policy-engine, web). For a live incident, use
`docs/runbooks/incident-response.md` instead -- this document is for
routine and semi-routine tasks, not "something is on fire."

## Health and status checks

```bash
kubectl -n gridkeep get pods
kubectl -n gridkeep rollout status deployment/gridkeep-control-api
kubectl -n gridkeep top pods            # requires metrics-server
```

`GET /healthz` (liveness/readiness probe target for control-api and
worker) is process-liveness only -- it never checks Postgres/Redis
connectivity (documented gap, `docs/testing/chaos-testing.md`). A pod
reporting `Ready` proves the process is up, not that its dependencies
are reachable. For actual dependency health, use the Prometheus queries
in `docs/architecture/slo-validation.md` (error rate, latency, the
`http_requests_total` / `http_request_duration_seconds` series from
`internal/platform/metrics`) against the `:9090/metrics` endpoint --
never exposed on the same Service as application traffic (see the
NetworkPolicy in `infrastructure/helm/gridkeep/charts/control-api`
restricting it to the `monitoring` namespace).

## Scaling

control-api autoscales on CPU via the chart's HPA (min 2 / max 6 / 70%
target -- `infrastructure/helm/gridkeep/charts/control-api/values.yaml`).
worker, policy-engine, and web do not have an HPA in this milestone;
scale them manually if load requires it:

```bash
kubectl -n gridkeep scale deployment/gridkeep-worker --replicas=<n>
```

To raise the ceiling itself (HPA max, node group size), change the
relevant Helm value or the `eks_node_max_size`/`eks_node_desired_size`
Terraform variable and re-apply -- see
`docs/deployment/production-deployment.md`.

## Restarting a pod / rolling restart

```bash
kubectl -n gridkeep rollout restart deployment/gridkeep-control-api
```

Because `Store.Migrate` runs on every control-api process start and the
Helm chart's `RollingUpdate` strategy caps `maxSurge` at 1 specifically
to keep that safe (see the comment in
`infrastructure/helm/gridkeep/charts/control-api/templates/deployment.yaml`),
a rolling restart of control-api is always safe to run at any time,
including mid-incident -- it will never race two migration attempts
against each other.

## Logs

```bash
kubectl -n gridkeep logs deploy/gridkeep-control-api --tail=200 -f
kubectl -n gridkeep logs deploy/gridkeep-control-api --previous   # last crash
```

All four services log structured JSON to stdout (see
`docs/architecture/observability.md`); there is no log-shipping/
aggregation layer configured in this milestone, so `kubectl logs`
against the currently-running (or `--previous`, most-recently-crashed)
container is the only access path until one is added.

## Rotating credentials

### Database / cache credentials (Terraform-managed)

`random_password`/`random_bytes` resources in
`infrastructure/terraform/modules/{database,cache,secrets}` are the
source of truth. Rotating any of them:

```bash
cd infrastructure/terraform/environments/production
terraform taint module.database.random_password.master     # or the cache/secrets equivalent
terraform apply
```

then update the corresponding AWS Secrets Manager JSON (automatic, since
`terraform apply` recomputes the `secrets` module's
`aws_secretsmanager_secret_version` from the new value) and re-sync the
Kubernetes Secret (`docs/deployment/production-deployment.md`'s "Bridge
Secrets Manager into Kubernetes" section), then roll every pod that reads
it (`kubectl rollout restart`).

### The three application encryption keys

`MFA_ENCRYPTION_KEY`, `PKI_CA_ENCRYPTION_KEY`, `SECRETS_VAULT_ENCRYPTION_KEY`
each protect data already encrypted at rest under the *current* key
(TOTP secrets, the PKI CA private key, workload secrets respectively --
see `docs/security/cryptographic-review.md`). Rotating one of these in
Terraform (`terraform taint module.secrets.random_bytes.<name>`) changes
the key new writes use, but this codebase has **no re-encryption
migration** for data already written under the old key -- rotating one
of these three without a corresponding data migration will make existing
encrypted rows unreadable. Treat this as a two-step operation:
1. Write and test a re-encryption pass (decrypt-under-old-key,
   re-encrypt-under-new-key) for the affected table before rotating.
2. Only then taint/apply the key and deploy.
This gap (no rotation-with-re-encryption tooling exists yet) is a known
limitation, not something to route around by rotating anyway.

### The `gridkeep_backup` database role

Rotate its password directly in Postgres (it is not Terraform-managed --
see `docs/disaster-recovery/backup-and-restore-runbook.md` for why this
role exists) and update wherever the backup job's credentials are stored.

## Revoking a compromised operator agent or cluster agent certificate

```
POST /api/v1/operators/{operatorID}/agents/{agentID}/revoke
POST /api/v1/operators/{operatorID}/cluster-agents/{clusterAgentID}/revoke
```

(`internal/modules/agents`, `operator.agents.manage` permission required).
**Known gap**: this revokes the certificate's status in the database, but
there is no test proving an already-established connection using the
now-revoked certificate is rejected mid-session (see
`docs/security/operator-isolation-audit.md`'s informational finding).
After revoking, treat any in-flight session from that agent as still
possibly trusted until it naturally reconnects (and is rejected on the
next signature check) or until the corresponding Kubernetes-side network
path is manually cut off.

## Revoking a compromised enterprise user's sessions

There is no bulk "revoke all sessions for this user" admin action.
`ChangePassword` does not revoke other active sessions (known gap,
`docs/security/application-security-audit.md`). Until that's fixed, the
working procedure is: force a password reset (`RequestPasswordReset` +
`ResetPassword`, which **does** revoke other sessions per that same
audit), and if platform-level intervention is needed, use the support-access
grant workflow (`platform.support_access.grant`,
`internal/modules/platformadmin`) to act on the tenant's behalf rather
than trying to directly invalidate session rows.

## Routine maintenance cadence

- **Dependency scanning**: runs on every CI push (govulncheck, pip-audit,
  npm audit, Trivy -- `.github/workflows/ci.yml`). Treat a new HIGH/CRITICAL
  finding on `main` as a scheduling trigger for a patch release, not
  something to action ad hoc against a running deployment.
- **RDS automated backups**: verify retention is actually happening
  (`aws rds describe-db-instances` -- `LatestRestorableTime` should be
  within minutes of now) monthly, independent of the manual `pg_dump` drill
  in `docs/disaster-recovery/backup-and-restore-runbook.md`.
- **Certificate rotation**: operator/cluster-agent certificates rotate via
  the existing `internal/modules/agents` rotation endpoints -- follow
  whatever cadence the operator's own contract specifies
  (`operator_contracts`), not a fixed platform-wide schedule.
- **TLS termination**: this platform's own code has no explicit TLS
  configuration anywhere (deliberately left to the terminating layer --
  `docs/security/cryptographic-review.md`); check the Ingress
  controller's/cert-manager's own certificate expiry monitoring
  separately, since nothing here does it.
