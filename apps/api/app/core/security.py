"""Password hashing, opaque token generation/hashing, and CSRF helpers.

Passwords: Argon2id via argon2-cffi (PasswordHasher defaults to the
argon2id variant with vetted parameters).

Opaque tokens (session tokens, email-verification tokens, password-reset
tokens, invitation tokens): generated with `secrets.token_urlsafe`, and only
their SHA-256 hash is ever stored. The raw token exists only in the value
handed to the client (cookie or link) and in memory during the single
request that validates it - it is never persisted or logged.
"""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_password_hasher = PasswordHasher()


def hash_password(raw_password: str) -> str:
    return _password_hasher.hash(raw_password)


def verify_password(raw_password: str, hashed_password: str) -> bool:
    try:
        return _password_hasher.verify(hashed_password, raw_password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def needs_rehash(hashed_password: str) -> bool:
    return _password_hasher.check_needs_rehash(hashed_password)


def generate_opaque_token(num_bytes: int = 32) -> str:
    """Returns a URL-safe random token. Give this to the client; never
    store it - store `hash_token(token)` instead."""
    return secrets.token_urlsafe(num_bytes)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
