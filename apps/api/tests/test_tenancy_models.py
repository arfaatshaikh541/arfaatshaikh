from app.db.base import Base
from app import models  # noqa: F401


def test_tenancy_tables_are_registered() -> None:
    expected = {
        "organisations", "memberships", "roles", "permissions", "role_permissions",
        "platform_administrators", "support_access_grants", "audit_events", "security_events",
    }
    assert expected.issubset(Base.metadata.tables)


def test_audit_events_have_no_updated_at_column() -> None:
    assert "updated_at" not in Base.metadata.tables["audit_events"].columns
    assert "updated_at" not in Base.metadata.tables["security_events"].columns
