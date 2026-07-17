"""Outbound transactional email via SMTP.

In local development this points at the Mailpit/Maildev capture service
configured in docker-compose (no real mail is sent, nothing leaves the
local network). In production it points at a real SMTP relay configured
via SMTP_HOST/SMTP_PORT. This is a genuine SMTP client, not a mock -
what differs between environments is only the destination server.
"""

from email.message import EmailMessage

import aiosmtplib

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("gridkeep.mail")


async def send_email(
    *, to_email: str, subject: str, text_body: str, html_body: str | None = None
) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    try:
        await aiosmtplib.send(message, hostname=settings.smtp_host, port=settings.smtp_port)
    except Exception:
        logger.exception(
            "email_send_failed", to_email_domain=to_email.rsplit("@", 1)[-1], subject=subject
        )
        raise
