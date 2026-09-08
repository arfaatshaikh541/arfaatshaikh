from __future__ import annotations

import hashlib

import pytest

from aura_core.identity import AlreadyEnrolledError, EnrollmentEngine, NotEnrolledError


def make_engine(tmp_path) -> EnrollmentEngine:
    return EnrollmentEngine(f"sqlite:///{tmp_path}/identity.db")


def test_a_fresh_installation_is_not_enrolled(tmp_path):
    engine = make_engine(tmp_path)
    assert engine.is_enrolled() is False


def test_enrolling_creates_an_owner_and_a_working_device_token(tmp_path):
    engine = make_engine(tmp_path)

    owner, raw_token = engine.enroll_owner("Ada")

    assert engine.is_enrolled() is True
    assert owner.display_name == "Ada"
    device = engine.verify_token(raw_token)
    assert device is not None
    assert device.owner_id == owner.id


def test_a_fresh_owner_has_no_backend_pin_yet(tmp_path):
    engine = make_engine(tmp_path)
    engine.enroll_owner("Ada")

    assert engine.has_owner_pin() is False
    assert engine.verify_owner_pin("0000") is False  # never raises for "not configured"


def test_setting_and_verifying_a_backend_pin(tmp_path):
    engine = make_engine(tmp_path)
    engine.enroll_owner("Ada")

    engine.set_owner_pin("482913")

    assert engine.has_owner_pin() is True
    assert engine.verify_owner_pin("482913") is True
    assert engine.verify_owner_pin("000000") is False


def test_the_raw_pin_and_a_fast_hash_are_never_stored(tmp_path):
    engine = make_engine(tmp_path)
    engine.enroll_owner("Ada")
    engine.set_owner_pin("482913")

    with engine._Session() as session:
        from aura_core.identity.models import Owner
        owner = session.query(Owner).first()
        assert "482913" not in owner.pin_hash
        assert owner.pin_hash != hashlib.sha256(b"482913").hexdigest()  # not a bare fast hash
        assert owner.pin_iterations >= 100_000  # a real, slow KDF, not a single round


def test_setting_a_pin_twice_uses_a_fresh_salt(tmp_path):
    engine = make_engine(tmp_path)
    engine.enroll_owner("Ada")

    engine.set_owner_pin("111111")
    with engine._Session() as session:
        from aura_core.identity.models import Owner
        first_salt = session.query(Owner).first().pin_salt

    engine.set_owner_pin("111111")
    with engine._Session() as session:
        from aura_core.identity.models import Owner
        second_salt = session.query(Owner).first().pin_salt

    assert first_salt != second_salt
    assert engine.verify_owner_pin("111111") is True


def test_setting_a_pin_before_enrollment_is_honestly_rejected(tmp_path):
    engine = make_engine(tmp_path)

    with pytest.raises(NotEnrolledError):
        engine.set_owner_pin("123456")


def test_the_raw_token_is_never_stored_only_its_hash(tmp_path):
    engine = make_engine(tmp_path)
    _owner, raw_token = engine.enroll_owner("Ada")

    devices = engine.list_devices()

    assert len(devices) == 1
    assert raw_token not in devices[0].token_hash
    assert devices[0].token_hash != raw_token


def test_enrolling_twice_fails_closed_rather_than_minting_a_second_owner(tmp_path):
    engine = make_engine(tmp_path)
    engine.enroll_owner("Ada")

    with pytest.raises(AlreadyEnrolledError):
        engine.enroll_owner("Someone Else")


def test_issuing_a_device_token_before_enrollment_fails(tmp_path):
    engine = make_engine(tmp_path)

    with pytest.raises(NotEnrolledError):
        engine.issue_device_token("second-machine")


def test_a_wrong_token_does_not_verify(tmp_path):
    engine = make_engine(tmp_path)
    engine.enroll_owner("Ada")

    assert engine.verify_token("not-the-real-token") is None


def test_a_revoked_device_no_longer_verifies(tmp_path):
    engine = make_engine(tmp_path)
    _owner, raw_token = engine.enroll_owner("Ada")
    device = engine.verify_token(raw_token)

    engine.revoke_device(device.id)

    assert engine.verify_token(raw_token) is None


def test_a_second_device_can_be_trusted_and_verifies_independently(tmp_path):
    engine = make_engine(tmp_path)
    _owner, first_token = engine.enroll_owner("Ada")
    _second_device, second_token = engine.issue_device_token("laptop")

    assert engine.verify_token(first_token) is not None
    assert engine.verify_token(second_token) is not None
    assert first_token != second_token


def test_verifying_updates_last_seen_at(tmp_path):
    engine = make_engine(tmp_path)
    _owner, raw_token = engine.enroll_owner("Ada")
    fresh = engine.list_devices()[0]
    assert fresh.last_seen_at is None

    engine.verify_token(raw_token)

    seen = engine.list_devices()[0]
    assert seen.last_seen_at is not None
