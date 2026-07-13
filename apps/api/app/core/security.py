"""Password hashing, token issuance/verification, and field encryption.

Design notes (see docs/architecture/authentication-strategy.md):
- Passwords: Argon2id via argon2-cffi, OWASP-recommended parameters.
- Access tokens: short-lived JWT carrying only {sub, sid, exp, iat}.
- Refresh tokens / verification / reset tokens: high-entropy opaque
  strings; only their SHA-256 hash is ever persisted.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import get_settings

_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

JWT_ALGORITHM = "HS256"


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def password_needs_rehash(hashed_password: str) -> bool:
    return _password_hasher.check_needs_rehash(hashed_password)


def create_access_token(*, user_id: str, session_id: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "sid": session_id,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])


def generate_opaque_token() -> str:
    """High-entropy token for refresh/verification/reset tokens (returned to the client)."""
    return secrets.token_urlsafe(48)


def hash_opaque_token(token: str) -> str:
    """One-way hash of an opaque token, for storage. Not reversible."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _fernet() -> Fernet:
    settings = get_settings()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"leadflow-field-encryption",
        iterations=390_000,
    )
    key = kdf.derive(settings.field_encryption_key.encode("utf-8"))
    import base64

    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_field(plaintext: str) -> str:
    """Encrypt a sensitive field at rest (e.g. TOTP secret)."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_field(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
