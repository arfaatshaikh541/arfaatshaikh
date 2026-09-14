from app.core.security import hash_password, hash_token, verify_password


def test_password_hash_round_trip() -> None:
    password_hash = hash_password("CorrectHorseBattery9")
    assert password_hash != "CorrectHorseBattery9"
    assert verify_password(password_hash, "CorrectHorseBattery9") is True
    assert verify_password(password_hash, "wrong-password") is False


def test_token_hash_is_deterministic_and_peppered() -> None:
    assert hash_token("token", "pepper-a") == hash_token("token", "pepper-a")
    assert hash_token("token", "pepper-a") != hash_token("token", "pepper-b")


def test_auth_service_exposes_csrf_rotation() -> None:
    from app.services.auth import AuthService
    assert callable(AuthService.rotate_csrf_token)
