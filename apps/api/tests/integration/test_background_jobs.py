"""The worker's jobs against a real migrated PostgreSQL database (WOI_TEST_DATABASE_URL, empty)."""
import json
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

TEST_DB = os.environ.get("WOI_TEST_DATABASE_URL")
pytestmark = [pytest.mark.skipif(not TEST_DB, reason="WOI_TEST_DATABASE_URL not set"), pytest.mark.asyncio(loop_scope="module")]
if TEST_DB:
    os.environ["WOI_DATABASE_URL"] = TEST_DB

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def db():
    from app.core.config import get_settings
    from app.db.session import Database
    database = Database(get_settings())
    yield database
    await database.dispose()


async def _user(session):
    from app.models.identity import User
    user = User(email=f"bg-{uuid.uuid4().hex[:10]}@example.org", password_hash="x", display_name="BG", password_changed_at=NOW)
    session.add(user)
    await session.flush()
    return user


async def _mail(session, kind="email_verification", age=timedelta(minutes=1), token="A" * 40):
    from app.models.identity import EmailOutbox
    row = EmailOutbox(kind=kind, recipient=f"{uuid.uuid4().hex[:8]}@example.org", template_id="verify-email-v1" if kind == "email_verification" else "password-reset-v1",
                      payload_json=json.dumps({"token": token}), available_at=NOW - age)
    session.add(row)
    await session.commit()
    return row.id


async def _fresh(session, row_id):
    from app.models.identity import EmailOutbox
    await session.rollback()
    return await session.get(EmailOutbox, row_id, populate_existing=True)


async def _clear_outbox(session):
    from sqlalchemy import delete
    from app.models.identity import EmailOutbox
    await session.execute(delete(EmailOutbox))
    await session.commit()


async def test_nothing_is_sent_and_nothing_is_lost_when_smtp_is_not_configured(db):
    from app.core.config import get_settings
    from app.services import background
    settings = get_settings().model_copy(update={"smtp_host": ""})
    async with db.session_factory() as s:
        await _clear_outbox(s)
        row_id = await _mail(s)
        result = await background.send_email_outbox(s, settings, now=NOW)
        assert result["status"] == "smtp_not_configured" and result["pending"] == 1 and result["sent"] == 0
        row = await _fresh(s, row_id)
        assert row.sent_at is None and row.failed_at is None and "A" * 40 in row.payload_json


async def test_delivery_marks_sent_removes_the_token_and_is_idempotent(db):
    from app.core.config import get_settings
    from app.services import background
    settings = get_settings().model_copy(update={"smtp_host": "mail.example"})
    outbox = []
    async with db.session_factory() as s:
        await _clear_outbox(s)
        ids = [await _mail(s), await _mail(s, kind="password_reset", token="B" * 40)]
        first = await background.send_email_outbox(s, settings, send=lambda to, subj, body: outbox.append((to, subj, body)), now=NOW)
        assert first == {"status": "ok", "sent": 2, "failed": 0, "expired": 0}
        assert any("A" * 40 in body for _, _, body in outbox) and any("B" * 40 in body for _, _, body in outbox)
        for row_id in ids:
            row = await _fresh(s, row_id)
            assert row.sent_at is not None and "A" * 40 not in row.payload_json and "B" * 40 not in row.payload_json
        again = await background.send_email_outbox(s, settings, send=lambda *a: outbox.append("DUPLICATE"), now=NOW)
        assert again["sent"] == 0 and "DUPLICATE" not in outbox


async def test_a_mail_outage_leaves_the_message_queued_and_raises_for_retry(db):
    from app.core.config import get_settings
    from app.services import background
    settings = get_settings().model_copy(update={"smtp_host": "mail.example"})

    def down(*_):
        raise background.TransientEmailError("down")
    async with db.session_factory() as s:
        await _clear_outbox(s)
        row_id = await _mail(s)
        with pytest.raises(background.TransientEmailError):
            await background.send_email_outbox(s, settings, send=down, now=NOW)
        row = await _fresh(s, row_id)
        assert row.sent_at is None and row.failed_at is None and "A" * 40 in row.payload_json


async def test_a_refused_message_is_failed_once_with_a_reason_and_no_token(db):
    from app.core.config import get_settings
    from app.services import background
    settings = get_settings().model_copy(update={"smtp_host": "mail.example"})

    def refuse(*_):
        raise background.PermanentEmailError("recipient refused by the mail server")
    async with db.session_factory() as s:
        await _clear_outbox(s)
        row_id = await _mail(s)
        result = await background.send_email_outbox(s, settings, send=refuse, now=NOW)
        assert result["failed"] == 1
        row = await _fresh(s, row_id)
        assert row.failed_at is not None and "refused" in row.failure_reason and "A" * 40 not in row.payload_json
        assert (await background.send_email_outbox(s, settings, send=refuse, now=NOW))["failed"] == 0


