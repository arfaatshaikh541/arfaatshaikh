# GRIDKEEP control-plane infrastructure (Terraform)

This provisions the AWS infrastructure the GRIDKEEP control plane (control-api,
worker, policy-engine, web -- deployed via `infrastructure/helm/gridkeep`)
runs on. It does **not** provision anything on the operator side: operators
bring their own Kubernetes clusters and are reached only through the existing
mock-agent/cluster-agent pattern in
`apps/control-api/internal/platform/clusteradapter`, exactly as in every
prior milestone.

## Why AWS

The architecture brief this project was built against does not specify a
cloud provider anywhere -- every other infrastructure-facing module in this
codebase (billing, energy/carbon, attestation, network services) resolved
the same ambiguity by picking one concrete, illustrative provider behind an
explicit abstraction, structured so a different one could be swapped in
later. Terraform follows that same precedent: AWS is the concrete choice,
the module boundaries (`networking`, `eks`, `database`, `cache`,
`message-queue`, `object-storage`, `secrets`) are what would need
provider-specific rewrites for GCP/Azure, and nothing above those module
boundaries (Helm charts, application code) has any AWS-specific assumption
baked in beyond generic S3-API compatibility (already true of
`internal/platform/storage`, which talks to MinIO locally today).

## Layout

```
modules/
  networking/       VPC, public/private subnets across 3 AZs, NAT gateways,
                     S3 gateway endpoint
  eks/               EKS cluster, managed node group, IRSA OIDC provider
  database/          RDS PostgreSQL 16, Multi-AZ, encrypted, force-SSL
  cache/             ElastiCache Redis, encrypted at rest + in transit
  message-queue/     MSK (managed Kafka)
  object-storage/    S3 bucket (artefacts) + scoped IAM user for it
  secrets/           AWS Secrets Manager: generates the three
                     required-no-fallback encryption keys
                     (MFA_ENCRYPTION_KEY, PKI_CA_ENCRYPTION_KEY,
                     SECRETS_VAULT_ENCRYPTION_KEY) and assembles the JSON
                     blobs matching the three existingSecret references in
                     infrastructure/helm/gridkeep's values.yaml files
environments/
  production/        Root module wiring all seven together
```

Every module maps to one item on Milestone 16's own list (networking,
database, cache, message queue, object storage, secrets, k8s cluster).

## Getting from Secrets Manager to a Kubernetes Secret

This stack stops at Secrets Manager -- it never adds a Kubernetes provider
block, which would require a live, reachable cluster just to run
`terraform plan`. Populating the actual `gridkeep-control-api-secrets` /
`gridkeep-worker-secrets` / `gridkeep-web-secrets` Kubernetes Secret objects
that the Helm charts' `envFrom` reference is a cluster-side concern: either
the External Secrets Operator reading the ARNs this module outputs, or a
one-time `kubectl create secret generic ... --from-literal=...` during
initial bootstrap. See `docs/deployment/production-deployment.md` for the
exact commands once that document exists.

## Validating without a live AWS account

This sandbox has no AWS credentials and no route to `registry.terraform.io`
/ `registry.opentofu.org` (both 403 through the environment's proxy
allowlist, confirmed via `curl "$HTTPS_PROXY/__agentproxy/status"`) --  the
same class of restriction already documented for Docker Hub and
`get.helm.sh` since Milestone 1. `terraform`/`tofu` itself isn't
apt-installable either (BSL-licensed, not in Debian/Ubuntu's repos); this
was worked around by building OpenTofu (`hashicorp/terraform`'s
Apache-licensed, drop-in-compatible fork) from source via
`go install`-equivalent (`go build` against a `git clone` of the tagged
release, since `proxy.golang.org`/`github.com` are reachable even though the
Terraform registry isn't).

Real validation was still possible, though, because
`releases.hashicorp.com` -- the direct provider-zip download host, as
opposed to the registry's discovery API -- is reachable. Every module and
the root environment were validated against the **actual AWS, random, and
tls provider plugins** (v5.60.0 / v3.6.3 / v4.0.6, downloaded directly and
served to `tofu init` via a filesystem_mirror CLI config, bypassing only the
registry's discovery step):

```
tofu fmt -recursive -check                    # clean
tofu init -backend=false                      # real provider plugins installed
tofu validate                                 # passes, against real provider schemas
tofu plan  (with dummy AWS credentials)       # gets past every local resource
                                               # (random_password, random_bytes),
                                               # fails only at the AWS STS
                                               # GetCallerIdentity call that
                                               # requires a real account
```

This caught one real bug: an `aws_security_group` description in the `eks`
module exceeded AWS's 255-character limit -- something no amount of
hand-review or `fmt`/syntax-only checking would have caught, only the real
provider schema's own validation. Fixed in `modules/eks/main.tf`.

What is **not** verified here, and cannot be without a real AWS account:
whether `terraform apply` actually succeeds end-to-end (IAM permissions,
service quotas, region capacity for the chosen instance types, MSK's
broker-count-must-divide-evenly-by-AZ-count constraint at real apply time,
etc.). `terraform.tfvars.example` documents the one value that **must**
change before a real apply (`artefacts_bucket_name` -- S3 bucket names are
globally unique across all of AWS).

`.terraform.lock.hcl` is deliberately not committed: the lock file produced
here was generated through the filesystem-mirror workaround above and only
records `linux_amd64` checksums for the local platform this sandbox runs
on, not the full cross-platform checksum set a normal `terraform init`
against the real registry produces. Committing it would misrepresent it as
authoritative. Run `terraform init` on any machine with normal registry
access to generate the real one.

## One-time backend bootstrap

Remote state (S3 + DynamoDB locking) is deliberately left commented out in
`environments/production/versions.tf` -- a backend's own storage can never
be created by the same `apply` that uses it as backend, and this sandbox
has nothing to point it at anyway. Before a real `terraform init` against
this environment, provision the state bucket and lock table by hand (or a
tiny separate one-off Terraform config) and uncomment the `backend "s3"`
block.
