"""Tests that connectors are actually reachable through the real Runtime,
API, and CLI -- not just importable, tested classes that nothing ever
wires up. build_runtime() is the single place production code assembles
the system, so if a connector doesn't show up here, it doesn't exist for
any real caller."""
from __future__ import annotations

from fastapi.testclient import TestClient

from aura_core.api.app import create_app
from aura_core.runtime import build_runtime
from aura_core.status import CapabilityStatus, registry as status_registry


def test_build_runtime_registers_the_credential_free_connectors():
    runtime = build_runtime()
    names = {m.name for m in runtime.connectors.manifests()}
    # filesystem/http/desktop_control/telephony(mock) never need external
    # credentials, so they must always be registered with no configuration.
    assert {"filesystem", "http", "desktop_control", "telephony"}.issubset(names)


def test_filesystem_connector_is_live_through_the_real_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_FS_SANDBOX_DIR", str(tmp_path / "sandbox"))
    runtime = build_runtime()
    snapshot = status_registry.snapshot()
    assert snapshot["connector.filesystem"]["status"] == CapabilityStatus.LIVE.value


def test_telephony_mock_provider_is_live_through_the_real_runtime():
    runtime = build_runtime()
    snapshot = status_registry.snapshot()
    assert snapshot["connector.telephony"]["status"] == CapabilityStatus.LIVE.value


def test_email_connector_is_not_registered_without_smtp_configuration(monkeypatch):
    monkeypatch.delenv("AURA_SMTP_HOST", raising=False)
    runtime = build_runtime()
    names = {m.name for m in runtime.connectors.manifests()}
    assert "email" not in names
    snapshot = status_registry.snapshot()
    assert snapshot["connector.email"]["status"] == CapabilityStatus.NOT_CONNECTED.value


def test_email_connector_registers_once_smtp_host_is_configured(monkeypatch):
    monkeypatch.setenv("AURA_SMTP_HOST", "127.0.0.1")
    runtime = build_runtime()
    names = {m.name for m in runtime.connectors.manifests()}
    assert "email" in names


def test_connectors_endpoint_reports_real_manifests_and_status():
    with TestClient(create_app()) as client:
        response = client.get("/connectors")
        assert response.status_code == 200
        body = response.json()
        names = {c["name"] for c in body}
        assert {"filesystem", "http", "desktop_control", "telephony"}.issubset(names)
        filesystem = next(c for c in body if c["name"] == "filesystem")
        assert filesystem["status"]["status"] == CapabilityStatus.LIVE.value
        assert "filesystem.write_file" in filesystem["capabilities"]
