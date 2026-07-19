"""`run_business_enrichment` - the Celery task that drives one business's
website enrichment crawl end-to-end: crawl the business's website safely
(bounded, robots-respecting - see `worker.crawler`), run every detector
against every crawled page, and persist the result as `EnrichmentEvidence`
rows plus a summary `BusinessEnrichment` status.

Whole-crawl "missing X" signals (`missing_whatsapp`,
`missing_online_booking`, `missing_online_ordering`,
`missing_contact_method`) are computed here, not by any single detector in
`worker.crawler.detectors`, because they are claims about the *whole
crawl* (nothing found across every page actually checked), not about one
page - and because they must only ever be recorded when the site was
actually reachable and checked, never when the crawl itself failed (a site
that couldn't be reached gets `website_unavailable`, not five different
"missing" claims about content nobody ever saw).
"""

import uuid
from datetime import UTC, datetime

from app.core.db import AsyncSessionLocal, set_platform_bypass, set_tenant_context
from app.core.logging import configure_logging, get_logger
from app.modules.businesses import repositories as businesses_repo
from app.modules.enrichment import repositories as enrichment_repo

from worker.async_utils import run_db_task
from worker.celery_app import celery_app
from worker.crawler.detectors import Signal, run_all_detectors
from worker.crawler.fetcher import crawl_site
from worker.retry import default_backoff, retry_or_finalize

logger = get_logger("gridkeep.worker.enrichment")

