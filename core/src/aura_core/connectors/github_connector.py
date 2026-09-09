"""GitHub connector: a concrete, real vendor configuration of the
generic RestApiConnector -- closing the gap FINAL_COMPLETION_AUDIT.md
called out specifically: "a generic REST connector exists" is not the
same claim as "a real integration exists," and this repository's own
work in this session used GitHub through the harness's own MCP tools,
never through AURA's own governed Action-Broker pipeline.

Covers what section 12 (Git / software workflow) asks for: listing and
reading pull requests and issues, commenting on either, and reading a
commit's combined build/check status -- all real GitHub REST API v3
paths, not guessed ones.

REQUIRES_OWNER_CREDENTIAL: a real personal access token (or GitHub App
installation token) with appropriate repo scope. Until one is
configured, health_check() honestly reports READY_TO_CONNECT rather
than assuming success from configuration alone -- see RestApiConnector,
which this only configures, not replaces.

Known limitation: RestApiConnector only ever sets one custom header
(Authorization). GitHub's REST API works without the recommended
`Accept: application/vnd.github+json` / `X-GitHub-Api-Version` headers
for these endpoints today, but a future RestApiConnector enhancement to
support multiple static headers would make that explicit rather than
relying on GitHub's default behavior.
"""
from __future__ import annotations

from .rest_connector import RestApiConnector, RestCapability

GITHUB_CAPABILITY_MAP: dict[str, RestCapability] = {
    "github.list_pull_requests": RestCapability("GET", "/repos/{owner}/{repo}/pulls"),
    "github.get_pull_request": RestCapability("GET", "/repos/{owner}/{repo}/pulls/{number}"),
    "github.list_issues": RestCapability("GET", "/repos/{owner}/{repo}/issues"),
    "github.get_issue": RestCapability("GET", "/repos/{owner}/{repo}/issues/{number}"),
    # GitHub's comment-creation endpoint is shared by issues and pull
    # requests (a PR is an issue for commenting purposes). Pass
    # params={"owner":..., "repo":..., "number":..., "body": {"body": "text"}}
    # -- RestApiConnector's handler sends params["body"] as the JSON
    # payload verbatim, and this endpoint expects {"body": "<text>"}.
    "github.comment_on_issue": RestCapability("POST", "/repos/{owner}/{repo}/issues/{number}/comments"),
    "github.get_combined_status": RestCapability("GET", "/repos/{owner}/{repo}/commits/{ref}/status"),
}


def build_github_connector(token: str | None = None, base_url: str = "https://api.github.com") -> RestApiConnector:
    """base_url is overridable so this can be pointed at a real local
    fake server in tests, exactly the way every other connector in this
    project is verified against something real rather than mocked."""
    return RestApiConnector(
        name="github", base_url=base_url, capability_map=GITHUB_CAPABILITY_MAP,
        api_key=token, header_name="Authorization", health_path="/", auth_method="api_key",
    )
