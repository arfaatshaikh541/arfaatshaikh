import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()

# Argon2id with parameters tuned for an interactive login path (~100-200ms
# on typical container CPU). time_cost/memory_cost can be raised as
# hardware allows without invalidating existing hashes — argon2-cffi
# stores parameters in the hash string itself.
_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        _password_hasher.verify(password_hash, plain_password)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _password_hasher.check_needs_rehash(password_hash)


def generate_opaque_token(num_bytes: int = 32) -> str:
    """A URL-safe, high-entropy token for sessions/invitations/verification/reset links.

    The raw value is only ever sent to the client (cookie, email link); the
    database stores only its SHA-256 hash so a leaked database dump does
    not yield usable tokens.
    """
    return secrets.token_urlsafe(num_bytes)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
