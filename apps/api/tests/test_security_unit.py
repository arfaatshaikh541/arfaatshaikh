"""Pure unit tests for password hashing and token helpers (no DB needed)."""

import time

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_not_plaintext_and_verifies():
    hashed = hash_password("CorrectHorseBattery9!")
    assert hashed != "CorrectHorseBattery9!"
    assert verify_password("CorrectHorseBattery9!", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_password_hash_is_salted_and_unique_per_call():
    a = hash_password("SamePassword123!")
    b = hash_password("SamePassword123!")
    assert a != b


def test_opaque_token_hash_is_deterministic_and_one_way():
    token = "some-refresh-token-value"
    h1 = hash_opaque_token(token)
    h2 = hash_opaque_token(token)
    assert h1 == h2
    assert h1 != token


def test_access_token_round_trips_claims():
    token = create_access_token(
        user_id="11111111-1111-1111-1111-111111111111",
        session_id="22222222-2222-2222-2222-222222222222",
    )
    payload = decode_access_token(token)
    assert payload["sub"] == "11111111-1111-1111-1111-111111111111"
    assert payload["sid"] == "22222222-2222-2222-2222-222222222222"
    assert payload["exp"] > time.time()
