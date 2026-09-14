from app.db.base import Base
import app.models  # noqa: F401
from app.services.deployment import DeploymentConfig, evaluate_release_readiness, validate_deployment_config


def test_deployment_tables_are_registered():
    expected = {"deployment_environments", "deployment_releases", "deployment_verifications", "backup_restore_rehearsals"}
    assert expected.issubset(Base.metadata.tables)


def test_production_config_requires_https_secure_cookie_digest_and_managed_secrets():
    result = validate_deployment_config(DeploymentConfig(
        environment="production", public_base_url="http://example.com", allowed_origins=("http://example.com",),
        cookie_secure=False, secret_key_length=16, image_digest="latest", migration_revision="0038", secrets_provider="env_file",
    ))
    assert result["valid"] is False
    assert {"https_required", "secure_cookies_required", "secret_key_too_short", "immutable_image_digest_required", "managed_secrets_provider_required", "insecure_allowed_origin"}.issubset(result["reason_codes"])


def test_valid_production_config_passes():
    result = validate_deployment_config(DeploymentConfig(
        environment="production", public_base_url="https://islam.example", allowed_origins=("https://islam.example",),
        cookie_secure=True, secret_key_length=64, image_digest="sha256:" + "a" * 64, migration_revision="20260725_0038", secrets_provider="aws-secrets-manager",
    ))
    assert result["valid"] is True


def test_production_release_fails_closed_without_all_checks():
    result = evaluate_release_readiness(environment="production", verification_statuses={"config": "passed", "migration": "passed"}, backup_rehearsal_passed=False, ai_release_gate_passed=False)
    assert result["release_allowed"] is False
    assert "backup_restore_rehearsal_required" in result["reason_codes"]
    assert "ai_release_gate_failed" in result["reason_codes"]


def test_production_release_passes_with_all_evidence():
    checks = {name: "passed" for name in {"config", "secrets", "migration", "health", "readiness", "backup", "rollback"}}
    result = evaluate_release_readiness(environment="production", verification_statuses=checks, backup_rehearsal_passed=True, ai_release_gate_passed=True)
    assert result["release_allowed"] is True
