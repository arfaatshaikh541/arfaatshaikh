"""The Celery application: which tasks it registers, that the schedule only names real tasks, and the pure parts of the mail job."""
import json
import smtplib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "worker"))

from app.services import background  # noqa: E402
from app.core.config import get_settings  # noqa: E402

EXPECTED = {"woi.email.send_outbox", "woi.auth.purge_expired", "woi.data.validate"}


def test_the_worker_registers_exactly_the_intended_tasks():
    from worker.celery_app import celery_app
    import worker.tasks  # noqa: F401
    registered = {name for name in celery_app.tasks if name.startswith("woi.")}
    assert registered == EXPECTED


def test_every_scheduled_entry_points_at_a_registered_task():
    from worker.celery_app import celery_app
    import worker.tasks  # noqa: F401
    scheduled = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert scheduled == EXPECTED and scheduled <= set(celery_app.tasks)


def test_mail_task_retries_only_on_a_mail_outage_and_has_a_bounded_policy():
    import worker.tasks as t
    task = t.send_email_outbox
    assert task.max_retries == 5 and task.retry_backoff and task.retry_jitter
    assert background.TransientEmailError in task.autoretry_for
    assert background.PermanentEmailError not in task.autoretry_for


def test_verification_mail_puts_the_token_in_the_url_fragment_not_the_query():
    subject, body = background.render_email("verify-email-v1", {"token": "T" * 40}, "https://app.arfaat.com/worldofislam")
    assert "https://app.arfaat.com/worldofislam/en/verify-email#token=" + "T" * 40 in body
    assert "?token=" not in body and "Confirm" in subject


def test_reset_mail_and_unknown_template():
    _, body = background.render_email("password-reset-v1", {"token": "R" * 40}, "https://x.example")
    assert "https://x.example/en/reset-password#token=" + "R" * 40 in body
    with pytest.raises(background.PermanentEmailError):
        background.render_email("nope", {}, "https://x.example")


def test_base_url_falls_back_to_the_first_allowed_origin_and_cookie_path():
    settings = get_settings().model_copy(update={"public_base_url": "", "cookie_path": "/worldofislam"})
    assert background.base_url(settings).endswith("/worldofislam")
    assert background.base_url(settings.model_copy(update={"public_base_url": "https://h.example/w/"})) == "https://h.example/w"


class _FakeSMTP:
    behaviour: Exception | None = None
    sent: list = []

    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def starttls(self, **k): pass
    def login(self, *a): pass
    def send_message(self, message):
        if self.behaviour:
            raise self.behaviour
        self.sent.append(message)


@pytest.mark.parametrize("error,expected", [
    (smtplib.SMTPRecipientsRefused({"a@b": (550, b"no")}), background.PermanentEmailError),
    (smtplib.SMTPResponseException(554, b"rejected"), background.PermanentEmailError),
    (smtplib.SMTPResponseException(451, b"try later"), background.TransientEmailError),
    (smtplib.SMTPResponseException(535, b"bad credentials"), background.TransientEmailError),
    (smtplib.SMTPServerDisconnected("gone"), background.TransientEmailError),
    (ConnectionRefusedError(), background.TransientEmailError),
])
def test_smtp_errors_are_classified_as_permanent_or_transient(monkeypatch, error, expected):
    monkeypatch.setattr(background.smtplib, "SMTP", _FakeSMTP)
    _FakeSMTP.behaviour = error
    settings = get_settings().model_copy(update={"smtp_host": "mail.example", "smtp_from": "no-reply@example.org", "smtp_username": ""})
    with pytest.raises(expected):
        background.smtp_sender(settings)("a@b.example", "s", "b")


def test_a_successful_smtp_send_builds_a_plain_text_message(monkeypatch):
    monkeypatch.setattr(background.smtplib, "SMTP", _FakeSMTP)
    _FakeSMTP.behaviour, _FakeSMTP.sent = None, []
    settings = get_settings().model_copy(update={"smtp_host": "mail.example", "smtp_from": "no-reply@example.org", "smtp_username": ""})
    background.smtp_sender(settings)("a@b.example", "Hello", "Body")
    message = _FakeSMTP.sent[0]
    assert message["To"] == "a@b.example" and message["From"] == "no-reply@example.org" and message.get_content().strip() == "Body"
    assert json.loads(background.REDACTED_PAYLOAD)["token"].startswith("[removed")
