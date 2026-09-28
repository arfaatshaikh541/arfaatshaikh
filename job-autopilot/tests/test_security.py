import base64
import io
import json
import logging
import os

import pytest

from autopilot.logging_setup import JsonFormatter
from autopilot.security.credentials import (
    delete_credential, list_credentials, rotate_master_key, store_credential, use_credential,
)
from autopilot.security.passwords import hash_password, verify_password
from autopilot.security.redact import RedactingFilter, redact
from autopilot.security.vault import Vault, VaultError


def _key():
    return os.urandom(32)


def test_vault_roundtrip_and_context_binding():
    v = Vault(_key())
    blob = v.encrypt(b"s3cret-value", b"ctx:a")
    assert b"s3cret-value" not in blob
    assert v.decrypt(blob, b"ctx:a") == b"s3cret-value"
    with pytest.raises(VaultError):
        v.decrypt(blob, b"ctx:b")  # blob cannot be moved to another record


def test_vault_tamper_and_wrong_key():
    v = Vault(_key())
    blob = bytearray(v.encrypt(b"x" * 20, b"c"))
    blob[-1] ^= 1
    with pytest.raises(VaultError):
        v.decrypt(bytes(blob), b"c")
    with pytest.raises(VaultError):
        Vault(_key()).decrypt(v.encrypt(b"y", b"c"), b"c")


def test_vault_rotation_with_retired_key():
    old, new = _key(), _key()
    blob = Vault(old).encrypt(b"pw", b"c")
    v2 = Vault(new, retired=[old])
    assert v2.decrypt(blob, b"c") == b"pw"
    re = v2.rewrap(blob, b"c")
    assert Vault.blob_key_id(re) == v2.current_key_id
    assert Vault(new).decrypt(re, b"c") == b"pw"


def test_redaction_of_registered_secrets_and_patterns():
    v = Vault(_key())
    blob = v.encrypt_str("Hunter2!Password", "c")
    with v.use_secret(blob, "c") as secret:
        assert redact(f"typing {secret} into field") == "typing [REDACTED] into field"
    assert "Hunter2" in redact("Hunter2!Password")  # no longer registered once out of scope
    assert "abc123" not in redact('{"password": "abc123", "user": "u"}')
    assert "tok" not in redact("Authorization: Bearer tokabcdefghijkl")
    assert "sessionvalue" not in redact("cookie=sessionvalue; other")


def test_log_records_never_contain_secret():
    v = Vault(_key())
    blob = v.encrypt_str("PlainTextPw#1", "c")
    stream = io.StringIO()
    h = logging.StreamHandler(stream)
    h.setFormatter(JsonFormatter())
    h.addFilter(RedactingFilter())
    log = logging.getLogger("t-redact")
    log.addHandler(h)
    log.setLevel(logging.INFO)
    with v.use_secret(blob, "c") as secret:
        log.info("login with %s", secret, extra={"error": f"failed {secret}"})
        try:
            raise RuntimeError(f"boom {secret}")
        except RuntimeError:
            log.exception("err")
    out = stream.getvalue()
    assert "PlainTextPw#1" not in out
    assert "[REDACTED]" in out
    json.loads(out.splitlines()[0])


def test_credentials_store_is_write_only(s, user):
    view = store_credential(s, user_id=user.id, platform_key="generic_portal", username="me@example.invalid",
                            secret="MyRealPassword123")
    s.commit()
    assert not hasattr(view, "secret") and "MyRealPassword123" not in repr(view)
    from autopilot.models import Credential

    row = s.get(Credential, view.id)
    assert b"MyRealPassword123" not in row.blob
    with use_credential(s, user.id, "generic_portal") as (u, pw):
        assert (u, pw) == ("me@example.invalid", "MyRealPassword123")
    assert [c.platform_key for c in list_credentials(s, user.id)] == ["generic_portal"]
    assert delete_credential(s, user.id, view.id)


def test_master_key_rotation_rewraps_credentials(s, user):
    old = Vault.from_config()
    store_credential(s, user_id=user.id, platform_key="p", username="u", secret="pw-rotate-me", vault=old)
    s.commit()
    new_raw = os.urandom(32)
    old_raw = base64.urlsafe_b64decode(os.environ["JOBAP_MASTER_KEY"])
    newv = Vault(new_raw, retired=[old_raw])
    assert rotate_master_key(s, newv) == 1
    s.commit()
    with use_credential(s, user.id, "p", vault=Vault(new_raw)) as (_, pw):
        assert pw == "pw-rotate-me"


def test_admin_password_hashing():
    h = hash_password("a long admin password")
    assert verify_password("a long admin password", h)
    assert not verify_password("wrong", h)
    with pytest.raises(ValueError):
        hash_password("short")
