"""`push_lead_to_integration` - delivers one `IntegrationDelivery`'s
already-built payload to its `Integration`'s webhook: sign it (HMAC-
SHA256 over the exact bytes sent, `X-Gridkeep-Signature`), POST it
through `worker.crawler.safety.safe_post_json` (the same SSRF-safe
resolve-and-validate defense the enrichment crawler uses - a tenant-
admin-supplied webhook URL is exactly the kind of lower-trust input that
defense exists for), and record the result. Modeled on `worker.
enrichment_tasks.run_business_enrichment`'s two-phase-lookup, bounded-
retry, clean-failure shape.

A permanent, non-retryable outcome (the URL fails the SSRF check) is
distinguished from a transient one (timeout, connection refused, a 5xx
response) - see `_run_push_async`'s exception handling. Only the latter
is retried; a webhook URL that resolves to a private address will never
become safe to retry, so retrying it would just be repeated wasted work
(and repeated wasted attempts against whatever it actually points at).
"""

import json
import uuid
from datetime import UTC, datetime

from app.core.db import AsyncSessionLocal, set_platform_bypass, set_tenant_context
from app.core.logging import configure_logging, get_logger
from app.core.security import decrypt_credential, sign_payload
from app.modules.integrations import repositories as integrations_repo

from worker.async_utils import run_db_task
from worker.celery_app import celery_app
from worker.crawler.safety import FetchError, UnsafeUrlError, safe_post_json

logger = get_logger("gridkeep.worker.integrations")

MAX_RESPONSE_SNIPPET_LENGTH = 1000


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _run_push_async(delivery_id_str: str) -> None:
    delivery_id = uuid.UUID(delivery_id_str)

    async with AsyncSessionLocal() as session:
        # Same reasoning as worker.enrichment_tasks/worker.export_tasks
        # (ADR-0007): the tenant isn't known until this lookup finds it.
        await set_platform_bypass(session)
        delivery = await integrations_repo.get_delivery_or_raise(session, delivery_id)
        tenant_id = delivery.tenant_id

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        delivery = await integrations_repo.get_delivery_or_raise(session, delivery_id)
        if delivery.status != "pending":
            return  # duplicate delivery or already handled by another worker
        integration = await integrations_repo.get_integration_or_raise(
            session, delivery.integration_id
        )
        secret = decrypt_credential(integration.webhook_secret_encrypted)
        body_bytes = json.dumps(delivery.payload, separators=(",", ":")).encode("utf-8")
        signature = sign_payload(secret, body_bytes)

        response = await safe_post_json(
            integration.webhook_url,
            json_body=delivery.payload,
            headers={
                "Content-Type": "application/json",
                "X-Gridkeep-Signature": signature,
                "X-Gridkeep-Event": "lead.pushed",
            },
        )
        success = 200 <= response.status_code < 300
        # A non-2xx response is not yet terminal - retries may still
        # follow, so `status` stays "pending" here (the duplicate-
        # delivery guard above treats a non-"pending" delivery as already
        # handled; marking it "failed" prematurely would make every
        # subsequent retry silently no-op instead of actually retrying).
        # Only `_finalize_failed`, called once retries are exhausted or
        # the URL is permanently unsafe, sets the terminal "failed".
        await integrations_repo.mark_delivery_result(
            session,
            delivery,
            status="success" if success else "pending",
            http_status_code=response.status_code,
            response_snippet=response.text[:MAX_RESPONSE_SNIPPET_LENGTH],
            error_message=None if success else f"Non-2xx response: {response.status_code}",
            attempt_count=delivery.attempt_count + 1,
            delivered_at=_utcnow() if success else None,
        )
        await session.commit()
        if not success:
            raise FetchError(f"Webhook responded {response.status_code}")


async def _finalize_failed(delivery_id_str: str, message: str, *, attempt_count: int) -> None:
    delivery_id = uuid.UUID(delivery_id_str)
    async with AsyncSessionLocal() as session:
        await set_platform_bypass(session)
        delivery = await integrations_repo.get_delivery(session, delivery_id)
        if delivery is None:
            return
        await set_tenant_context(session, delivery.tenant_id)
        await integrations_repo.mark_delivery_result(
            session,
            delivery,
            status="failed",
            http_status_code=delivery.http_status_code,
            response_snippet=delivery.response_snippet,
            error_message=message[:2000],
            attempt_count=attempt_count,
            delivered_at=None,
        )
        await session.commit()


@celery_app.task(bind=True, name="worker.integration_tasks.push_lead_to_integration", max_retries=4)
def push_lead_to_integration(self, delivery_id: str) -> None:
    configure_logging()
    try:
        run_db_task(_run_push_async(delivery_id))
    except UnsafeUrlError as exc:
        # Permanent: this URL will never become safe to retry.
        logger.warning("integration_delivery_unsafe_url", delivery_id=delivery_id, error=str(exc))
        run_db_task(_finalize_failed(delivery_id, str(exc), attempt_count=self.request.retries + 1))
    except Exception as exc:  # noqa: BLE001 - genuinely broad: anything other than the
        # permanent UnsafeUrlError above (a timeout, a connection error, a non-2xx
        # response re-raised as FetchError, a database hiccup, a bug in the delivery
        # payload/decryption path) must still retry-then-cleanly-fail rather than
        # leave the delivery stuck "pending" forever with no error recorded - the
        # exact failure mode a too-narrow except clause produced here once already
        # (an unanticipated exception type escaped uncaught during live
        # verification, see docs/adr/0016).
        logger.warning(
            "integration_delivery_error",
            delivery_id=delivery_id,
            error=str(exc),
            attempt=self.request.retries,
        )
        # Check retries-exhausted *before* calling retry(), rather than
        # catching MaxRetriesExceededError afterwards: Celery's retry()
        # re-raises the original `exc` (not MaxRetriesExceededError) once
        # retries are exhausted whenever exc= is passed, so a try/except
        # MaxRetriesExceededError around this call never actually catches
        # anything - it's dead code that made this task die uncaught on
        # real retry exhaustion (see docs/adr/0016 for how this was found).
        if self.request.retries >= self.max_retries:
            run_db_task(
                _finalize_failed(delivery_id, str(exc), attempt_count=self.request.retries + 1)
            )
        else:
            raise self.retry(exc=exc, countdown=min(60, 5 * (2**self.request.retries))) from exc
