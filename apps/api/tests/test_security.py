from core.security import (
    constant_time_equals,
    generate_opaque_token,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("Sup3r-Secret-Pass!")
    assert hashed != "Sup3r-Secret-Pass!"
    assert verify_password("Sup3r-Secret-Pass!", hashed)
    assert not verify_password("wrong-password", hashed)


def test_password_hash_is_argon2id():
    hashed = hash_password("another-password")
    assert hashed.startswith("$argon2id$")
    assert not needs_rehash(hashed)


def test_verify_password_never_raises_on_malformed_hash():
    assert verify_password("anything", "not-a-real-hash") is False


def test_token_hash_is_deterministic_and_one_way():
    token = generate_opaque_token()
    h1 = hash_token(token)
    h2 = hash_token(token)
    assert h1 == h2
    assert h1 != token
    assert len(h1) == 64  # sha256 hex digest


def test_tokens_are_unique():
    tokens = {generate_opaque_token() for _ in range(50)}
    assert len(tokens) == 50


def test_constant_time_equals():
    assert constant_time_equals("abc", "abc")
    assert not constant_time_equals("abc", "abd")
