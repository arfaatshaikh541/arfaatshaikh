"""Per-tenant concurrency limiting for campaign task execution.

Independent of (and stricter than, in a shared-fleet sense) the
`max_concurrent_campaigns` entitlement checked at launch time: the
entitlement caps how many campaigns *this tenant's plan* allows to be
active at once; this Redis-backed slot pool caps how many campaign tasks
*any* tenant may have executing at the same instant across the whole
worker fleet, so one tenant's campaigns can never starve every other
tenant's tasks of worker capacity.

Implemented as a fixed pool of TTL'd slot keys per tenant rather than a
plain INCR/DECR counter: a counter leaks permanently if a worker process
is killed mid-task (no DECR ever runs), whereas a slot key's TTL expires
on its own, self-healing the pool even after a hard crash.
"""

from redis.asyncio import Redis

from app.core.rate_limit import get_redis

MAX_CONCURRENT_TASKS_PER_TENANT = 2
SLOT_TTL_SECONDS = 600  # self-heals a leaked slot after 10 minutes


def _slot_key(tenant_id: str, slot_index: int) -> str:
    return f"campaign_concurrency:{tenant_id}:slot:{slot_index}"


async def acquire_tenant_slot(
    tenant_id: str, task_id: str, *, redis: Redis | None = None
) -> int | None:
    """Attempts to claim one of this tenant's concurrency slots for
    `task_id`. Returns the claimed slot index, or None if all slots are
    currently held (caller should re-queue the task with a short delay)."""
    redis = redis or get_redis()
    for slot_index in range(MAX_CONCURRENT_TASKS_PER_TENANT):
        claimed = await redis.set(
            _slot_key(tenant_id, slot_index), task_id, nx=True, ex=SLOT_TTL_SECONDS
        )
        if claimed:
            return slot_index
    return None


async def release_tenant_slot(
    tenant_id: str, slot_index: int, task_id: str, *, redis: Redis | None = None
) -> None:
    redis = redis or get_redis()
    key = _slot_key(tenant_id, slot_index)
    held_by = await redis.get(key)
    if held_by == task_id:
        await redis.delete(key)
