# Secrets module: generates the three required-no-fallback encryption keys
# (cmd/server/main.go's loadMFAKey/loadPKICAKey/loadSecretsVaultKey each
# refuse to start without one) and stores every credential control-api,
# worker and web need as JSON blobs in AWS Secrets Manager -- one secret per
# service, matching the three existingSecret values already referenced by
# infrastructure/helm/gridkeep's values.yaml files
# (gridkeep-control-api-secrets, gridkeep-worker-secrets,
# gridkeep-web-secrets).
#
# Terraform's job stops at Secrets Manager. Getting these JSON blobs into
# the actual Kubernetes Secret objects those Helm charts' envFrom references
# is a separate, cluster-side concern (e.g. the External Secrets Operator
# reading these ARNs, or a one-time `kubectl create secret` during initial
# bootstrap) -- see docs/deployment/production-deployment.md for the wiring
# once that document exists. Keeping that step outside Terraform avoids ever
# needing a Kubernetes provider (and therefore a live cluster) just to plan
# this stack.

resource "random_bytes" "mfa_encryption_key" {
  length = 32
}

resource "random_bytes" "pki_ca_encryption_key" {
  length = 32
}

resource "random_bytes" "secrets_vault_encryption_key" {
  length = 32
}

resource "aws_secretsmanager_secret" "control_api" {
  name                    = "${var.name_prefix}/control-api"
  recovery_window_in_days = var.recovery_window_in_days
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "control_api" {
  secret_id = aws_secretsmanager_secret.control_api.id
  secret_string = jsonencode({
    DATABASE_URL                 = var.database_url
    REDIS_URL                    = var.redis_url
    MFA_ENCRYPTION_KEY           = random_bytes.mfa_encryption_key.base64
    PKI_CA_ENCRYPTION_KEY        = random_bytes.pki_ca_encryption_key.base64
    SECRETS_VAULT_ENCRYPTION_KEY = random_bytes.secrets_vault_encryption_key.base64
    S3_ENDPOINT                  = var.s3_endpoint
    S3_REGION                    = var.s3_region
    S3_BUCKET_ARTEFACTS          = var.s3_bucket
    S3_ACCESS_KEY                = var.s3_access_key
    S3_SECRET_KEY                = var.s3_secret_key
    S3_USE_SSL                   = "true"
  })
}

resource "aws_secretsmanager_secret" "worker" {
  name                    = "${var.name_prefix}/worker"
  recovery_window_in_days = var.recovery_window_in_days
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "worker" {
  secret_id = aws_secretsmanager_secret.worker.id
  secret_string = jsonencode({
    KAFKA_BROKERS = var.kafka_brokers
  })
}

# web has no server-side secret today -- every browser-facing value it
# needs (NEXT_PUBLIC_CONTROL_API_URL etc.) is baked into the client bundle
# at build time, not read from the environment at runtime (see
# apps/web/Dockerfile's build ARG and charts/web/values.yaml's own
# comment). This secret exists only so the Helm chart's existingSecret
# reference always resolves to something, ready for a genuine runtime
# value the moment one is needed.
resource "aws_secretsmanager_secret" "web" {
  name                    = "${var.name_prefix}/web"
  recovery_window_in_days = var.recovery_window_in_days
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "web" {
  secret_id = aws_secretsmanager_secret.web.id
  secret_string = jsonencode({
    NODE_ENV = "production"
  })
}