# Detector types that, if found on ANY crawled page, mean the
# corresponding "missing_X" whole-crawl signal must NOT be recorded.
_PRESENCE_TO_ABSENCE_TYPE = {
    "whatsapp": "missing_whatsapp",
    "booking": "missing_online_booking",
    "ordering": "missing_online_ordering",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _finalize_failed(tenant_id: uuid.UUID, enrichment_id: uuid.UUID, message: str) -> None:
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        enrichment = await enrichment_repo.get_enrichment_or_raise(session, enrichment_id)
        enrichment.status = "failed"
        enrichment.completed_at = _utcnow()
        enrichment.error_message = message
        await session.commit()


async def _run_business_enrichment_async(enrichment_id_str: str) -> None:
    enrichment_id = uuid.UUID(enrichment_id_str)

    async with AsyncSessionLocal() as session:
        # Same reasoning as worker.campaign_tasks (see ADR-0007): the
        # tenant isn't known until this very lookup finds it, so the
        # bypass has to be in place before the first read, not after.
        await set_platform_bypass(session)
        enrichment = await enrichment_repo.get_enrichment_or_raise(session, enrichment_id)
        tenant_id = enrichment.tenant_id
        business_id = enrichment.business_id

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        enrichment = await enrichment_repo.get_enrichment_or_raise(session, enrichment_id)
        if enrichment.status != "pending":
            return  # duplicate delivery or already handled by another worker
        enrichment.status = "running"
        enrichment.started_at = _utcnow()
        business = await businesses_repo.get_business_or_raise(session, business_id)
        website = business.website
        await session.commit()

    if not website:
        await _finalize_failed(tenant_id, enrichment_id, "Business has no website to crawl.")
        return

    crawl_result = await crawl_site(website)
    now = _utcnow()

    per_page_signals: list[tuple[str, Signal]] = []
    for page in crawl_result.pages:
        for signal in run_all_detectors(page.response.text, current_year=now.year):
            per_page_signals.append((page.url, signal))

    found_types = {signal.detector_type for _url, signal in per_page_signals}

    whole_crawl_signals: list[tuple[str, Signal]] = []
    if not crawl_result.site_reachable:
        whole_crawl_signals.append((website, Signal("website_unavailable", {}, confidence=0.9)))
    else:
        if crawl_result.ssl_failure:
            whole_crawl_signals.append((website, Signal("ssl_failure", {}, confidence=0.9)))
        pages_checked = len(crawl_result.pages)
        for presence_type, absence_type in _PRESENCE_TO_ABSENCE_TYPE.items():
            if presence_type not in found_types:
                whole_crawl_signals.append(
                    (
                        website,
                        Signal(absence_type, {"pages_checked": pages_checked}, confidence=0.6),
                    )
                )
        if "contact_email" not in found_types and "phone" not in found_types:
            whole_crawl_signals.append(
                (
                    website,
                    Signal(
                        "missing_contact_method", {"pages_checked": pages_checked}, confidence=0.6
                    ),
                )
            )

    # The highest-confidence contact_email signal found (a mailto: link
    # scores higher than a plain-text regex match) becomes Business.email -
    # the *only* place this field is ever set (see app.modules.businesses,
    # ADR-0011). If none was found, the field is simply never touched.
    best_email: tuple[str, float, str] | None = None  # (email, confidence, source_url)
    for url, signal in per_page_signals:
        if signal.detector_type != "contact_email":
            continue
        email = signal.structured_result.get("email")
        if not email:
            continue
        if best_email is None or signal.confidence > best_email[1]:
            best_email = (email, signal.confidence, url)

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        enrichment = await enrichment_repo.get_enrichment_or_raise(session, enrichment_id)
        business = await businesses_repo.get_business_or_raise(session, business_id)

        for url, signal in per_page_signals + whole_crawl_signals:
            await enrichment_repo.record_evidence(
                session,
                tenant_id=tenant_id,
                business_id=business_id,
                enrichment_id=enrichment_id,
                detector_type=signal.detector_type,
                source_url=url,
                structured_result=signal.structured_result,
                confidence=signal.confidence,
                supporting_snippet=signal.supporting_snippet,
                collected_at=now,
            )

        if best_email is not None:
            email, confidence, source_url = best_email
            business.email = email
            provenance = dict(business.field_provenance)
            provenance["email"] = {
                "source": "enrichment",
                "source_record_id": None,
                "confidence": confidence,
                "collected_at": now.isoformat(),
                "source_url": source_url,
            }
            business.field_provenance = provenance

        enrichment.status = "completed"
        enrichment.completed_at = now
        enrichment.pages_crawled = len(crawl_result.pages)
        await session.commit()


@celery_app.task(bind=True, name="worker.enrichment_tasks.run_business_enrichment", max_retries=3)
def run_business_enrichment(self, enrichment_id: str) -> None:
    configure_logging()
    try:
        run_db_task(_run_business_enrichment_async(enrichment_id))
    except Exception as exc:  # noqa: BLE001 - genuinely broad: any unexpected
        # crawl/detector failure should fail the enrichment run cleanly
        # rather than leave it stuck "running" forever, while still
        # retrying a bounded number of times for transient issues.
        logger.warning(
            "business_enrichment_task_error",
            enrichment_id=enrichment_id,
            error=str(exc),
            attempt=self.request.retries,
        )
        error = exc  # `except ... as exc` unbinds exc when this block exits;
        # the lambda below is a deferred closure, so it must capture a
        # plain local name instead (see worker.retry's own docstring).
        if self.request.retries < self.max_retries:
            # About to actually retry (see docs/adr/0023, which found and
            # fixed the identical bug in worker.campaign_tasks first): the
            # crawl happens after `enrichment.status = "running"` was
            # already committed, and nothing resets it back afterwards.
            # The duplicate-delivery guard above (`if enrichment.status !=
            # "pending": return`) only ever proceeds from `pending`, so
            # without this, the real retried delivery would find the
            # enrichment still `running` and silently no-op instead of
            # ever re-attempting the crawl.
            run_db_task(_reset_enrichment_to_pending_for_retry(enrichment_id))
        retry_or_finalize(
            self,
            exc=exc,
            finalize=lambda: _finalize_failed_after_error(enrichment_id, str(error)),
            countdown=default_backoff(self.request.retries),
            task_name="run_business_enrichment",
            task_id=enrichment_id,
        )


async def _reset_enrichment_to_pending_for_retry(enrichment_id_str: str) -> None:
    enrichment_id = uuid.UUID(enrichment_id_str)
    async with AsyncSessionLocal() as session:
        await set_platform_bypass(session)
        enrichment = await enrichment_repo.get_enrichment(session, enrichment_id)
        if enrichment is None:
            return
        await set_tenant_context(session, enrichment.tenant_id)
        if enrichment.status == "running":
            enrichment.status = "pending"
        await session.commit()


async def _finalize_failed_after_error(enrichment_id_str: str, message: str) -> None:
    enrichment_id = uuid.UUID(enrichment_id_str)
    async with AsyncSessionLocal() as session:
        await set_platform_bypass(session)
        enrichment = await enrichment_repo.get_enrichment(session, enrichment_id)
        if enrichment is None:
            return
        await set_tenant_context(session, enrichment.tenant_id)
        enrichment.status = "failed"
        enrichment.completed_at = _utcnow()
        enrichment.error_message = message
        await session.commit()
