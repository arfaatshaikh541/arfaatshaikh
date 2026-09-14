from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]


def test_rls_migration_enables_force_rls_and_append_only_triggers() -> None:
    migration = (API_ROOT / "alembic/versions/20260725_0004_security_hardening.py").read_text()
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "prevent_event_mutation" in migration
    assert "memberships_access_policy" in migration


def test_database_context_uses_transaction_local_settings() -> None:
    context = (API_ROOT / "app/db/context.py").read_text()
    assert "set_config('app.current_user_id'" in context
    assert "set_config('app.current_organisation_id'" in context
    assert ", true)" in context
