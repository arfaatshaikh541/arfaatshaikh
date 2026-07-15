from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(plain: str) -> str:
    return _password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _password_hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        # Malformed/legacy hash — treat as verification failure, never raise
        # into an auth code path (would risk an information-leaking 500).
        return False


def needs_rehash(hashed: str) -> bool:
    return _password_hasher.check_needs_rehash(hashed)


def generate_opaque_token(num_bytes: int = 32) -> str:
    """URL-safe random token used for session ids, invitation tokens,
    password-reset tokens, email-verification tokens."""
    return secrets.token_urlsafe(num_bytes)


def hash_token(token: str) -> str:
    """Tokens (session ids, reset tokens) are stored hashed at rest so a DB
    read alone never yields a usable credential."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)
