"""BackendElevationService is the real security boundary Backend Mode
depends on: a valid device token is not enough on its own to elevate,
the owner's PIN must also be presented; every attempt is written to the
real hash-chained Audit Log; repeated failures trigger a real,
measurable exponential cooldown; and -- the property that matters most
for crash/restart safety -- elevation sessions live only in this
service's own process memory, so a fresh instance (standing in for a
process restart) never has any elevated sessions at all, structurally,
not because something remembered to clear them.
"""
from __future__ import annotations

import time

import pytest

from aura_core.governance.audit_log import AuditLog
from aura_core.identity import BackendElevationService, BackendRateLimitedError, EnrollmentEngine, InvalidBackendCredentialError


def make_stack(tmp_path, **elevation_kwargs):
    db_url = f"sqlite:///{tmp_path}/elevation.db"
    enrollment = EnrollmentEngine(db_url)
    audit = AuditLog(db_url)
    owner, raw_device_token = enrollment.enroll_owner("Ada")
    enrollment.set_owner_pin("482913")
    service = BackendElevationService(enrollment, audit, **elevation_kwargs)
    return service, enrollment, audit, owner, raw_device_token


def test_correct_device_token_and_pin_grants_a_real_elevation_token(tmp_path):
    service, _enrollment, _audit, _owner, device_token = make_stack(tmp_path)

    token = service.authenticate(device_token, "482913")

    session = service.verify(token)
    assert session is not None
    assert session.is_expired() is False


def test_wrong_pin_is_denied_and_never_elevates(tmp_path):
    service, _enrollment, _audit, _owner, device_token = make_stack(tmp_path)

    with pytest.raises(InvalidBackendCredentialError):
        service.authenticate(device_token, "000000")

    assert service.active_session_count() == 0


def test_wrong_device_token_is_denied_even_with_the_right_pin(tmp_path):
    service, _enrollment, _audit, _owner, _device_token = make_stack(tmp_path)

    with pytest.raises(InvalidBackendCredentialError):
        service.authenticate("not-a-real-device-token", "482913")


def test_every_attempt_is_recorded_in_the_real_audit_log_without_leaking_the_pin(tmp_path):
    service, _enrollment, audit, _owner, device_token = make_stack(tmp_path)

    with pytest.raises(InvalidBackendCredentialError):
        service.authenticate(device_token, "wrong-pin")
    service.authenticate(device_token, "482913")

    entries = audit.all_entries()
    elevation_entries = [e for e in entries if e.action_type == "security.backend_elevation_attempt"]
    assert len(elevation_entries) == 2
    assert elevation_entries[0].decision == "DENY"
    assert elevation_entries[1].decision == "ALLOW"
    for entry in elevation_entries:
        assert "482913" not in entry.result_message
        assert "wrong-pin" not in entry.result_message


def test_repeated_failures_trigger_a_real_exponential_cooldown(tmp_path):
    service, _enrollment, _audit, _owner, device_token = make_stack(
        tmp_path, failures_before_backoff=2, base_backoff_seconds=100.0, max_backoff_seconds=1000.0,
    )

    for _ in range(2):
        with pytest.raises(InvalidBackendCredentialError):
            service.authenticate(device_token, "wrong")

    # The 2nd consecutive failure crosses failures_before_backoff=2 -> locked out now.
    with pytest.raises(BackendRateLimitedError) as excinfo:
        service.authenticate(device_token, "482913")  # even the CORRECT pin is blocked during cooldown
    assert excinfo.value.retry_after_seconds > 0


def test_a_successful_authentication_clears_the_failure_count(tmp_path):
    service, _enrollment, _audit, _owner, device_token = make_stack(
        tmp_path, failures_before_backoff=3, base_backoff_seconds=100.0,
    )

    with pytest.raises(InvalidBackendCredentialError):
        service.authenticate(device_token, "wrong")
    service.authenticate(device_token, "482913")  # succeeds, should reset the counter

    with pytest.raises(InvalidBackendCredentialError):
        service.authenticate(device_token, "wrong")
    # Only 1 consecutive failure since the reset -- still below failures_before_backoff=3.
    token = service.authenticate(device_token, "482913")
    assert service.verify(token) is not None


def test_verify_rejects_an_unknown_or_expired_token(tmp_path):
    service, _enrollment, _audit, _owner, device_token = make_stack(tmp_path, session_ttl_seconds=0)

    assert service.verify("not-a-real-token") is None

    token = service.authenticate(device_token, "482913")
    time.sleep(0.01)
    assert service.verify(token) is None  # ttl=0 -> expired essentially immediately


def test_revoke_destroys_the_session_immediately(tmp_path):
    service, _enrollment, _audit, _owner, device_token = make_stack(tmp_path)
    token = service.authenticate(device_token, "482913")

    service.revoke(token)

    assert service.verify(token) is None
    assert service.active_session_count() == 0


def test_a_fresh_service_instance_has_no_sessions_simulating_a_restart(tmp_path):
    """Elevation sessions live only in process memory -- a brand-new
    BackendElevationService against the SAME database (exactly what a
    process restart looks like) must never inherit a prior session."""
    db_url = f"sqlite:///{tmp_path}/restart.db"
    enrollment = EnrollmentEngine(db_url)
    audit = AuditLog(db_url)
    _owner, device_token = enrollment.enroll_owner("Ada")
    enrollment.set_owner_pin("482913")

    first_process = BackendElevationService(enrollment, audit)
    token = first_process.authenticate(device_token, "482913")
    assert first_process.verify(token) is not None

    second_process = BackendElevationService(enrollment, audit)  # simulates a restart
    assert second_process.verify(token) is None
    assert second_process.active_session_count() == 0


def test_revoke_all_clears_every_session(tmp_path):
    service, enrollment, _audit, _owner, device_token = make_stack(tmp_path)
    enrollment.issue_device_token("second-device")
    token1 = service.authenticate(device_token, "482913")

    service.revoke_all()

    assert service.verify(token1) is None
    assert service.active_session_count() == 0
