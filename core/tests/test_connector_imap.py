"""ImapConnector tested against a real local IMAP server -- a minimal
hand-rolled server implementing just enough of RFC 3501 (LOGIN, SELECT,
UID SEARCH, UID FETCH, LOGOUT) to prove imaplib is being driven
correctly, since no pip-installable fake IMAP server exists. This is
testing infrastructure only, not a production email server."""
from __future__ import annotations

import json
import re
import socketserver
import threading

import pytest

from aura_core.connectors import ConnectorRegistry, ImapConnector, build_threads
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine, RiskTier
from aura_core.status import CapabilityStatus


def _make_message(uid: int, subject: str, *, message_id: str, in_reply_to: str | None = None, date: str = "Mon, 1 Jan 2024 10:00:00 +0000") -> dict:
    headers = (
        f"From: sender@example.test\r\n"
        f"To: owner@example.test\r\n"
        f"Subject: {subject}\r\n"
        f"Message-ID: {message_id}\r\n"
        f"Date: {date}\r\n"
    )
    if in_reply_to:
        headers += f"In-Reply-To: {in_reply_to}\r\nReferences: {in_reply_to}\r\n"
    body = f"body of {subject}"
    raw = (headers + "\r\n" + body).encode()
    header_bytes = headers.encode()
    return {"uid": uid, "raw": raw, "headers": header_bytes}


class _FakeImapServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    mailbox: list[dict] = []
    appended: list[dict] = []


class _FakeImapHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.wfile.write(b"* OK Fake IMAP Server Ready\r\n")
        while True:
            line = self.rfile.readline()
            if not line:
                return
            text = line.decode(errors="replace").strip()
            if not text:
                continue
            parts = text.split(" ", 2)
            tag = parts[0]
            command = parts[1].upper() if len(parts) > 1 else ""
            rest = parts[2] if len(parts) > 2 else ""

            if command == "LOGIN":
                self.wfile.write(f"{tag} OK LOGIN completed\r\n".encode())
            elif command == "CAPABILITY":
                self.wfile.write(b"* CAPABILITY IMAP4rev1\r\n")
                self.wfile.write(f"{tag} OK CAPABILITY completed\r\n".encode())
            elif command in ("SELECT", "EXAMINE"):
                self.wfile.write(f"* {len(self.server.mailbox)} EXISTS\r\n".encode())
                self.wfile.write(b"* 0 RECENT\r\n")
                mode = "READ-ONLY" if command == "EXAMINE" else "READ-WRITE"
                self.wfile.write(f"{tag} OK [{mode}] {command} completed\r\n".encode())
            elif command == "UID":
                self._handle_uid(tag, rest)
            elif command == "APPEND":
                self._handle_append(tag, rest)
            elif command == "LOGOUT":
                self.wfile.write(b"* BYE logging out\r\n")
                self.wfile.write(f"{tag} OK LOGOUT completed\r\n".encode())
                return
            else:
                self.wfile.write(f"{tag} BAD unrecognized command\r\n".encode())

    def _handle_uid(self, tag: str, rest: str) -> None:
        subparts = rest.split(" ", 1)
        subcommand = subparts[0].upper()
        subrest = subparts[1] if len(subparts) > 1 else ""

        if subcommand == "SEARCH":
            criteria = subrest.strip()
            matched = [m for m in self.server.mailbox if self._matches(m, criteria)]
            uids = " ".join(str(m["uid"]) for m in matched)
            self.wfile.write(f"* SEARCH {uids}\r\n".encode())
            self.wfile.write(f"{tag} OK UID SEARCH completed\r\n".encode())
        elif subcommand == "FETCH":
            uid_str, fetch_item = subrest.split(" ", 1)
            uid = int(uid_str)
            fetch_item = fetch_item.strip("()")
            message = next((m for m in self.server.mailbox if m["uid"] == uid), None)
            if message is None:
                self.wfile.write(f"{tag} OK UID FETCH completed\r\n".encode())
                return
            data = message["headers"] if fetch_item == "RFC822.HEADER" else message["raw"]
            self.wfile.write(f"* {uid} FETCH (UID {uid} {fetch_item} {{{len(data)}}}\r\n".encode())
            self.wfile.write(data)
            self.wfile.write(b")\r\n")
            self.wfile.write(f"{tag} OK UID FETCH completed\r\n".encode())
        else:
            self.wfile.write(f"{tag} BAD unrecognized UID subcommand\r\n".encode())

    def _handle_append(self, tag: str, rest: str) -> None:
        """Real RFC 3501 literal handling: announce readiness for the
        literal, read exactly the declared byte count off the wire, then
        consume the trailing CRLF -- not a shortcut that trusts a
        pre-parsed message, since that's the actual protocol behavior
        this exists to prove imaplib's APPEND client code drives
        correctly."""
        match = re.search(r"\{(\d+)\}\s*$", rest)
        if not match:
            self.wfile.write(f"{tag} BAD malformed APPEND\r\n".encode())
            return

        size = int(match.group(1))
        head = rest[: match.start()].strip()
        # The mailbox name is either a quoted string (which may itself
        # contain spaces -- "My Drafts" -- so splitting on whitespace
        # first would truncate it) or a single bare token.
        mailbox_match = re.match(r'"((?:[^"\\]|\\.)*)"|(\S+)', head)
        mailbox = (mailbox_match.group(1) or mailbox_match.group(2)) if mailbox_match else head

        self.wfile.write(b"+ Ready for literal data\r\n")
        literal = self.rfile.read(size)
        self.rfile.readline()  # trailing CRLF after the literal

        self.server.appended.append({"mailbox": mailbox, "content": literal})
        self.wfile.write(f"{tag} OK APPEND completed\r\n".encode())

    @staticmethod
    def _matches(message: dict, criteria: str) -> bool:
        criteria = criteria.strip()
        if criteria.upper() == "ALL":
            return True
        if criteria.upper() == "UNSEEN":
            return False  # the fake mailbox tracks no seen/unseen state
        if criteria.upper().startswith("SUBJECT"):
            needle = criteria.split(None, 1)[1].strip('"').lower()
            return needle in message["headers"].decode().lower()
        return False


