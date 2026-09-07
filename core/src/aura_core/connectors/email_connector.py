"""Email connectors. Real smtplib/imaplib code — tested in this session
against real local SMTP (aiosmtpd) and IMAP (a minimal hand-rolled fake
server implementing just enough of RFC 3501 to prove the client-side
protocol usage) servers, never against a live external mailbox (no
credentials for one exist here).
"""
from __future__ import annotations

import imaplib
import json
import smtplib
from email import message_from_bytes
from email.header import decode_header
from email.message import EmailMessage

from ..governance.action_broker import ActionRequest, HandlerResult
from ..status import CapabilityStatus
from .base import Connector, ConnectorManifest


class SmtpConnector(Connector):
    def __init__(
        self, host: str, port: int, *, username: str | None = None,
        password: str | None = None, use_starttls: bool = False, from_address: str = "aura@localhost",
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_starttls = use_starttls
        self._from_address = from_address
        self.manifest = ConnectorManifest(
            name="email",
            auth_method="smtp_credentials" if username else "none",
            required_credentials=["username", "password"] if username else [],
            capabilities=["email.send_external"],
            notes=f"{host}:{port}",
        )

    def _connect(self) -> smtplib.SMTP:
        client = smtplib.SMTP(self._host, self._port, timeout=10)
        if self._use_starttls:
            client.starttls()
        if self._username:
            client.login(self._username, self._password or "")
        return client

    def health_check(self) -> HandlerResult:
        try:
            client = self._connect()
            client.quit()
            return HandlerResult(CapabilityStatus.LIVE, f"connected to {self._host}:{self._port}")
        except (OSError, smtplib.SMTPException) as exc:
            return HandlerResult(CapabilityStatus.UNAVAILABLE, f"cannot reach {self._host}:{self._port}: {exc}")

    def send(self, request: ActionRequest) -> HandlerResult:
        message = EmailMessage()
        message["From"] = self._from_address
        message["To"] = request.params["to"]
        message["Subject"] = request.params.get("subject", "")
        message.set_content(request.params.get("body", ""))

        try:
            client = self._connect()
            try:
                client.send_message(message)
            finally:
                client.quit()
            return HandlerResult(CapabilityStatus.LIVE, f"sent to {request.params['to']}")
        except (OSError, smtplib.SMTPException) as exc:
            return HandlerResult(CapabilityStatus.DEGRADED, f"send failed: {exc}")

    def handlers(self) -> dict:
        return {"email.send_external": self.send}


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for text, encoding in parts:
        if isinstance(text, bytes):
            decoded.append(text.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded.append(text)
    return "".join(decoded)


def _summarize_headers(uid: str, parsed) -> dict:
    references_raw = parsed.get("References", "")
    return {
        "uid": uid,
        "message_id": parsed.get("Message-ID"),
        "in_reply_to": parsed.get("In-Reply-To"),
        "references": references_raw.split() if references_raw else [],
        "subject": _decode_header_value(parsed.get("Subject")),
        "from": _decode_header_value(parsed.get("From")),
        "date": parsed.get("Date"),
    }


def _extract_body(parsed) -> str:
    if parsed.is_multipart():
        for part in parsed.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        return ""
    payload = parsed.get_payload(decode=True) or b""
    return payload.decode(parsed.get_content_charset() or "utf-8", errors="replace")


def build_threads(messages: list[dict]) -> list[list[dict]]:
    """Groups message summaries (as returned by list_messages/get_message)
    into conversation threads using the References/In-Reply-To chain, per
    section 12's "threading" requirement. A pure function, deliberately
    free of any I/O, so thread reconstruction can be tested and trusted
    independently of the IMAP client plumbing around it."""
    known_ids = {m["message_id"] for m in messages if m.get("message_id")}

    def parent_of(message: dict) -> str | None:
        references = message.get("references") or []
        if references:
            return references[-1]
        return message.get("in_reply_to")

    def root_of(message: dict) -> str:
        current = message.get("message_id")
        seen: set[str] = set()
        while current and current in seen_lookup:
            parent = parent_of(seen_lookup[current])
            if not parent or parent not in known_ids or parent in seen:
                return current
            seen.add(current)
            current = parent
        return current or f"__no_id_{id(message)}"

    seen_lookup = {m["message_id"]: m for m in messages if m.get("message_id")}

    threads: dict[str, list[dict]] = {}
    for message in messages:
        root = root_of(message) if message.get("message_id") else f"__no_id_{id(message)}"
        threads.setdefault(root, []).append(message)

    return [
        sorted(group, key=lambda m: m.get("date") or "")
        for group in threads.values()
    ]


class ImapConnector(Connector):
    """Read-only IMAP receive: list/search/fetch. Drafts and automatic
    classification are not implemented in this pass -- IMPLEMENTABLE_NOW,
    flagged as remaining work in docs/FINAL_COMPLETION_AUDIT.md."""

    def __init__(
        self, host: str, port: int = 993, *, username: str | None = None,
        password: str | None = None, use_ssl: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_ssl = use_ssl
        self.manifest = ConnectorManifest(
            name="email_inbox",
            auth_method="imap_credentials" if username else "none",
            required_credentials=["username", "password"] if username else [],
            capabilities=["email.list_messages", "email.get_message", "email.search_messages", "email.save_draft"],
            notes=f"{host}:{port}",
        )

    def _connect(self) -> imaplib.IMAP4:
        client: imaplib.IMAP4
        if self._use_ssl:
            client = imaplib.IMAP4_SSL(self._host, self._port)
        else:
            client = imaplib.IMAP4(self._host, self._port)
        if self._username:
            client.login(self._username, self._password or "")
        return client

    def health_check(self) -> HandlerResult:
        try:
            client = self._connect()
            client.logout()
            return HandlerResult(CapabilityStatus.LIVE, f"connected to {self._host}:{self._port}")
        except (OSError, imaplib.IMAP4.error) as exc:
            return HandlerResult(CapabilityStatus.UNAVAILABLE, f"cannot reach {self._host}:{self._port}: {exc}")

    def list_messages(self, request: ActionRequest) -> HandlerResult:
        folder = request.params.get("folder", "INBOX")
        limit = int(request.params.get("limit", 20))
        criteria = "UNSEEN" if request.params.get("unseen_only") else "ALL"

        try:
            client = self._connect()
            try:
                client.select(folder, readonly=True)
                status, data = client.uid("search", None, criteria)
                if status != "OK":
                    return HandlerResult(CapabilityStatus.DEGRADED, f"search failed: {data}")
                uids = [u.decode() for u in data[0].split()]
                if limit:
                    uids = uids[-limit:]
                messages = []
                for uid in uids:
                    status, msg_data = client.uid("fetch", uid, "(RFC822.HEADER)")
                    if status != "OK" or not msg_data or msg_data[0] is None:
                        continue
                    parsed = message_from_bytes(msg_data[0][1])
                    messages.append(_summarize_headers(uid, parsed))
                return HandlerResult(CapabilityStatus.LIVE, json.dumps(messages))
            finally:
                client.logout()
        except (OSError, imaplib.IMAP4.error) as exc:
            return HandlerResult(CapabilityStatus.DEGRADED, f"list_messages failed: {exc}")

    def get_message(self, request: ActionRequest) -> HandlerResult:
        folder = request.params.get("folder", "INBOX")
        uid = str(request.params["uid"])

        try:
            client = self._connect()
            try:
                client.select(folder, readonly=True)
                status, msg_data = client.uid("fetch", uid, "(RFC822)")
                if status != "OK" or not msg_data or msg_data[0] is None:
                    return HandlerResult(CapabilityStatus.DEGRADED, f"message '{uid}' not found in '{folder}'")
                parsed = message_from_bytes(msg_data[0][1])
                summary = _summarize_headers(uid, parsed)
                summary["body"] = _extract_body(parsed)
                return HandlerResult(CapabilityStatus.LIVE, json.dumps(summary))
            finally:
                client.logout()
        except (OSError, imaplib.IMAP4.error) as exc:
            return HandlerResult(CapabilityStatus.DEGRADED, f"get_message failed: {exc}")

    def search_messages(self, request: ActionRequest) -> HandlerResult:
        folder = request.params.get("folder", "INBOX")
        criteria = request.params.get("criteria", "ALL")

        try:
            client = self._connect()
            try:
                client.select(folder, readonly=True)
                status, data = client.uid("search", None, criteria)
                if status != "OK":
                    return HandlerResult(CapabilityStatus.DEGRADED, f"search failed: {data}")
                uids = [u.decode() for u in data[0].split()]
                messages = []
                for uid in uids:
                    status, msg_data = client.uid("fetch", uid, "(RFC822.HEADER)")
                    if status != "OK" or not msg_data or msg_data[0] is None:
                        continue
                    parsed = message_from_bytes(msg_data[0][1])
                    messages.append(_summarize_headers(uid, parsed))
                return HandlerResult(CapabilityStatus.LIVE, json.dumps(messages))
            finally:
                client.logout()
        except (OSError, imaplib.IMAP4.error) as exc:
            return HandlerResult(CapabilityStatus.DEGRADED, f"search_messages failed: {exc}")

    def save_draft(self, request: ActionRequest) -> HandlerResult:
        """Real IMAP APPEND with the \\Draft flag, closing the "drafts"
        half of section 12's email gap. Not sent -- appended to the
        drafts folder only, exactly like composing a message and closing
        the window without pressing send in any real mail client."""
        folder = request.params.get("folder", "Drafts")
        to = request.params.get("to", "")
        subject = request.params.get("subject", "")
        body_text = request.params.get("body", "")

        message = EmailMessage()
        if to:
            message["To"] = to
        message["Subject"] = subject
        message.set_content(body_text)

        try:
            client = self._connect()
            try:
                # imaplib does not quote the mailbox argument for you --
                # an unquoted name containing a space breaks the raw IMAP
                # command syntax. A quoted string is always valid IMAP
                # syntax, so quoting unconditionally (with minimal
                # backslash/quote escaping) is simpler and safer than
                # only quoting when a space happens to be present.
                quoted_folder = '"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"'
                status, response = client.append(quoted_folder, "(\\Draft)", None, message.as_bytes())
                if status != "OK":
                    return HandlerResult(CapabilityStatus.DEGRADED, f"append failed: {response}")
                return HandlerResult(CapabilityStatus.LIVE, json.dumps({"folder": folder, "to": to, "subject": subject}))
            finally:
                client.logout()
        except (OSError, imaplib.IMAP4.error) as exc:
            return HandlerResult(CapabilityStatus.DEGRADED, f"save_draft failed: {exc}")

    def handlers(self) -> dict:
        return {
            "email.list_messages": self.list_messages,
            "email.get_message": self.get_message,
            "email.search_messages": self.search_messages,
            "email.save_draft": self.save_draft,
        }
