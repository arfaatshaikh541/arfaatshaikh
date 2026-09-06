"""SMTP email connector. Real smtplib code — tested in this session
against a real local SMTP server (aiosmtpd), never against a live
external mailbox (no credentials for one exist here). Reading mail
(IMAP) is not implemented; only outbound send.
"""
from __future__ import annotations

import smtplib
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
