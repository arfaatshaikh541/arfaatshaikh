"""Short-lived signed tokens that let the web gateway attach an authenticated user to a
worker's held browser session. Nothing is stored: the token is an HMAC (key derived from
the master key, which both web and workers hold) over verification id, user id and expiry."""
from __future__ import annotations

import hashlib
import hmac
import time

from ..security.vault import Vault, get_vault

_LABEL = "remote-browser-session-v1"


def mint(vid: int, user_id: int, ttl_s: int = 120, vault: Vault | None = None) -> str:
    exp = int(time.time()) + ttl_s
    key = (vault or get_vault()).derive_key(_LABEL)
    mac = hmac.new(key, f"{vid}.{user_id}.{exp}".encode(), hashlib.sha256).hexdigest()
    return f"{vid}.{user_id}.{exp}.{mac}"


def verify(token: str, vid: int, vault: Vault | None = None) -> int | None:
    """Returns the user id if valid for this verification id and not expired."""
    try:
        t_vid, uid, exp, mac = token.split(".")
        if int(t_vid) != vid or int(exp) < time.time():
            return None
        key = (vault or get_vault()).derive_key(_LABEL)
        good = hmac.new(key, f"{t_vid}.{uid}.{exp}".encode(), hashlib.sha256).hexdigest()
        return int(uid) if hmac.compare_digest(good, mac) else None
    except (ValueError, AttributeError):
        return None
