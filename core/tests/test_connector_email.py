from __future__ import annotations

import socket

import pytest
from aiosmtpd.controller import Controller


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

from aura_core.connectors import ConnectorRegistry
from aura_core.connectors.email_connector import SmtpConnector
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine
from aura_core.status import CapabilityStatus


class _RecordingHandler:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def handle_DATA(self, server, session, envelope):
        self.messages.append({
            "mail_from": envelope.mail_from,
            "rcpt_tos": envelope.rcpt_tos,
            "content": envelope.content.decode("utf-8", errors="replace"),
        })
        return "250 Message accepted for delivery"


@pytest.fixture
def smtp_server():
    handler = _RecordingHandler()
    controller = Controller(handler, hostname="127.0.0.1", port=_free_port())
    controller.start()
    try:
        yield controller, handler
    finally:
        controller.stop()


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/email.db"
    policy = PolicyEngine(db_url)
    broker = ActionBroker(policy, RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    return broker, policy


def test_health_check_against_a_real_local_smtp_server(smtp_server):
    controller, _handler = smtp_server
    connector = SmtpConnector(host=controller.hostname, port=controller.port)
    result = connector.health_check()
    assert result.status == CapabilityStatus.LIVE


def test_health_check_reports_unavailable_when_nothing_is_listening():
    connector = SmtpConnector(host="127.0.0.1", port=1)  # nothing listens on port 1
    result = connector.health_check()
    assert result.status == CapabilityStatus.UNAVAILABLE


def test_send_actually_delivers_to_the_real_local_server(tmp_path, smtp_server):
    controller, handler = smtp_server
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("email.send_external", 4)
    connector = SmtpConnector(host=controller.hostname, port=controller.port, from_address="aura@example.test")
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="email.send_external",
        params={"to": "owner@example.test", "subject": "Daily brief", "body": "Three things happened today."},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    assert len(handler.messages) == 1
    delivered = handler.messages[0]
    assert delivered["mail_from"] == "aura@example.test"
    assert delivered["rcpt_tos"] == ["owner@example.test"]
    assert "Three things happened today." in delivered["content"]
    assert "Daily brief" in delivered["content"]


def test_send_failure_reported_honestly_not_as_executed(tmp_path):
    broker, policy = make_broker(tmp_path)
    policy.set_autonomy_level("email.send_external", 4)
    connector = SmtpConnector(host="127.0.0.1", port=1)  # nothing listening
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="email.send_external", params={"to": "x@example.test", "subject": "s", "body": "b"},
    ))

    assert outcome.status == OutcomeStatus.DENIED  # DEGRADED handler result -> broker reports DENIED, not EXECUTED
    assert "DEGRADED" in outcome.message
