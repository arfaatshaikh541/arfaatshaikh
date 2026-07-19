"""Milestone 29 — production-configuration fail-closed tests (finding H-02).

Each test constructs a real `core.config.Settings` instance directly
(never the process-wide `settings` singleton, which is already locked to
`environment=test` for this whole suite — see conftest.py) and asserts
either that construction succeeds, or that it raises with a message naming
the specific problem. `_env_file=None` and an explicit, exhaustive kwargs
dict keep each test deterministic regardless of the ambient environment
variables the rest of the test suite already relies on (conftest.py sets
several via `os.environ.setdefault`)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.config import (
    _DEV_APP_DB_CREDENTIAL_MARKER,
    _DEV_DB_CREDENTIAL_MARKER,
    _DEV_OBJECT_STORAGE_ACCESS_KEY,
    _DEV_OBJECT_STORAGE_SECRET_KEY,
    _DEV_VAULT_MASTER_KEY,
    Settings,
)


def _production_safe_kwargs() -> dict:
    """Every field the fail-closed validator inspects, set to a value that
    should pass — the baseline every individual test below mutates exactly
    one field away from."""
    return dict(
        environment="production",
        database_url="postgresql+asyncpg://realuser:realpass@prod-db-host:5432/gridkeep",
        database_migration_url="postgresql+psycopg://realuser:realpass@prod-db-host:5432/gridkeep",
        redis_url="redis://prod-redis-host:6379/0",
        vault_local_master_key="a-real-securely-generated-key-not-the-shipped-default",
        cors_allow_origins=["https://app.example.com"],
        object_storage_access_key="a-real-access-key",
        object_storage_secret_key="a-real-secret-key",
        allow_insecure_cookies_for_local_dev=False,
    )


def test_production_settings_construct_cleanly_when_fully_configured():
    settings = Settings(_env_file=None, **_production_safe_kwargs())
    assert settings.is_production is True


def test_non_production_settings_ignore_every_dev_default():
    """The validator only ever fires for `environment=production` — a
    `development` (or `test`) Settings object must construct cleanly even
    when every dev-default-shaped value is explicitly present, since those
    defaults exist precisely for this case. Explicitly passing every field
    (rather than relying on the class default) keeps this test correct
    regardless of what the ambient process environment happens to already
    have set — pydantic-settings reads env vars before falling back to a
    field's class default, so an un-passed field is not a reliable way to
    observe "the shipped default" in a process that also has real
    environment variables set (e.g. this whole test suite's own
    VAULT_LOCAL_MASTER_KEY)."""
    kwargs = _production_safe_kwargs()
    kwargs["environment"] = "development"
    kwargs["vault_local_master_key"] = _DEV_VAULT_MASTER_KEY
    kwargs["allow_insecure_cookies_for_local_dev"] = True
    settings = Settings(_env_file=None, **kwargs)
    assert settings.is_production is False
    assert settings.vault_local_master_key == _DEV_VAULT_MASTER_KEY
    assert settings.allow_insecure_cookies_for_local_dev is True


@pytest.mark.parametrize(
    "field, bad_value, expected_message_fragment",
    [
        ("vault_local_master_key", _DEV_VAULT_MASTER_KEY, "VAULT_LOCAL_MASTER_KEY"),
        ("object_storage_access_key", _DEV_OBJECT_STORAGE_ACCESS_KEY, "OBJECT_STORAGE_ACCESS_KEY"),
        ("object_storage_secret_key", _DEV_OBJECT_STORAGE_SECRET_KEY, "OBJECT_STORAGE_SECRET_KEY"),
        ("cors_allow_origins", ["http://localhost:3000"], "CORS_ALLOW_ORIGINS"),
        ("redis_url", "redis://localhost:6379/0", "REDIS_URL"),
        ("allow_insecure_cookies_for_local_dev", True, "ALLOW_INSECURE_COOKIES_FOR_LOCAL_DEV"),
    ],
)
def test_app_refuses_to_start_in_production_with_a_dev_default(
    field: str, bad_value, expected_message_fragment: str
):
    kwargs = _production_safe_kwargs()
    kwargs[field] = bad_value
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, **kwargs)
    assert expected_message_fragment in str(exc_info.value)


@pytest.mark.parametrize(
    "field, expected_message_fragment",
    [
        # Milestone 31 (finding C-01): DATABASE_URL and DATABASE_MIGRATION_URL
        # get distinct messages now — the former names the specific mistake
        # (the app's own connection must be the least-privilege gridkeep_app
        # role, never the superuser), not just the shared credential marker.
        ("database_url", "the gridkeep superuser"),
        ("database_migration_url", "gridkeep:gridkeep"),
    ],
)
def test_app_refuses_to_start_in_production_with_default_db_credential(
    field: str, expected_message_fragment: str
):
    kwargs = _production_safe_kwargs()
    kwargs[field] = f"postgresql+asyncpg://{_DEV_DB_CREDENTIAL_MARKER}prod-db-host:5432/gridkeep"
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, **kwargs)
    assert expected_message_fragment in str(exc_info.value)


def test_app_refuses_to_start_in_production_with_default_app_db_password():
    """Milestone 31 (finding C-01): a real deployment could correctly swap
    the role name to gridkeep_app but forget to also change the shipped
    development password — this must be refused independently of the
    gridkeep-superuser check above, which wouldn't fire for this value."""
    kwargs = _production_safe_kwargs()
    kwargs["database_url"] = (
        f"postgresql+asyncpg://{_DEV_APP_DB_CREDENTIAL_MARKER}prod-db-host:5432/gridkeep"
    )
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, **kwargs)
    assert "GRIDKEEP_APP_DB_PASSWORD" in str(exc_info.value)


def test_app_refuses_to_start_in_production_with_127_0_0_1_cors_origin():
    kwargs = _production_safe_kwargs()
    kwargs["cors_allow_origins"] = ["http://127.0.0.1:3000"]
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, **kwargs)
    assert "CORS_ALLOW_ORIGINS" in str(exc_info.value)


def test_validation_error_lists_every_problem_at_once_not_just_the_first():
    """A real deployment likely mis-sets more than one field on a first
    attempt — the error should tell them everything wrong in one pass, not
    make them fix-and-retry one field at a time."""
    kwargs = _production_safe_kwargs()
    kwargs["vault_local_master_key"] = _DEV_VAULT_MASTER_KEY
    kwargs["redis_url"] = "redis://localhost:6379/0"
    kwargs["allow_insecure_cookies_for_local_dev"] = True
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, **kwargs)
    message = str(exc_info.value)
    assert "VAULT_LOCAL_MASTER_KEY" in message
    assert "REDIS_URL" in message
    assert "ALLOW_INSECURE_COOKIES_FOR_LOCAL_DEV" in message