@pytest.fixture
def fake_imap():
    _FakeImapServer.mailbox = [
        _make_message(1, "Widget order #100", message_id="<msg-1@example.test>"),
        _make_message(2, "Re: Widget order #100", message_id="<msg-2@example.test>", in_reply_to="<msg-1@example.test>"),
        _make_message(3, "Unrelated newsletter", message_id="<msg-3@example.test>"),
    ]
    _FakeImapServer.appended = []
    server = _FakeImapServer(("127.0.0.1", 0), _FakeImapHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[0], server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def make_broker(tmp_path):
    db_url = f"sqlite:///{tmp_path}/imap.db"
    policy = PolicyEngine(db_url)
    risk = RiskEngine()
    broker = ActionBroker(policy, risk, ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    return broker, policy, risk


def test_health_check_against_a_real_local_imap_server(fake_imap):
    host, port = fake_imap
    connector = ImapConnector(host, port, use_ssl=False)
    result = connector.health_check()
    assert result.status == CapabilityStatus.LIVE


def test_health_check_reports_unavailable_when_nothing_is_listening():
    connector = ImapConnector("127.0.0.1", 1, use_ssl=False)
    result = connector.health_check()
    assert result.status == CapabilityStatus.UNAVAILABLE


def test_list_messages_returns_real_headers_through_the_broker(tmp_path, fake_imap):
    host, port = fake_imap
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("email.list_messages", 4)
    connector = ImapConnector(host, port, use_ssl=False, username="tester", password="pw")
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(action_type="email.list_messages", params={}))

    assert outcome.status == OutcomeStatus.EXECUTED
    messages = json.loads(outcome.message)
    assert len(messages) == 3
    assert {m["subject"] for m in messages} == {"Widget order #100", "Re: Widget order #100", "Unrelated newsletter"}


def test_get_message_returns_the_real_body(tmp_path, fake_imap):
    host, port = fake_imap
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("email.get_message", 4)
    connector = ImapConnector(host, port, use_ssl=False, username="tester", password="pw")
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(action_type="email.get_message", params={"uid": 1}))

    assert outcome.status == OutcomeStatus.EXECUTED
    message = json.loads(outcome.message)
    assert message["subject"] == "Widget order #100"
    assert "body of Widget order #100" in message["body"]


