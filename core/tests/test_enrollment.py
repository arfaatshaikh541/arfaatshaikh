from __future__ import annotations

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
