import logging
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.core.db import session_scope, set_rls_context
from app.modules.entitlements.service import cleanup_expired_overrides
from app.modules.identity.repository import InvitationRepository, SessionRepository

logger = logging.getLogger("worker.cleanup")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(name="app.tasks.cleanup.cleanup_expired_sessions", autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def cleanup_expired_sessions() -> int:
    """Deletes session rows past their absolute expiry. Idempotent: a
    session already deleted by a prior (possibly retried) run simply
    won't appear in the next query."""
    with session_scope() as db:
        set_rls_context(db, tenant_id=None, is_platform_admin=True)
        repo = SessionRepository(db)
        expired = repo.list_expired(before=_utcnow())
        for session in expired:
            repo.delete(session)
        count = len(expired)
    logger.info("Deleted %d expired sessions", count)
    return count


@celery_app.task(name="app.tasks.cleanup.cleanup_expired_invitations", autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def cleanup_expired_invitations() -> int:
    """Marks unaccepted, expired invitations as revoked so they can no
    longer be accepted and stop showing as "pending" in tenant admin UI.
    Idempotent: only rows still matching (accepted_at IS NULL, revoked_at
    IS NULL, expired) are touched on each run."""
    with session_scope() as db:
        set_rls_context(db, tenant_id=None, is_platform_admin=True)
        repo = InvitationRepository(db)
        expired = repo.list_expired_unaccepted(before=_utcnow())
        for invitation in expired:
            invitation.revoked_at = _utcnow()
        count = len(expired)
    logger.info("Revoked %d expired invitations", count)
    return count


@celery_app.task(name="app.tasks.cleanup.cleanup_expired_feature_overrides", autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def cleanup_expired_feature_overrides() -> int:
    with session_scope() as db:
        set_rls_context(db, tenant_id=None, is_platform_admin=True)
        count = cleanup_expired_overrides(db)
    logger.info("Deleted %d expired feature overrides", count)
    return count