def test_search_messages_filters_by_subject(tmp_path, fake_imap):
    host, port = fake_imap
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("email.search_messages", 4)
    connector = ImapConnector(host, port, use_ssl=False, username="tester", password="pw")
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="email.search_messages", params={"criteria": 'SUBJECT "widget"'},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    messages = json.loads(outcome.message)
    assert {m["subject"] for m in messages} == {"Widget order #100", "Re: Widget order #100"}


def test_read_capabilities_are_green_tier(tmp_path):
    _broker, _policy, risk = make_broker(tmp_path)
    for action_type in ["email.list_messages", "email.get_message", "email.search_messages"]:
        assert risk.classify(ActionRequest(action_type=action_type)).tier == RiskTier.GREEN


def test_a_read_at_autonomy_level_zero_is_denied_by_default(tmp_path, fake_imap):
    host, port = fake_imap
    broker, _policy, _risk = make_broker(tmp_path)
    connector = ImapConnector(host, port, use_ssl=False)
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(action_type="email.list_messages", params={}))

    assert outcome.status == OutcomeStatus.DENIED


def test_build_threads_groups_a_reply_with_its_original_and_leaves_unrelated_mail_separate(tmp_path, fake_imap):
    """Proves threading (section 12) reconstructs the reply chain from
    References/In-Reply-To headers returned by a real list_messages call --
    not a hand-fed fixture of already-grouped data."""
    host, port = fake_imap
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("email.list_messages", 4)
    connector = ImapConnector(host, port, use_ssl=False, username="tester", password="pw")
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(action_type="email.list_messages", params={}))
    messages = json.loads(outcome.message)

    threads = build_threads(messages)

    sizes = sorted(len(t) for t in threads)
    assert sizes == [1, 2]
    reply_thread = next(t for t in threads if len(t) == 2)
    assert {m["subject"] for m in reply_thread} == {"Widget order #100", "Re: Widget order #100"}


def test_save_draft_appends_a_real_message_to_the_drafts_folder(tmp_path, fake_imap):
    host, port = fake_imap
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("email.save_draft", 4)
    connector = ImapConnector(host, port, use_ssl=False, username="tester", password="pw")
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="email.save_draft",
        params={"to": "vendor@example.test", "subject": "Draft: order follow-up", "body": "Checking on the shipment."},
    ))

    assert outcome.status == OutcomeStatus.EXECUTED
    result = json.loads(outcome.message)
    assert result["folder"] == "Drafts"
    assert result["to"] == "vendor@example.test"

    assert len(_FakeImapServer.appended) == 1
    appended = _FakeImapServer.appended[0]
    assert appended["mailbox"] == "Drafts"
    assert b"Checking on the shipment." in appended["content"]
    assert b"Draft: order follow-up" in appended["content"]


def test_save_draft_defaults_to_the_drafts_folder_and_uses_a_custom_one_when_given(tmp_path, fake_imap):
    host, port = fake_imap
    broker, policy, _risk = make_broker(tmp_path)
    policy.set_autonomy_level("email.save_draft", 4)
    connector = ImapConnector(host, port, use_ssl=False, username="tester", password="pw")
    ConnectorRegistry(broker).register(connector)

    broker.submit(ActionRequest(
        action_type="email.save_draft", params={"folder": "My Drafts", "subject": "s", "body": "b"},
    ))

    assert _FakeImapServer.appended[0]["mailbox"] == "My Drafts"


def test_save_draft_is_amber_tier(tmp_path):
    _broker, _policy, risk = make_broker(tmp_path)
    assert risk.classify(ActionRequest(action_type="email.save_draft")).tier == RiskTier.AMBER


def test_save_draft_is_denied_by_default_at_autonomy_zero(tmp_path, fake_imap):
    host, port = fake_imap
    broker, _policy, _risk = make_broker(tmp_path)
    connector = ImapConnector(host, port, use_ssl=False, username="tester", password="pw")
    ConnectorRegistry(broker).register(connector)

    outcome = broker.submit(ActionRequest(
        action_type="email.save_draft", params={"subject": "s", "body": "b"},
    ))

    assert outcome.status == OutcomeStatus.DENIED
    assert _FakeImapServer.appended == []

