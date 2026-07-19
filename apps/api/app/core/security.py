"""Password hashing, opaque token generation/hashing, credential
encryption, and CSRF helpers.

Passwords: Argon2id via argon2-cffi (PasswordHasher defaults to the
argon2id variant with vetted parameters).

Opaque tokens (session tokens, email-verification tokens, password-reset
tokens, invitation tokens): generated with `secrets.token_urlsafe`, and only
their SHA-256 hash is ever stored. The raw token exists only in the value
handed to the client (cookie or link) and in memory during the single
request that validates it - it is never persisted or logged.

Credential encryption (`encrypt_credential`/`decrypt_credential`):
Milestone 1 reserved `Settings.credential_encryption_master_key` for
"a future feature needing to store a third-party credential" - Milestone
8's integration webhook secrets are that feature. Unlike a password
(verify-only, so a one-way hash is correct) or a token (also verify-only,
same reasoning) a webhook secret must be *recovered* in full to sign an
outgoing delivery, so it needs real, reversible encryption, not a hash.
Fernet (from `cryptography`, already a dependency) is symmetric
AES-128-CBC + HMAC-SHA256 authenticated encryption - simple, well-vetted,
and exactly the right shape for "one master key, many small encrypted
values," without pulling in a full secrets-manager integration this
project doesn't otherwise need. The master key setting is an arbitrary
string (so it fits naturally in `.env`, unlike a raw 32-byte Fernet key);
it is stretched into a real 32-byte key via SHA-256, matching Fernet's
own key-length requirement without asking the operator to generate and
manage a base64 key directly.
"""

import base64
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

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


def _fernet() -> Fernet:
    settings = get_settings()
    if not settings.credential_encryption_master_key:
        raise RuntimeError(
            "CREDENTIAL_ENCRYPTION_MASTER_KEY is not set - required to store or read any "
            "encrypted credential (e.g. an integration webhook secret)."
        )
    key_bytes = hashlib.sha256(settings.credential_encryption_master_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt_credential(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_credential(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Could not decrypt credential - wrong key or corrupted value.") from exc


def sign_payload(secret: str, payload_bytes: bytes) -> str:
    """HMAC-SHA256 over the exact bytes sent on the wire - the same
    "sign what you send" scheme Stripe/GitHub webhooks use, so a receiver
    can verify `X-Gridkeep-Signature` against its own copy of `secret`
    without needing to re-derive the JSON encoding (whitespace/key-order
    differences would otherwise break verification)."""
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
