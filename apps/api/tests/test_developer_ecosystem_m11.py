import app.models  # noqa: F401
from app.db.base import Base
from app.services.developer_ecosystem import evaluate_api_version, evaluate_sdk_release, evaluate_sandbox_session, validate_documentation_artifact


def test_developer_ecosystem_tables_registered():
    assert {"api_products", "api_versions", "api_documentation_artifacts", "sdk_releases", "developer_sandbox_sessions"}.issubset(Base.metadata.tables)


def test_current_api_version_accepts_verified_nonbreaking_contract():
    result = evaluate_api_version(version="v2", lifecycle_status="current", specification_sha256="a"*64, breaking_changes=[], sunset_notice_days=0, successor_version=None)
    assert result["valid"] is True


def test_deprecated_api_requires_successor_and_notice():
    result = evaluate_api_version(version="v1", lifecycle_status="deprecated", specification_sha256="a"*64, breaking_changes=[], sunset_notice_days=30, successor_version=None)
    assert result["valid"] is False
    assert "minimum_sunset_notice_required" in result["reason_codes"]
    assert "successor_version_required" in result["reason_codes"]


def test_current_version_cannot_smuggle_breaking_change():
    result = evaluate_api_version(version="v1", lifecycle_status="current", specification_sha256="a"*64, breaking_changes=["renamed field"], sunset_notice_days=0, successor_version=None)
    assert result["valid"] is False


def test_documentation_requires_https_hash_and_verification():
    good = validate_documentation_artifact(artifact_type="openapi", locale="en", content_uri="https://docs.example.com/openapi.json", content_sha256="b"*64, verified=True)
    bad = validate_documentation_artifact(artifact_type="guide", locale="xx_YY", content_uri="http://localhost/guide", content_sha256="bad", verified=False)
    assert good["valid"] is True
    assert bad["valid"] is False


def test_sdk_release_requires_tests_provenance_and_live_api_version():
    good = evaluate_sdk_release(language="python", version="1.2.0", package_uri="https://packages.example.com/sdk.whl", package_sha256="c"*64, tests_passed=True, provenance_verified=True, api_version_status="current")
    bad = evaluate_sdk_release(language="python", version="1", package_uri="https://packages.example.com/sdk.whl", package_sha256="c"*64, tests_passed=False, provenance_verified=False, api_version_status="retired")
    assert good["publishable"] is True
    assert bad["publishable"] is False


def test_sandbox_blocks_assistant_scope_and_unknown_scope():
    result = evaluate_sandbox_session(application_status="active", requested_scopes={"assistant.request", "unknown"}, request_limit=100, used_requests=0, expired=False)
    assert result["allowed"] is False
    assert "assistant_scope_not_available_in_sandbox" in result["reason_codes"]


def test_sandbox_allows_bounded_read_only_session():
    result = evaluate_sandbox_session(application_status="draft", requested_scopes={"quran.read", "hadith.read"}, request_limit=100, used_requests=10, expired=False)
    assert result["allowed"] is True
    assert result["remaining"] == 90
