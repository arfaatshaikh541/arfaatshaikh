"""Admin password hashing (scrypt, stdlib)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

_N, _R, _P = 2**15, 8, 1


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Admin password must be at least 12 characters")
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, maxmem=64 * 1024 * 1024, dklen=32)
    return "scrypt${}${}${}${}${}".format(
        _N, _R, _P, base64.b64encode(salt).decode(), base64.b64encode(dk).decode()
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, dk_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode(),
            salt=base64.b64decode(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            maxmem=64 * 1024 * 1024,
            dklen=32,
        )
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except Exception:
        return False
