from app.services.email_service import EmailMessage, send_email_safely
from worker.celery_app import celery_app


@celery_app.task(
    name="worker.tasks.send_email",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def send_email_task(
    self,  # type: ignore[no-untyped-def]
    *,
    to: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> None:
    """Background email delivery. Auth flows (invite/verify/reset) currently
    send synchronously from the request path for immediate feedback in
    local dev; this task exists so later milestones (assignment alerts,
    follow-up reminders, workflow actions) can enqueue email without
    blocking a request. See docs/product/milestone-1-acceptance-criteria.md
    for what's in vs. out of scope for Milestone 1's communications layer."""
    try:
        send_email_safely(
            EmailMessage(to=to, subject=subject, text_body=text_body, html_body=html_body)
        )
    except Exception as exc:  # noqa: BLE001 - retry on any transient send failure
        raise self.retry(exc=exc) from exc