async def test_a_reset_mail_older_than_its_token_is_not_sent(db):
    from app.core.config import get_settings
    from app.services import background
    settings = get_settings().model_copy(update={"smtp_host": "mail.example", "password_reset_ttl_seconds": 1800})
    sent = []
    async with db.session_factory() as s:
        await _clear_outbox(s)
        row_id = await _mail(s, kind="password_reset", age=timedelta(hours=2))
        result = await background.send_email_outbox(s, settings, send=lambda *a: sent.append(a), now=NOW)
        assert result["expired"] == 1 and not sent
        assert (await _fresh(s, row_id)).failure_reason == "expired before delivery"


async def test_purge_removes_only_rows_past_retention_and_is_idempotent(db):
    from app.models.identity import EmailOutbox, EmailVerificationToken, Session
    from app.services import background
    async with db.session_factory() as s:
        await _clear_outbox(s)
        user = await _user(s)
        old, recent = NOW - timedelta(days=45), NOW - timedelta(days=2)
        for expires in (old, recent, NOW + timedelta(days=5)):
            s.add(Session(user_id=user.id, token_hash=uuid.uuid4().hex + uuid.uuid4().hex[:32], csrf_token_hash="c", expires_at=expires, last_seen_at=NOW))
        s.add(EmailVerificationToken(user_id=user.id, token_hash=uuid.uuid4().hex + uuid.uuid4().hex[:32], expires_at=old))
        s.add(EmailOutbox(kind="x", recipient="a@b.example", template_id="t", payload_json="{}", available_at=old, sent_at=old))
        s.add(EmailOutbox(kind="x", recipient="a@b.example", template_id="t", payload_json="{}", available_at=recent, sent_at=recent))
        await s.commit()
        first = await background.purge_expired(s, now=NOW)
        assert first["deleted"]["sessions"] == 1 and first["deleted"]["email_verification_tokens"] == 1 and first["deleted"]["email_outbox"] == 1
        second = await background.purge_expired(s, now=NOW)
        assert sum(second["deleted"].values()) == 0


async def test_data_validation_job_returns_its_findings_and_logs_one_audit_row(db):
    from sqlalchemy import func, select
    from app.models.content_contract import PlatformAuditEvent
    from app.services import background
    async with db.session_factory() as s:
        before = await s.scalar(select(func.count()).select_from(PlatformAuditEvent).where(PlatformAuditEvent.action == "system.data_validation"))
        result = await background.run_data_validation(s)
        assert result["status"] in ("ok", "failed") and result["checks"] >= 10 and isinstance(result["failed"], dict)
        after = await s.scalar(select(func.count()).select_from(PlatformAuditEvent).where(PlatformAuditEvent.action == "system.data_validation"))
        assert after == before + 1


# ---------------------------------------------------------------- Arabic review queue
async def test_arabic_review_workflow_requires_attestation_keeps_decisions_and_exports(db):
    import csv
    import io
    from sqlalchemy import delete
    from app.core.errors import ApplicationError
    from app.models.content_contract import ReviewItem
    from app.services import review_queue as rq
    async with db.session_factory() as s:
        await s.execute(delete(ReviewItem))
        await rq.sync_arabic(s)
        await s.commit()
        items = (await rq.list_items(s, "arabic_ui", "NEEDS_NATIVE_REVIEW", None, 1, page_size=3))["items"]
        assert items and all(i["payload"].get("context") and i["payload"].get("arabic") for i in items), "every item carries its context and Arabic text"
        reviewer = await _user(s)
        await s.commit()
        first = items[0]
        from uuid import UUID
        with pytest.raises(ApplicationError) as err:                       # no attestation -> refused, nothing recorded
            await rq.decide(s, UUID(first["id"]), "NATIVE_REVIEW_APPROVED", None, None, False, reviewer)
        assert err.value.code == "attestation_required"
        with pytest.raises(ApplicationError):                              # a change request needs content
            await rq.decide(s, UUID(first["id"]), "NATIVE_REVIEW_CHANGES_REQUESTED", None, None, True, reviewer)
        await rq.decide(s, UUID(first["id"]), "NATIVE_REVIEW_CHANGES_REQUESTED", "wording", "نص مقترح", True, reviewer)
        await s.commit()
        await rq.sync_arabic(s)                                            # a re-sync must not erase the decision or the suggestion
        await s.commit()
        again = (await rq.list_items(s, "arabic_ui", "NATIVE_REVIEW_CHANGES_REQUESTED", None, 1))["items"]
        assert len(again) == 1 and again[0]["payload"]["suggested_text"] == "نص مقترح" and again[0]["reviewed_by_name"] == "BG" and again[0]["reviewed_at"]
        rows = await rq.export_rows(s, "arabic_ui", None, None)
        assert len(rows) == 168 and {"key", "category", "context", "english_source", "arabic", "status", "reviewer", "reviewed_at"} <= set(rows[0])
        assert sum(1 for r in rows if r["status"] == "NATIVE_REVIEW_APPROVED") == 0, "nothing is approved unless a person approved it"
        assert next(r for r in rows if r["key"] == first["key"])["reviewer"] == "BG"
        buffer = io.StringIO()
        csv.DictWriter(buffer, fieldnames=list(rows[0])).writerows(rows)
        await s.execute(delete(ReviewItem))
        await s.commit()
