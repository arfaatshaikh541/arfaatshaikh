"""CampaignStateMachine: the single writer of Campaign.status.

Every transition is validated against `LEGAL_TRANSITIONS` and recorded as
a `CampaignEvent` - no service or worker task ever assigns
`campaign.status = ...` directly outside of this module.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ResourceNotFoundError
from app.modules.campaigns import repositories as repo
from app.modules.campaigns.models import Campaign

LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"estimating"},
    "estimating": {"ready", "draft"},
    "ready": {"queued"},
    "queued": {"running", "cancelling"},
    "running": {"pausing", "cancelling", "completed", "partially_completed", "failed"},
    "pausing": {"paused"},
    "paused": {"queued", "cancelling"},
    "cancelling": {"cancelled"},
    "cancelled": set(),
    "completed": set(),
    "partially_completed": set(),
    "failed": set(),
}


async def transition(
    session: AsyncSession,
    campaign: Campaign,
    *,
    to_status: str,
    message: str | None = None,
    metadata: dict | None = None,
) -> Campaign:
    from_status = campaign.status
    allowed = LEGAL_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise ConflictError(f"Cannot transition campaign from '{from_status}' to '{to_status}'.")
    campaign.status = to_status
    await repo.record_event(
        session,
        tenant_id=campaign.tenant_id,
        campaign_id=campaign.id,
        event_type="status_changed",
        from_status=from_status,
        to_status=to_status,
        message=message,
        metadata=metadata,
    )
    return campaign


def is_terminal(status: str) -> bool:
    return len(LEGAL_TRANSITIONS.get(status, set())) == 0


async def get_campaign_or_raise(session: AsyncSession, campaign_id: uuid.UUID) -> Campaign:
    campaign = await repo.get_campaign(session, campaign_id)
    if campaign is None:
        raise ResourceNotFoundError("Campaign not found.")
    return campaign
