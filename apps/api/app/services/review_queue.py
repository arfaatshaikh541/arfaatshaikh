"""Human review queues: what the platform flags, and what a person decided about it.

A decision is recorded with who made it and when. It never edits the reviewed data (no rename, delete, merge or rewrite): the data stays as
it was imported, and the queue says honestly whether anyone has looked. Native Arabic approval is an attestation by the reviewer; the
platform cannot verify anyone's language ability and does not claim to.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.models.content_contract import REVIEW_STATUSES, PlatformAuditEvent, ReviewItem
from app.models.identity import User
from app.services.data_quality import dataset_conflicts
from app.services.manifest import manifest_path

ARABIC_QUEUE = "arabic_ui"
MOSQUE_QUEUES = {"mosque_name_anomaly": "non_mosque_names", "mosque_colocated": "co_located_different", "mosque_near_identical": "similar_names",
                 "mosque_duplicate_candidate": "duplicate_candidates"}
QUEUES = (ARABIC_QUEUE, *MOSQUE_QUEUES)
ARABIC_GROUPS = ("GENERAL_UI", "QURAN", "HADITH", "FIQH", "AQEEDAH", "TAFSIR", "SCHOLARSHIP", "DIRECTORY")
DECISIONS = {
    ARABIC_QUEUE: {"NEEDS_NATIVE_REVIEW", "NATIVE_REVIEW_APPROVED", "NATIVE_REVIEW_CHANGES_REQUESTED"},
    **{q: {"OPEN", "KEEP_AS_IS", "NEEDS_SOURCE_CHECK", "CONFIRMED_DUPLICATE"} for q in MOSQUE_QUEUES},
}
assert all(status in REVIEW_STATUSES for statuses in DECISIONS.values() for status in statuses)


def arabic_seed_path():
    return manifest_path().with_name("arabic-strings.json")


def _upsert(rows: list[dict]):
    stmt = insert(ReviewItem).values(rows)
    # an existing row keeps its status, note and reviewer: only the flagged payload may be refreshed
    return stmt.on_conflict_do_update(constraint="uq_review_items_queue_key", set_={"payload": stmt.excluded.payload, "group_name": stmt.excluded.group_name, "updated_at": func.now()})


async def sync_arabic(db: AsyncSession) -> dict:
    seed = json.loads(arabic_seed_path().read_text(encoding="utf-8"))["strings"]
    rows = [{"queue": ARABIC_QUEUE, "item_key": s["key"], "group_name": s["group"], "status": "NEEDS_NATIVE_REVIEW",
             "payload": {"arabic": s["arabic"], "english": s.get("english"), "file": s["file"], "religious_term": s["religious_term"]}} for s in seed]
    before = await db.scalar(select(func.count()).select_from(ReviewItem).where(ReviewItem.queue == ARABIC_QUEUE))
    for i in range(0, len(rows), 200):
        await db.execute(_upsert(rows[i:i + 200]))
    after = await db.scalar(select(func.count()).select_from(ReviewItem).where(ReviewItem.queue == ARABIC_QUEUE))
    return {"queue": ARABIC_QUEUE, "flagged": len(rows), "added": after - before}


def _pair_key(item: dict) -> str:
    if "a" in item:
        a, b = sorted([str(item.get("a_key") or item["a"]), str(item.get("b_key") or item["b"])])
        return f"{a}|{b}"
    return str(item.get("key") or item["id"])


async def sync_mosques(db: AsyncSession, dataset_key: str = "directory-mosques") -> dict:
    """Queue every flag the conflict scan raises, keyed by the source ids (stable across re-imports), never by row id."""
    found = await dataset_conflicts(db, dataset_key, limit=100000)
    added: dict[str, int] = {}
    for queue, kind in MOSQUE_QUEUES.items():
        items = found["items"].get(kind, [])
        rows = [{"queue": queue, "item_key": _pair_key(i)[:300], "group_name": None, "status": "OPEN", "payload": {**{k: v for k, v in i.items()}, "dataset": dataset_key}} for i in items]
        before = await db.scalar(select(func.count()).select_from(ReviewItem).where(ReviewItem.queue == queue))
        for start in range(0, len(rows), 200):
            await db.execute(_upsert(rows[start:start + 200]))
        after = await db.scalar(select(func.count()).select_from(ReviewItem).where(ReviewItem.queue == queue))
        added[queue] = after - before
    return {"dataset": dataset_key, "flagged": {q: len(found["items"].get(k, [])) for q, k in MOSQUE_QUEUES.items()}, "added": added,
            "note": "Flagged for review only. No listing was renamed, merged, hidden or deleted."}


async def summary(db: AsyncSession) -> dict:
    rows = (await db.execute(select(ReviewItem.queue, ReviewItem.status, func.count()).group_by(ReviewItem.queue, ReviewItem.status))).all()
    out: dict[str, dict[str, int]] = {q: {} for q in QUEUES}
    for queue, status, total in rows:
        out.setdefault(queue, {})[status] = int(total)
    return {"queues": out, "statuses": list(REVIEW_STATUSES)}


async def list_items(db: AsyncSession, queue: str, status: str | None, group: str | None, page: int, page_size: int = 50) -> dict:
    if queue not in QUEUES:
        raise ApplicationError("unknown_queue", "Unknown review queue.", 404)
    stmt = select(ReviewItem).where(ReviewItem.queue == queue)
    if status:
        stmt = stmt.where(ReviewItem.status == status)
    if group:
        stmt = stmt.where(ReviewItem.group_name == group)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.scalars(stmt.order_by(ReviewItem.group_name, ReviewItem.item_key).limit(page_size).offset((page - 1) * page_size))).all()
    by_group = Counter(r.group_name for r in rows)
    return {"queue": queue, "total": int(total or 0), "page": page, "by_group_on_page": dict(by_group),
            "items": [{"id": str(r.id), "key": r.item_key, "group": r.group_name, "status": r.status, "note": r.note, "payload": r.payload,
                       "reviewed_by": str(r.reviewed_by_user_id) if r.reviewed_by_user_id else None, "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None} for r in rows]}


async def decide(db: AsyncSession, item_id: UUID, status: str, note: str | None, suggested_text: str | None, attest_native_reader: bool, actor: User) -> ReviewItem:
    item = await db.get(ReviewItem, item_id)
    if item is None:
        raise ApplicationError("review_item_not_found", "Review item not found.", 404)
    if status not in DECISIONS.get(item.queue, set()):
        raise ApplicationError("invalid_review_status", f"Status must be one of: {', '.join(sorted(DECISIONS.get(item.queue, set())))}.", 422)
    if status == "NATIVE_REVIEW_APPROVED" and not attest_native_reader:
        raise ApplicationError("attestation_required", "Approving Arabic text needs the reviewer to attest they read Arabic natively and reviewed this string.", 422)
    if status == "NATIVE_REVIEW_CHANGES_REQUESTED" and not (suggested_text or note):
        raise ApplicationError("change_needs_detail", "Say what should change (suggested text or a note).", 422)
    item.status, item.note = status, (note or None)
    if suggested_text:
        item.payload = {**item.payload, "suggested_text": suggested_text}  # recorded, never applied automatically
    item.reviewed_by_user_id = actor.id if status not in {"OPEN", "NEEDS_NATIVE_REVIEW"} else None
    item.reviewed_at = datetime.now(UTC) if item.reviewed_by_user_id else None
    db.add(PlatformAuditEvent(actor_user_id=actor.id, action="review.decide", target_type="review_item", target_id=item.id,
                              metadata_json={"queue": item.queue, "key": item.item_key, "status": status, "attested_native_reader": attest_native_reader}))
    await db.flush()
    return item
