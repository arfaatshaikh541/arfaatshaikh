from __future__ import annotations

import time

from aura_core.governance.credential_broker import CredentialBroker


def test_issued_token_is_valid_until_revoked():
    broker = CredentialBroker(default_ttl_seconds=60)
    token = broker.issue("email.send_external", scope="{}")
    assert broker.is_valid(token.token) is True

    broker.revoke(token.token)
    assert broker.is_valid(token.token) is False


def test_token_expires_after_ttl():
    broker = CredentialBroker(default_ttl_seconds=0)
    token = broker.issue("email.send_external", scope="{}", ttl_seconds=0)
    time.sleep(0.01)
    assert token.is_valid() is False
    assert broker.is_valid(token.token) is False


def test_revoke_all_invalidates_every_outstanding_token():
    broker = CredentialBroker()
    t1 = broker.issue("a", scope="{}")
    t2 = broker.issue("b", scope="{}")

    count = broker.revoke_all()

    assert count == 2
    assert broker.is_valid(t1.token) is False
    assert broker.is_valid(t2.token) is False


def test_unknown_token_is_invalid():
    broker = CredentialBroker()
    assert broker.is_valid("not-a-real-token") is False
