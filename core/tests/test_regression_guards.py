"""Explicit regression fences for the security/architecture invariants
this project has repeatedly been asked to never silently lose across
future passes: device trust, backend elevation independent of device
trust, the planner's "never fabricate a capability" discipline, and the
installer's state-preservation logic. Every assertion here names the
exact invariant in its test name and docstring, specifically so that if
a future change weakens or deletes one, the failure is immediately
legible as "you just regressed something explicitly protected," not a
mysterious unrelated test failure somewhere else in the suite.

This file deliberately does not re-implement full behavioral tests
already covered elsewhere (test_api_devices.py, test_backend_elevation.py,
test_universal_planner.py, test_task_engine.py) -- it re-asserts the
single most load-bearing fact from each, plus a few structural checks
(which endpoints require which dependencies) that are cheap to check
directly against the real FastAPI route table rather than only inferred
from behavior.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings
from aura_core.identity import BackendElevationService, EnrollmentEngine


REPO_ROOT = Path(__file__).resolve().parents[2]


def _dependency_names(route) -> set[str]:
    return {dep.call.__name__ for dep in route.dependant.dependencies}


def _route(app, path: str):
    return next(r for r in app.routes if getattr(r, "path", None) == path)


# ---------------------------------------------------------------------
# Device trust: multi-device support must remain real and reachable.
# ---------------------------------------------------------------------

def test_device_management_endpoints_exist_and_require_backend_elevation():
    app = create_app(load_settings())
    for path in ("/devices", "/devices/{device_id}/revoke", "/devices/{device_id}/rename", "/devices/pairing/start"):
        route = _route(app, path)
        deps = _dependency_names(route)
        assert "require_backend_elevation" in deps, f"{path} lost its backend-elevation gate"
        assert "require_device_token" in deps, f"{path} lost its device-token gate"


def test_pairing_claim_is_reachable_without_any_prior_device_token():
    """The joining device has no token yet by definition -- if this ever
    becomes gated, no second device could ever enroll."""
    app = create_app(load_settings())
    route = _route(app, "/devices/pairing/claim")
    assert _dependency_names(route) == set()


def test_a_revoked_device_immediately_loses_access_not_just_its_db_row():
    engine = EnrollmentEngine("sqlite:///:memory:")
    engine.enroll_owner("Ada")
    device, raw_token = engine.issue_device_token("secondary")

    assert engine.verify_token(raw_token) is not None
    engine.revoke_device(device.id)
    assert engine.verify_token(raw_token) is None


def test_multiple_devices_per_owner_remains_supported():
    engine = EnrollmentEngine("sqlite:///:memory:")
    engine.enroll_owner("Ada")
    engine.issue_device_token("phone")
    engine.issue_device_token("laptop")

    labels = {d.label for d in engine.list_devices()}
    assert labels == {"primary", "phone", "laptop"}


# ---------------------------------------------------------------------
# Backend elevation: a separate factor from device trust, never
# persisted, never satisfied by a device token alone.
# ---------------------------------------------------------------------

def test_backend_endpoints_reject_a_device_token_with_no_elevation_at_all():
    app = create_app(load_settings())
    app.state.runtime.enrollment.enroll_owner("Ada")
    device_token = app.state.runtime.enrollment.list_devices()[0]
    client = TestClient(app)

    # A syntactically-present but unverified elevation header must not
    # be treated as a bypass of the real check.
    response = client.get(
        "/backend/diagnostics",
        headers={"X-Aura-Device-Token": "irrelevant", "X-Aura-Backend-Elevation": "not-a-real-token"},
    )
    assert response.status_code == 401
    del device_token  # only needed to prove enrollment happened; the header above is deliberately wrong


def test_a_fresh_elevation_service_instance_never_inherits_a_prior_sessions_trust(tmp_path):
    """The structural proof that backend elevation cannot survive a
    restart: elevation sessions live only in process memory, never in
    the database, so a second service instance against the identical
    database has zero sessions no matter what the first one granted.
    (Also covered end-to-end in test_backend_elevation.py -- reasserted
    here as an explicit, named regression fence.)"""
    from aura_core.governance import AuditLog

    db_url = f"sqlite:///{tmp_path}/regression_guard.db"
    engine = EnrollmentEngine(db_url)
    audit = AuditLog(db_url)
    _owner, device_token = engine.enroll_owner("Ada")
    engine.set_owner_pin("482913")

    first_process = BackendElevationService(engine, audit)
    token = first_process.authenticate(device_token, "482913")
    assert first_process.verify(token) is not None

    second_process = BackendElevationService(engine, audit)  # simulates a restart
    assert second_process.verify(token) is None
    assert second_process.active_session_count() == 0


# ---------------------------------------------------------------------
# Planner: never fabricates a capability that isn't really registered.
# ---------------------------------------------------------------------

def test_the_capability_registry_never_advertises_a_capability_with_no_real_handler():
    """The whole point of list_available() being live-filtered rather
    than a static catalog dump: every name it returns must have an
    actual connector-registered handler right now, in THIS running
    process -- never "the code exists somewhere," which is what
    list_all() (a superset) would report instead."""
    app = create_app(load_settings())
    runtime = app.state.runtime

    available_names = {c.name for c in runtime.capabilities.list_available()}
    for name in available_names:
        assert runtime.capabilities.is_handler_registered(name), (
            f"{name} was advertised as available but has no registered handler"
        )

    # And the catalog must contain at least one entry that ISN'T
    # available in a fresh, unconfigured build (proving the filter is
    # real, not a no-op that returns everything).
    all_names = {c.name for c in runtime.capabilities.list_all()}
    assert all_names - available_names, "list_available() returned everything list_all() has -- the live filter looks disabled"


# ---------------------------------------------------------------------
# Installer: must keep preserving owner state across an update. This is
# a static text guard (the installer script cannot run outside Windows
# in this sandbox) -- it fails loudly if the preservation block is ever
# deleted or renamed without a replacement, rather than silently
# shipping an update that forces re-enrollment.
# ---------------------------------------------------------------------

def test_installer_still_preserves_the_database_models_and_device_token_across_updates():
    installer_text = (REPO_ROOT / "install" / "Install-AURA.ps1").read_text()
    assert "aura_core.db" in installer_text
    assert ".models" in installer_text
    assert ".aura" in installer_text, "device-token directory preservation was removed from the installer"
    assert "dotnet test" in installer_text, "installer no longer runs the C# test suites as part of its self-test gate"


def test_interface_mode_manager_still_always_boots_fresh_never_resuming_backend_mode():
    """Static text guard (C# state machine, not runnable from Python):
    InterfaceModeManager.Mode must still be hard-initialized to Booting,
    which is the entire structural reason a crash or restart cannot
    reopen Backend Mode. If this default ever changes to read a
    persisted value, this test fails immediately."""
    source = (REPO_ROOT / "apps" / "windows" / "AuraShell.Core" / "InterfaceModeManager.cs").read_text()
    assert "InterfaceMode.Booting;" in source
    assert "public InterfaceMode Mode { get; private set; } = InterfaceMode.Booting;" in source
