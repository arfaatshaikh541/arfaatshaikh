from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlparse

DEPLOYMENT_POLICY_VERSION = "deployment-v1"
REQUIRED_PRODUCTION_CHECKS = {"config", "secrets", "migration", "health", "readiness", "backup", "rollback"}

@dataclass(frozen=True)
class DeploymentConfig:
    environment: str
    public_base_url: str
    allowed_origins: tuple[str, ...]
    cookie_secure: bool
    secret_key_length: int
    image_digest: str
    migration_revision: str
    secrets_provider: str


def validate_deployment_config(config: DeploymentConfig) -> dict[str, object]:
    if config.environment not in {"development", "test", "staging", "production"}:
        raise ValueError("unsupported deployment environment")
    reasons: list[str] = []
    parsed = urlparse(config.public_base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        reasons.append("invalid_public_base_url")
    if config.environment in {"staging", "production"} and parsed.scheme != "https":
        reasons.append("https_required")
    if config.environment == "production" and not config.cookie_secure:
        reasons.append("secure_cookies_required")
    if config.secret_key_length < 32:
        reasons.append("secret_key_too_short")
    if config.environment == "production" and not config.image_digest.startswith("sha256:"):
        reasons.append("immutable_image_digest_required")
    if not config.migration_revision.strip():
        reasons.append("migration_revision_required")
    if config.environment == "production" and config.secrets_provider in {"env_file", "plaintext", "local"}:
        reasons.append("managed_secrets_provider_required")
    for origin in config.allowed_origins:
        origin_url = urlparse(origin)
        if origin_url.scheme not in {"http", "https"} or not origin_url.netloc:
            reasons.append("invalid_allowed_origin")
            break
        if config.environment == "production" and origin_url.scheme != "https":
            reasons.append("insecure_allowed_origin")
            break
    return {"valid": not reasons, "reason_codes": reasons or ["deployment_config_valid"], "policy_version": DEPLOYMENT_POLICY_VERSION}


def evaluate_release_readiness(*, environment: str, verification_statuses: dict[str, str], backup_rehearsal_passed: bool, ai_release_gate_passed: bool) -> dict[str, object]:
    if environment not in {"development", "test", "staging", "production"}:
        raise ValueError("unsupported deployment environment")
    reasons: list[str] = []
    required = REQUIRED_PRODUCTION_CHECKS if environment == "production" else {"config", "migration", "health", "readiness"}
    missing = sorted(required - set(verification_statuses))
    if missing:
        reasons.append("missing_checks:" + ",".join(missing))
    failed = sorted(name for name in required if verification_statuses.get(name) != "passed")
    if failed:
        reasons.append("failed_checks:" + ",".join(failed))
    if environment == "production" and not backup_rehearsal_passed:
        reasons.append("backup_restore_rehearsal_required")
    if not ai_release_gate_passed:
        reasons.append("ai_release_gate_failed")
    return {"release_allowed": not reasons, "reason_codes": reasons or ["deployment_release_ready"], "policy_version": DEPLOYMENT_POLICY_VERSION}
