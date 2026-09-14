from app.db.base import Base
from app.models import (
    EmailOutbox,
    EmailVerificationToken,
    PasswordResetToken,
    PlatformMetadata,
    Session,
    User,
)


def test_platform_metadata_is_registered() -> None:
    assert PlatformMetadata.__tablename__ == "platform_metadata"
    assert "platform_metadata" in Base.metadata.tables
    table = Base.metadata.tables["platform_metadata"]
    assert set(table.columns.keys()) == {
        "id",
        "key",
        "value",
        "description",
        "created_at",
        "updated_at",
    }


def test_identity_tables_are_registered() -> None:
    expected = {
        User.__tablename__,
        Session.__tablename__,
        EmailVerificationToken.__tablename__,
        PasswordResetToken.__tablename__,
        EmailOutbox.__tablename__,
    }
    assert expected.issubset(Base.metadata.tables)
