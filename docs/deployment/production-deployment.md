# Production deployment guide

How `infrastructure/terraform`, `infrastructure/helm/gridkeep`, and
`.github/workflows/ci.yml` fit together into one deploy, end to end. This is
a procedure document, not a description of something that has been run
against a live AWS account from this sandbox -- see "What has and hasn't
been executed" at the end.

## Overview

```
 developer            CI (.github/workflows/ci.yml)              AWS
 ─────────            ────────────────────────────              ───
 push/PR  ──────▶  test, lint, govulncheck/pip-audit/npm audit
                   │
                   ▼ (on push to main only)
                   build image per service (Dockerfiles)
                   Trivy scan (blocks on CRITICAL-with-fix)
                   Syft SBOM (SPDX)
                   push to GHCR + cosign keyless sign
                                     │
                                     ▼
                              operator/CI runs:
                              terraform apply   (infrastructure/terraform)
                              helm upgrade      (infrastructure/helm/gridkeep)
```

Terraform owns everything below the Kubernetes API (VPC, EKS, RDS,
ElastiCache, MSK, S3, Secrets Manager). Helm owns everything the Kubernetes
API knows about (Deployments, Services, NetworkPolicies, HPA, Ingress).
Neither tool is aware of the other's resources directly -- they're bridged
by a handful of Terraform outputs an operator (or a deploy pipeline) copies
into Helm's `values`/`--set` flags and into Kubernetes Secret objects, by
hand, as described below.

## 1. One-time backend bootstrap

Terraform's own remote-state storage cannot be created by the same `apply`
that will use it. Once, before anything else:

```bash
aws s3api create-bucket --bucket gridkeep-terraform-state --region us-east-1
aws s3api put-bucket-versioning --bucket gridkeep-terraform-state \
  --versioning-configuration Status=Enabled
aws dynamodb create-table --table-name gridkeep-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

Then uncomment the `backend "s3"` block in
`infrastructure/terraform/environments/production/versions.tf`.

## 2. Provision infrastructure

```bash
cd infrastructure/terraform/environments/production
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars -- artefacts_bucket_name MUST be changed, S3 bucket
# names are globally unique across all of AWS.
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Capture the outputs a Helm deploy will need:

```bash
terraform output -raw configure_kubectl | bash   # aws eks update-kubeconfig ...
terraform output control_api_secret_arn
terraform output worker_secret_arn
terraform output web_secret_arn
```

## 3. Bridge Secrets Manager into Kubernetes

`infrastructure/terraform/modules/secrets` deliberately stops at AWS
Secrets Manager -- see that module's own comment for why (adding a
Kubernetes provider block to the Terraform stack would require a live,
reachable cluster just to run `terraform plan`). Two ways to close this
gap, in increasing order of operational maturity:

**Manual bootstrap** (fastest path to a first deploy):

```bash
for svc in control-api worker web; do
  aws secretsmanager get-secret-value \
    --secret-id "gridkeep-production/${svc}" \
    --query SecretString --output text \
  | jq -r 'to_entries[] | "--from-literal=\(.key)=\(.value)"' \
  | xargs kubectl create secret generic "gridkeep-${svc}-secrets" \
      --namespace gridkeep
done
```

**External Secrets Operator** (recommended for anything past the first
deploy, since it re-syncs on rotation instead of drifting silently):
install ESO, then create one `ExternalSecret` per service pointing at the
three ARNs above, targeting the same `gridkeep-<service>-secrets` names the
Helm charts already reference via `existingSecret`.

Either way, do this **before** step 4 -- `envFrom.secretRef` in every
Deployment will fail to start the pod if the named Secret doesn't exist yet
(the pod stays in `CreateContainerConfigError`, not a crash loop).

## 4. Deploy with Helm

```bash
cd infrastructure/helm/gridkeep
helm dependency update
helm upgrade --install gridkeep . \
  --namespace gridkeep --create-namespace \
  --set global.imageRegistry=ghcr.io/<org> \
  --set control-api.image.tag=<git-sha-or-release-tag> \
  --set worker.image.tag=<git-sha-or-release-tag> \
  --set policy-engine.image.tag=<git-sha-or-release-tag> \
  --set web.image.tag=<git-sha-or-release-tag>
```

Image tags should be the same immutable tag CI pushed and cosign-signed in
`container-security` job of `.github/workflows/ci.yml` -- never `latest`,
so a rollback (`helm rollback`) actually rolls back to a specific,
previously-verified image rather than whatever `latest` currently resolves
to.

