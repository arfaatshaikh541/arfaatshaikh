"""World Model observation: turns real action outcomes into Entities and
Relationships, so WorldModelStore actually gets populated by the system's
own activity instead of sitting empty except for direct, manually-called
upsert_entity()/link() calls -- the exact gap this codebase's own audit
flagged ("nothing populates it from observation").

Deliberately narrow and explicit: each action_type that can produce a
useful observation has its own small extractor function registered
below, rather than one clever generic JSON-to-entity mapper. A JSON blob
has no inherent schema for "what's an entity here" -- guessing wrong
would silently pollute the World Model with garbage, which is worse than
not observing at all.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable

from ..memory.world_model import WorldModelStore

Extractor = Callable[[WorldModelStore, dict, dict, str], None]

_EXTRACTORS: dict[str, Extractor] = {}


def register_extractor(action_type: str, extractor: Extractor) -> None:
    _EXTRACTORS[action_type] = extractor


def observe(world_model: WorldModelStore, action_type: str, params: dict, raw_message: str, source: str) -> None:
    """Called after a successful action execution. Never raises -- a
    malformed or unexpected payload for a registered action_type is
    skipped, not a reason to fail the task that already succeeded."""
    extractor = _EXTRACTORS.get(action_type)
    if extractor is None:
        return
    try:
        payload = json.loads(raw_message)
    except (TypeError, ValueError):
        return
    try:
        extractor(world_model, params, payload, source)
    except (KeyError, TypeError, AttributeError):
        return


def _repo_key(params: dict) -> str:
    return f"{params.get('owner', '?')}/{params.get('repo', '?')}"


def _upsert_github_pull_request(world_model: WorldModelStore, params: dict, pr: dict, source: str) -> None:
    number = pr.get("number")
    if number is None:
        return
    repo = _repo_key(params)
    entity_id = f"github:{repo}#pr{number}"
    entity = world_model.upsert_entity(
        entity_id=entity_id, entity_type="github_pull_request",
        name=f"{repo} PR #{number}: {pr.get('title', '')}", source=source,
        attributes={"number": number, "title": pr.get("title"), "state": pr.get("state"), "repo": repo},
    )
    author = (pr.get("user") or {}).get("login")
    if author:
        author_id = f"github:user:{author}"
        world_model.upsert_entity(entity_id=author_id, entity_type="person", name=author, source=source)
        world_model.link(subject_id=author_id, predicate="authored", object_id=entity.id, source=source)


def _observe_github_pull_requests_list(world_model: WorldModelStore, params: dict, payload, source: str) -> None:
    if not isinstance(payload, list):
        return
    for pr in payload:
        _upsert_github_pull_request(world_model, params, pr, source)


def _observe_github_pull_request(world_model: WorldModelStore, params: dict, payload, source: str) -> None:
    if isinstance(payload, dict):
        _upsert_github_pull_request(world_model, params, payload, source)


def _upsert_github_issue(world_model: WorldModelStore, params: dict, issue: dict, source: str) -> None:
    number = issue.get("number")
    if number is None:
        return
    repo = _repo_key(params)
    entity_id = f"github:{repo}#issue{number}"
    entity = world_model.upsert_entity(
        entity_id=entity_id, entity_type="github_issue",
        name=f"{repo} issue #{number}: {issue.get('title', '')}", source=source,
        attributes={"number": number, "title": issue.get("title"), "state": issue.get("state"), "repo": repo},
    )
    author = (issue.get("user") or {}).get("login")
    if author:
        author_id = f"github:user:{author}"
        world_model.upsert_entity(entity_id=author_id, entity_type="person", name=author, source=source)
        world_model.link(subject_id=author_id, predicate="reported", object_id=entity.id, source=source)


def _observe_github_issues_list(world_model: WorldModelStore, params: dict, payload, source: str) -> None:
    if not isinstance(payload, list):
        return
    for issue in payload:
        _upsert_github_issue(world_model, params, issue, source)


def _observe_github_issue(world_model: WorldModelStore, params: dict, payload, source: str) -> None:
    if isinstance(payload, dict):
        _upsert_github_issue(world_model, params, payload, source)


_EMAIL_ADDRESS_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _extract_email_address(from_header: str) -> str | None:
    match = _EMAIL_ADDRESS_RE.search(from_header or "")
    return match.group(0).lower() if match else None


def _upsert_email_message(world_model: WorldModelStore, message: dict, source: str) -> None:
    message_id = message.get("message_id")
    from_header = message.get("from", "")
    address = _extract_email_address(from_header)
    if not message_id or not address:
        return

    person_id = f"email:{address}"
    world_model.upsert_entity(entity_id=person_id, entity_type="person", name=address, source=source)

    message_entity_id = f"email_message:{message_id}"
    message_entity = world_model.upsert_entity(
        entity_id=message_entity_id, entity_type="email_message",
        name=message.get("subject", "(no subject)"), source=source,
        attributes={"subject": message.get("subject"), "from": from_header, "date": message.get("date")},
    )
    world_model.link(subject_id=person_id, predicate="sent", object_id=message_entity.id, source=source)


def _observe_email_messages_list(world_model: WorldModelStore, params: dict, payload, source: str) -> None:
    if not isinstance(payload, list):
        return
    for message in payload:
        if isinstance(message, dict):
            _upsert_email_message(world_model, message, source)


def _observe_email_message(world_model: WorldModelStore, params: dict, payload, source: str) -> None:
    if isinstance(payload, dict):
        _upsert_email_message(world_model, payload, source)


def _observe_telephony_call(world_model: WorldModelStore, params: dict, call: dict, source: str) -> None:
    call_id = call.get("id")
    to = call.get("to")
    if not call_id or not to:
        return

    person_id = f"phone:{to}"
    world_model.upsert_entity(entity_id=person_id, entity_type="person", name=to, source=source)

    call_entity_id = f"telephony_call:{call_id}"
    call_entity = world_model.upsert_entity(
        entity_id=call_entity_id, entity_type="phone_call",
        name=f"Call to {to}: {call.get('status', '?')}", source=source,
        attributes={"to": to, "from": call.get("from"), "status": call.get("status"), "message": call.get("message")},
    )
    world_model.link(subject_id=person_id, predicate="received", object_id=call_entity.id, source=source)


def _observe_cloud_deployment(world_model: WorldModelStore, params: dict, deployment: dict, source: str) -> None:
    service = deployment.get("service")
    deployment_id = deployment.get("id")
    if not service or not deployment_id:
        return

    environment = deployment.get("environment", "production")
    service_id = f"cloud_service:{service}:{environment}"
    service_entity = world_model.upsert_entity(
        entity_id=service_id, entity_type="cloud_service", name=f"{service} ({environment})", source=source,
        attributes={"service": service, "environment": environment},
    )

    deployment_entity_id = f"cloud_deployment:{deployment_id}"
    deployment_entity = world_model.upsert_entity(
        entity_id=deployment_entity_id, entity_type="cloud_deployment",
        name=f"{service}@{deployment.get('version', '?')} ({environment})", source=source,
        attributes={
            "version": deployment.get("version"), "status": deployment.get("status"),
            "environment": environment, "previous_deployment_id": deployment.get("previous_deployment_id"),
        },
    )
    world_model.link(subject_id=deployment_entity.id, predicate="deploys", object_id=service_entity.id, source=source)


register_extractor("github.list_pull_requests", _observe_github_pull_requests_list)
register_extractor("github.get_pull_request", _observe_github_pull_request)
register_extractor("github.list_issues", _observe_github_issues_list)
register_extractor("github.get_issue", _observe_github_issue)
register_extractor("email.list_messages", _observe_email_messages_list)
register_extractor("email.search_messages", _observe_email_messages_list)
register_extractor("email.get_message", _observe_email_message)
register_extractor("telephony.call", _observe_telephony_call)
register_extractor("cloud.deploy", _observe_cloud_deployment)
register_extractor("cloud.rollback", _observe_cloud_deployment)
register_extractor("cloud.get_deployment_status", _observe_cloud_deployment)
