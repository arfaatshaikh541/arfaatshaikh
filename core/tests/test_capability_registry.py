"""CapabilityRegistry joins the real, already-tested catalog with an
actual running ConnectorRegistry -- these tests prove it reports real
availability (a capability whose connector isn't registered shows as
unavailable) and real risk tiers (from the same RiskEngine every
submission through the Action Broker is already classified against),
never inventing a capability that has no registered handler.
"""
from __future__ import annotations

from aura_core.capabilities import CAPABILITY_CATALOG, Capability, CapabilityRegistry
from aura_core.connectors import ConnectorRegistry, FilesystemConnector, build_github_connector
from aura_core.governance.action_broker import ActionBroker
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import RiskEngine, RiskTier


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/capreg.db"
    policy = PolicyEngine(db_url)
    return ActionBroker(policy, RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))


def test_every_cataloged_capability_has_a_domain_and_a_description():
    for capability in CAPABILITY_CATALOG.values():
        assert capability.domain, capability.name
        assert capability.description, capability.name


def test_list_available_only_includes_capabilities_whose_connector_is_actually_registered(tmp_path):
    broker = make_broker(tmp_path)
    connectors = ConnectorRegistry(broker)
    connectors.register(FilesystemConnector(str(tmp_path / "sandbox")))

    registry = CapabilityRegistry(connectors)

    available_names = {c.name for c in registry.list_available()}
    assert "filesystem.read_file" in available_names
    assert "github.list_pull_requests" not in available_names  # not registered in this test


def test_registering_a_connector_makes_its_capabilities_available(tmp_path):
    broker = make_broker(tmp_path)
    connectors = ConnectorRegistry(broker)
    registry = CapabilityRegistry(connectors)

    assert not registry.is_handler_registered("github.list_pull_requests")

    connectors.register(build_github_connector(token=None))

    assert registry.is_handler_registered("github.list_pull_requests")


def test_status_reports_the_real_risk_tier_from_the_shared_risk_engine(tmp_path):
    broker = make_broker(tmp_path)
    connectors = ConnectorRegistry(broker)
    connectors.register(FilesystemConnector(str(tmp_path / "sandbox")))
    registry = CapabilityRegistry(connectors)

    read_status = registry.status("filesystem.read_file")
    write_status = registry.status("filesystem.write_file")

    assert read_status.risk_tier == RiskTier.GREEN
    assert write_status.risk_tier == RiskTier.AMBER
    assert read_status.handler_registered is True


def test_status_for_an_unknown_capability_is_honestly_none(tmp_path):
    broker = make_broker(tmp_path)
    registry = CapabilityRegistry(ConnectorRegistry(broker))

    assert registry.status("not.a.real.capability") is None


def test_domains_reflects_the_real_catalog():
    broker_free_registry = CapabilityRegistry.__new__(CapabilityRegistry)
    broker_free_registry._catalog = dict(CAPABILITY_CATALOG)
    domains = broker_free_registry.domains()
    assert "email" in domains
    assert "social" in domains
    assert "engineering" in domains


def test_register_adds_a_new_catalog_entry_without_touching_existing_ones(tmp_path):
    broker = make_broker(tmp_path)
    registry = CapabilityRegistry(ConnectorRegistry(broker))

    registry.register(Capability(name="custom.thing", domain="custom", description="a new one"))

    assert registry.get("custom.thing") is not None
    assert registry.get("filesystem.read_file") is not None
