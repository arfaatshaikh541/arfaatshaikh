import pytest
from pydantic import ValidationError

from app.schemas.auth import RegisterRequest


def test_registration_normalizes_display_name() -> None:
    payload = RegisterRequest(email="User@Example.com", password="LongSecurePassword7", display_name="  Amina   Noor ")
    assert payload.display_name == "Amina Noor"


def test_registration_rejects_weak_password() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="user@example.com", password="alllowercasepassword", display_name="Amina")
