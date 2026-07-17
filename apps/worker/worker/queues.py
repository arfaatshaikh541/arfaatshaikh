"""Named Celery queues.

Fixing these names now means Milestone 2's campaign orchestration routes
tasks onto a scheme that already exists, instead of retrofitting one.
Only QUEUE_MAINTENANCE is consumed in Milestone 1 - the others are
declared, not yet routed to, and will be wired up as each owning
milestone implements its tasks.
"""

QUEUE_MAINTENANCE = "queue.maintenance"  # Milestone 1: credit reservation expiry, etc.
QUEUE_SEARCH = "queue.search"  # Milestone 2/3: connector search tasks
QUEUE_ENRICHMENT = "queue.enrichment"  # Milestone 4: website enrichment
QUEUE_DEDUP = "queue.dedup"  # Milestone 5: deduplication
QUEUE_SCORING = "queue.scoring"  # Milestone 5: lead scoring
QUEUE_EXPORT = "queue.export"  # Milestone 7: export generation
QUEUE_CRM_PUSH = "queue.crm_push"  # Milestone 8: CRM delivery
QUEUE_DEAD_LETTER = "queue.dead_letter"  # cross-cutting: exhausted-retry tasks
