"""LinkedIn connector: a concrete, real vendor configuration of the
generic RestApiConnector, closing the "LinkedIn" row's code gap named in
FINAL_COMPLETION_AUDIT.md's section G. LinkedIn's current public API
surface for a personal/company page is narrow -- general posting APIs
beyond the UGC Posts endpoint need LinkedIn Partner Program approval.
This covers what's legitimately available without that: reading the
authenticated member's profile and sharing a UGC post.

REQUIRES_OWNER_CREDENTIAL: a real OAuth2 access token from a LinkedIn
app the owner has registered and authorized. Until configured,
health_check() honestly reports READY_TO_CONNECT. Getting that token
needs a live OAuth consent flow in a real browser
(REQUIRES_OWNER_AUTHORIZATION); anything beyond `ugcPosts`/`me` is
REQUIRES_PLATFORM_APPROVAL (LinkedIn Partner Program review).

Known limitation, same shape as the GitHub connector's: RestApiConnector
only ever sets one static header (Authorization). LinkedIn's API
recommends `X-Restli-Protocol-Version: 2.0.0` and
`LinkedIn-Version: <date>` on requests; without a RestApiConnector
enhancement for multiple static headers, this relies on LinkedIn's
default/legacy behavior rather than sending those explicitly.
"""
from __future__ import annotations

from .rest_connector import RestApiConnector, RestCapability

LINKEDIN_CAPABILITY_MAP: dict[str, RestCapability] = {
    "linkedin.get_profile": RestCapability("GET", "/me"),
    # Pass params={"body": {"author": "urn:li:person:...", "lifecycleState": "PUBLISHED", ...}}
    # -- the full UGC Posts JSON shape LinkedIn's API documents.
    "linkedin.share_post": RestCapability("POST", "/ugcPosts"),
}


def build_linkedin_connector(token: str | None = None, base_url: str = "https://api.linkedin.com/v2") -> RestApiConnector:
    """base_url is overridable so this can be pointed at a real local
    fake server in tests, exactly the way every other connector in this
    project is verified against something real rather than mocked."""
    return RestApiConnector(
        name="linkedin", base_url=base_url, capability_map=LINKEDIN_CAPABILITY_MAP,
        api_key=token, header_name="Authorization", health_path="/me", auth_method="api_key",
    )
