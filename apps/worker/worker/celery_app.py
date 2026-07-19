"""Celery application entry point.

The worker imports and runs the exact same domain services as the API
(`app.modules.*`) rather than re-implementing business logic - `gridkeep-
worker` depends on `gridkeep-api` as a uv workspace member so both
processes share one source of truth.

Milestone 1 shipped `expire_stale_reservations` (credit-ledger
maintenance). Milestone 2 added `run_campaign_task` (campaign page
fan-out) on `queue.search`. Milestone 4 adds `run_business_enrichment`
(website crawl + detectors) on its own `queue.enrichment` - kept separate
from `queue.search` so a backlog of enrichment crawls (which are much
slower than a mock/API-based search page) never starves campaign
processing, and vice versa. Milestone 7 adds `run_export` (XLSX/CSV
generation + object storage upload) on its own `queue.export`, same
isolation reasoning - a large export shouldn't starve campaign or
enrichment throughput. Milestone 8 adds `push_lead_to_integration`
(outbound webhook delivery) on its own `queue.crm_push` (declared since
Milestone 2, unconsumed until now), and `run_csv_import` on `queue.search`
- CSV import shares campaign discovery's queue deliberately, since it is
the same class of work (turning raw external data into `Business` rows
via the same upsert/dedup pipeline `run_campaign_task` already uses), not
a new source of isolation pressure that would justify its own queue.
"""

# Must be imported before any ORM operation runs in this process: it pulls
# in every model module so SQLAlchemy's mapper configuration step can
# resolve cross-module string FK targets (e.g. Campaign.tenant_id's
# ForeignKey("tenants.id")) - without it, only whatever models the task
# modules happen to import directly are registered, and any FK pointing
# at a table outside that set fails with NoReferencedTableError the first
# time a query touches it (this bit us for real - see the Milestone 2
# session transcript).
from app.core import model_registry  # noqa: F401,E402
from app.core.config import get_settings
from celery import Celery

settings = get_settings()

celery_app = Celery(
    "gridkeep",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "worker.tasks",
        "worker.campaign_tasks",
        "worker.enrichment_tasks",
        "worker.export_tasks",
        "worker.integration_tasks",
        "worker.csv_import_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="queue.maintenance",
    task_routes={
        "worker.tasks.expire_stale_reservations": {"queue": "queue.maintenance"},
        "worker.campaign_tasks.run_campaign_task": {"queue": "queue.search"},
        "worker.enrichment_tasks.run_business_enrichment": {"queue": "queue.enrichment"},
        "worker.export_tasks.run_export": {"queue": "queue.export"},
        "worker.integration_tasks.push_lead_to_integration": {"queue": "queue.crm_push"},
        "worker.csv_import_tasks.run_csv_import": {"queue": "queue.search"},
    },
)

from worker import beat_schedule  # noqa: E402

celery_app.conf.beat_schedule = beat_schedule.BEAT_SCHEDULE
