"""Meta (Facebook Page) connector: a concrete, real vendor configuration
of the generic RestApiConnector, closing the "Meta/Instagram" row's code
gap named in FINAL_COMPLETION_AUDIT.md's section G. Covers real Meta
Graph API v19 paths for Facebook Page-level publishing/reading: listing
a page's posts, reading a post's comments, publishing to a page's feed,
and replying to a comment.

Scoped to Facebook Page operations, not Instagram's own publish flow,
which is a genuinely different (two-step: create a media container, then
publish it) API shape -- building that honestly needs its own capability
map and handler sequencing, not something RestApiConnector's
single-request-per-action_type model covers as a drop-in configuration,
and is called out as remaining work rather than silently folded into
this connector's name.

REQUIRES_OWNER_CREDENTIAL: a real Page access token (from a Meta app the
owner has set up and had authorized). Until one is configured,
health_check() honestly reports READY_TO_CONNECT. Getting that token in
the first place needs a live OAuth consent flow in a real browser --
REQUIRES_OWNER_AUTHORIZATION -- and, for most permissions a real
business integration needs, Meta App Review -- REQUIRES_PLATFORM_APPROVAL.
Neither is something this connector can honestly claim to provide;
it provides the governed, tested Action-Broker pipeline for using a
token once the owner has one.
"""
from __future__ import annotations

from .rest_connector import RestApiConnector, RestCapability

META_CAPABILITY_MAP: dict[str, RestCapability] = {
    "meta.get_page_posts": RestCapability("GET", "/{page_id}/posts"),
    "meta.get_post_comments": RestCapability("GET", "/{post_id}/comments"),
    # Graph API accepts a JSON body for these write endpoints; pass
    # params={"page_id":..., "body": {"message": "text"}}.
    "meta.publish_post": RestCapability("POST", "/{page_id}/feed"),
    "meta.reply_to_comment": RestCapability("POST", "/{comment_id}/comments"),
}


def build_meta_connector(token: str | None = None, base_url: str = "https://graph.facebook.com/v19.0") -> RestApiConnector:
    """base_url is overridable so this can be pointed at a real local
    fake server in tests, exactly the way every other connector in this
    project is verified against something real rather than mocked."""
    return RestApiConnector(
        name="meta", base_url=base_url, capability_map=META_CAPABILITY_MAP,
        api_key=token, header_name="Authorization", health_path="/me", auth_method="api_key",
    )
