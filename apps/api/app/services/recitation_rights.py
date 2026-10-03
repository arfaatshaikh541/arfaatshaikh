"""How a recitation may be delivered, decided only from the rights recorded for it.

STREAMED_EXTERNALLY       we link to / play from the rights holder's own host; nothing is copied.
HOSTED_WITH_PERMISSION    we host checksummed files because redistribution is authorised in writing.
OFFLINE_WITH_PERMISSION   hosted, and the holder also allows download and offline caching.
NOT_PLAYABLE              not enough recorded to publish anything. A recording is never copied "because it can be downloaded".
"""
from __future__ import annotations

from typing import Protocol

from app.services.data_contracts import PUBLISHABLE_LICENCE_STATUSES

STREAMED_EXTERNALLY = "STREAMED_EXTERNALLY"
HOSTED_WITH_PERMISSION = "HOSTED_WITH_PERMISSION"
OFFLINE_WITH_PERMISSION = "OFFLINE_WITH_PERMISSION"
NOT_PLAYABLE = "NOT_PLAYABLE"
DELIVERY_CLASSES = (STREAMED_EXTERNALLY, HOSTED_WITH_PERMISSION, OFFLINE_WITH_PERMISSION, NOT_PLAYABLE)


class RecitationRights(Protocol):
    delivery_mode: str
    license_status: str
    rights_authorization: str | None
    source_url: str | None
    recording_owner: str | None
    streaming_allowed: bool
    download_allowed: bool
    redistribution_allowed: bool
    caching_allowed: bool
    offline_allowed: bool


def rights_problems(r: RecitationRights) -> list[str]:
    """What is missing before this recitation may be published in the mode it asks for. Empty means nothing is missing."""
    problems: list[str] = []
    if not (r.recording_owner or "").strip():
        problems.append("recording_owner (who owns the recording) is not recorded")
    if not r.streaming_allowed:
        problems.append("streaming rights are not recorded as granted")
    if r.delivery_mode == "external_link":
        if not r.source_url:
            problems.append("an external-link recitation needs the rights holder's page (source_url)")
        if r.offline_allowed or r.caching_allowed or r.redistribution_allowed:
            problems.append("an external-link recitation cannot be cached, taken offline or redistributed; host it only with permission")
        return problems
    if r.license_status not in PUBLISHABLE_LICENCE_STATUSES:
        problems.append(f"licence status {r.license_status} does not permit hosting")
    if not (r.rights_authorization or "").strip():
        problems.append("hosting needs a recorded authorisation (who, when, on what basis)")
    if not r.redistribution_allowed:
        problems.append("redistribution rights are not recorded as granted")
    if r.offline_allowed and not (r.download_allowed and r.caching_allowed):
        problems.append("offline use needs download and caching rights")
    return problems


def delivery_class(r: RecitationRights) -> str:
    if rights_problems(r):
        return NOT_PLAYABLE
    if r.delivery_mode == "external_link":
        return STREAMED_EXTERNALLY
    return OFFLINE_WITH_PERMISSION if r.offline_allowed else HOSTED_WITH_PERMISSION