### Migrations run themselves -- with one rollout constraint

control-api's `Store.Migrate` (`internal/platform/db/migrate.go`) runs on
every process start and is checksum-idempotent -- there is no separate
migration Job to run. The one thing this requires from the rollout: at most
one *new* control-api pod starting at a time, so two brand-new pods never
race to apply the same not-yet-applied migration simultaneously (old pods
never re-run `Migrate`, so they're never part of this race). The
control-api Deployment template sets `strategy.rollingUpdate.maxSurge: 1`,
`maxUnavailable: 0` specifically to guarantee this -- do not override it to
a higher `maxSurge` via `--set` on a rollout that includes a new migration.

### Verify the rollout

```bash
kubectl -n gridkeep rollout status deployment/gridkeep-control-api
kubectl -n gridkeep get pods
kubectl -n gridkeep logs deploy/gridkeep-control-api --tail=50 | grep -i migrat
```

A successful `Migrate` call logs the list of newly-applied migration
versions (or an empty list, on a redeploy with no schema changes) --
absence of a migration-related error in the first pod's logs is the signal
the schema is current.

### Smoke test

```bash
kubectl -n gridkeep port-forward svc/gridkeep-control-api 8080:8080 &
curl -sf http://localhost:8080/healthz
# authenticated smoke test against a real seeded account is the more
# meaningful check -- see docs/testing/performance-and-load-testing.md's
# login-path measurement for what a healthy response looks like.
```

`/healthz` is a liveness-only check (see the known-limitation note in
`docs/testing/chaos-testing.md` -- it never checks Postgres/Redis). A
`200` from it proves the process is up, not that its dependencies are
reachable; check `kubectl get pods` for `Ready` status too, since the
readiness probe hits the same endpoint today.

## 5. Rollback

```bash
helm rollback gridkeep <previous-revision> --namespace gridkeep
```

This only rolls back the Kubernetes objects (images, config, replica
counts) to a prior Helm release -- it does **not** roll back a database
migration. Because `internal/platform/db/migrate.go` has no down-migration
concept (every migration file in
`apps/control-api/internal/platform/db/migrations` is forward-only), a bad
schema change requires either a forward-fix migration or a restore from
backup (`docs/disaster-recovery/backup-and-restore-runbook.md`), not a
Helm rollback. Plan schema changes accordingly: additive/backward-compatible
migrations that a rolled-back older binary can still run against, the same
discipline this platform has followed in every earlier migration file.

Infrastructure changes follow the normal Terraform workflow
(`terraform plan`/`apply` against a reverted commit, or a targeted
`-target=` apply for an isolated fix) -- there is no Terraform-native
"rollback" beyond that.

## 6. What to watch after a deploy

- `docs/architecture/observability.md` / `docs/architecture/slo-validation.md`
  -- the Prometheus metrics and PromQL queries that define "healthy" for
  control-api specifically.
- `docs/testing/chaos-testing.md` -- known failure-mode behaviour (Redis
  outage: transparent Postgres fallback; Postgres outage: clean 500s, no
  crash; `/healthz` blind spot).
- CI's `container-security` job -- SARIF results land in the repo's code
  scanning tab; a HIGH finding on an already-deployed image is a
  non-blocking signal to schedule a rebuild, not an incident by itself.

## What has and hasn't been executed

This sandbox has no AWS account, no live Kubernetes cluster, and no Docker
daemon (`ulimit: error setting limit (Operation not permitted)` starting
dockerd -- see `docs/project-status.md`'s Milestone 16 section and
`docs/security/supply-chain-review.md` for the exact constraint). Every command in this
guide has been written against, and cross-checked line-by-line with:

- the actual Terraform module outputs (`infrastructure/terraform/*/outputs.tf`)
- the actual Helm chart's `existingSecret` values and templated env vars
  (`infrastructure/helm/gridkeep/charts/*/values.yaml` and
  `templates/deployment.yaml`)
- the actual migration runner's real behaviour
  (`apps/control-api/internal/platform/db/migrate.go`)

but the full sequence (bootstrap → apply → bridge secrets → helm upgrade →
smoke test → rollback) has never been run start-to-finish against a real
AWS account from within this environment, matching every other "written
correctly, hand/tool-verified, not live-verified" limitation already
disclosed for Docker builds, Helm's `get.helm.sh` download, and Terraform's
provider registry throughout Milestone 16.
