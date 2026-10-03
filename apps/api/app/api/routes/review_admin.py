"""Administrator review queues: Arabic UI strings awaiting a native reader, and mosque records the data-quality scan flagged."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.dependencies.auth import DbSession, require_csrf
from app.api.dependencies.platform_admin import require_platform_administrator
from app.core.errors import ApplicationError
from app.models.identity import Session, User
from app.services import review_queue as rq

router = APIRouter(prefix="/admin/review", tags=["admin-review"])
Admin = Annotated[User, Depends(require_platform_administrator)]
Csrf = Annotated[Session, Depends(require_csrf)]


class DecisionPayload(BaseModel):
    status: str = Field(max_length=32)
    note: str | None = Field(default=None, max_length=1000)
    suggested_text: str | None = Field(default=None, max_length=2000)
    attest_native_reader: bool = False


@router.get("")
async def queues(db: DbSession, _: Admin):
    return {**(await rq.summary(db)), "arabic_groups": list(rq.ARABIC_GROUPS),
            "notice": "A queue records what a person decided. It never changes the reviewed data, and no Arabic string counts as reviewed until a reader approves it here."}


@router.post("/sync/{queue}")
async def sync(queue: str, db: DbSession, admin: Admin, _: Csrf):
    if queue == rq.ARABIC_QUEUE:
        result = await rq.sync_arabic(db)
    elif queue == "mosques":
        result = await rq.sync_mosques(db)
    else:
        raise ApplicationError("unknown_queue", "Sync 'arabic_ui' or 'mosques'.", 404)
    await db.commit()
    return result


@router.get("/{queue}/export.csv")
async def export_csv(queue: str, db: DbSession, _: Admin, status: Annotated[str | None, Query(max_length=32)] = None, group: Annotated[str | None, Query(max_length=40)] = None):
    rows = await rq.export_rows(db, queue, status, group)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]) if rows else ["key"], quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows([{k: (("'" + v) if isinstance(v, str) and v[:1] in "=+-@\t\r" and v else v) for k, v in row.items()} for row in rows])  # no spreadsheet formula injection
    return Response("\ufeff" + buffer.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="review-{queue}.csv"'})


@router.get("/{queue}")
async def items(queue: str, db: DbSession, _: Admin, status: Annotated[str | None, Query(max_length=32)] = None, group: Annotated[str | None, Query(max_length=40)] = None,
                page: Annotated[int, Query(ge=1, le=100000)] = 1):
    return await rq.list_items(db, queue, status, group, page)


@router.post("/items/{item_id}/decide")
async def decide(item_id: UUID, payload: DecisionPayload, db: DbSession, admin: Admin, _: Csrf):
    item = await rq.decide(db, item_id, payload.status, payload.note, payload.suggested_text, payload.attest_native_reader, admin)
    await db.commit()
    return {"id": str(item.id), "queue": item.queue, "status": item.status}
