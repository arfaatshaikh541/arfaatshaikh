"""Module 10 communications: tenant-configurable message templates.

Rendering uses a regex-based ``{{variable}}`` substitution - never
``eval``/``exec``, never ``str.format`` (which exposes attribute/index
access via ``{obj.__class__}``-style expressions). Unknown variables
render as an empty string rather than raising, so a template edited to
reference a field that doesn't apply to the current context degrades
gracefully instead of breaking delivery. See
docs/architecture/erd-summary-m3.md.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.communication import MESSAGE_TEMPLATE_KEYS, MessageTemplate
from app.repositories.communication import MessageTemplateRepository
from app.services.errors import NotFoundError, ValidationError

_VARIABLE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

DEFAULT_TEMPLATES: dict[str, dict[str, str]] = {
    "acknowledgement": {
        "subject": "We've received your enquiry, {{first_name}}",
        "body": (
            "Hi {{first_name}},\n\n"
            "Thank you for reaching out to {{tenant_name}}. We've received your enquiry "
            "and a member of our team will be in touch shortly.\n\n"
            "Reference: {{lead_id}}"
        ),
    },
    "assignment_alert": {
        "subject": "New lead assigned to you: {{lead_name}}",
        "body": (
            "Hi {{assignee_name}},\n\n"
            "A new lead has been assigned to you.\n\n"
            "Name: {{lead_name}}\nContact: {{lead_email}}\nService: {{service_name}}\n\n"
            "Please review and reach out."
        ),
    },
    "appointment_confirmation": {
        "subject": "Your appointment with {{tenant_name}} is confirmed",
        "body": (
            "Hi {{first_name}},\n\n"
            "Your appointment is confirmed for {{appointment_time}}.\n\n"
            "If you need to reschedule, please contact us."
        ),
    },
    "appointment_reminder": {
        "subject": "Reminder: your appointment with {{tenant_name}}",
        "body": (
            "Hi {{first_name}},\n\n"
            "This is a reminder of your upcoming appointment at {{appointment_time}}."
        ),
    },
    "follow_up": {
        "subject": "Following up on your enquiry",
        "body": (
            "Hi {{first_name}},\n\n"
            "Just following up on your enquiry with {{tenant_name}}. Are you still interested?"
        ),
    },
}


def render_template(text: str, context: dict[str, str]) -> str:
    """Safe, non-executable substitution of ``{{key}}`` placeholders."""

    def _replace(match: re.Match[str]) -> str:
        return context.get(match.group(1), "")

    return _VARIABLE_PATTERN.sub(_replace, text)


@dataclass
class RenderedMessage:
    subject: str
    body: str


class MessageTemplateService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.templates = MessageTemplateRepository(db)

    def list_templates(self, tenant_id: uuid.UUID) -> list[MessageTemplate]:
        return self.templates.list_for_tenant(tenant_id)

    def get_or_404(self, tenant_id: uuid.UUID, template_id: uuid.UUID) -> MessageTemplate:
        template = self.templates.get_by_id_for_tenant(tenant_id, template_id)
        if template is None:
            raise NotFoundError("Message template not found.")
        return template

    def get_by_key(self, tenant_id: uuid.UUID, key: str) -> MessageTemplate | None:
        return self.templates.get_by_key(tenant_id, key)

    def create(self, tenant_id: uuid.UUID, *, key: str, subject: str, body: str) -> MessageTemplate:
        if key not in MESSAGE_TEMPLATE_KEYS:
            raise ValidationError(f"Unknown message template key '{key}'.")
        if self.templates.get_by_key(tenant_id, key) is not None:
            raise ValidationError(f"A template for key '{key}' already exists for this tenant.")
        return self.templates.create(tenant_id=tenant_id, key=key, subject=subject, body=body)

    def update(
        self, tenant_id: uuid.UUID, template_id: uuid.UUID, **fields: object
    ) -> MessageTemplate:
        template = self.get_or_404(tenant_id, template_id)
        return self.templates.update(template, **fields)

    def render(
        self, tenant_id: uuid.UUID, key: str, context: dict[str, str]
    ) -> RenderedMessage | None:
        """Render the tenant's template for ``key``, falling back to the
        built-in default copy if the tenant hasn't customized it. Returns
        None only if the template is explicitly deactivated."""
        template = self.templates.get_by_key(tenant_id, key)
        if template is not None:
            if not template.is_active:
                return None
            return RenderedMessage(
                subject=render_template(template.subject, context),
                body=render_template(template.body, context),
            )
        default = DEFAULT_TEMPLATES.get(key)
        if default is None:
            return None
        return RenderedMessage(
            subject=render_template(default["subject"], context),
            body=render_template(default["body"], context),
        )

    def seed_defaults_for_tenant(self, tenant_id: uuid.UUID) -> list[MessageTemplate]:
        created = []
        for key, defaults in DEFAULT_TEMPLATES.items():
            if self.templates.get_by_key(tenant_id, key) is not None:
                continue
            created.append(
                self.templates.create(
                    tenant_id=tenant_id, key=key, subject=defaults["subject"], body=defaults["body"]
                )
            )
        return created
