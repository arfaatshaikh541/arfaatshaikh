"""UniversalPlanner never trusts the model's output blindly: every
capability_name it proposes is re-checked against the real list of
currently-available capabilities before being treated as an executable
step. An unparseable response, a hallucinated capability name, and an
honestly-flagged missing capability are all reported as gaps, never
silently coerced into something executable -- the same discipline
executive.parse_plan() and email_intent.classify_message_intent() already
apply to model output driving a real decision.
"""
from __future__ import annotations

import pytest

from aura_core.capabilities import Capability, CapabilityRegistry
from aura_core.connectors import ConnectorRegistry, FilesystemConnector
from aura_core.governance.action_broker import ActionBroker
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import RiskEngine
from aura_core.planning import UniversalPlanner, parse_plan_response
from aura_core.providers import ModelRouter

_CAPS = [
    Capability(name="filesystem.write_file", domain="files", description="write a file"),
    Capability(name="email.send_external", domain="email", description="send an email"),
]


class ScriptedProvider:
    name = "scripted"

    def __init__(self, response: str) -> None:
        self.response = response
        self.last_prompt: str | None = None

    async def is_available(self) -> bool:
        return True

    async def generate_stream(self, prompt: str, history: list[dict[str, str]]):
        self.last_prompt = prompt
        for word in self.response.split(" "):
            yield word + " "


def test_parse_plan_response_resolves_a_valid_step():
    raw = '[{"capability_name": "email.send_external", "params": {"to": "a@b.com"}, "reasoning": "notify"}]'

    result = parse_plan_response("email someone", raw, _CAPS)

    assert result.fully_resolved
    assert len(result.steps) == 1
    assert result.steps[0].capability_name == "email.send_external"
    assert result.steps[0].params == {"to": "a@b.com"}


def test_parse_plan_response_rejects_a_hallucinated_capability_name():
    raw = '[{"capability_name": "social.instagram.magic_publish", "params": {}}]'

    result = parse_plan_response("post something", raw, _CAPS)

    assert not result.fully_resolved
    assert result.steps == []
    assert len(result.gaps) == 1
    assert "social.instagram.magic_publish" in result.gaps[0].missing_capability


def test_parse_plan_response_reports_an_honest_gap():
    raw = (
        '[{"missing_capability": "post to Instagram", "required_tool": "Instagram Graph API", '
        '"required_provider": "Meta", "required_permission": "owner OAuth token", '
        '"next_action": "connect AURA_INSTAGRAM_TOKEN"}]'
    )

    result = parse_plan_response("post to instagram", raw, _CAPS)

    assert result.gaps[0].missing_capability == "post to Instagram"
    assert result.gaps[0].required_provider == "Meta"
    gap_dict = result.gaps[0].to_dict()
    assert gap_dict["OBJECTIVE"] == "post to instagram"
    assert gap_dict["REQUIRED_TOOL"] == "Instagram Graph API"


def test_parse_plan_response_never_fabricates_a_plan_from_garbage():
    result = parse_plan_response("do something", "I'm not sure what you mean.", _CAPS)

    assert result.steps == []
    assert len(result.gaps) == 1
    assert "could not parse" in result.gaps[0].missing_capability


def test_parse_plan_response_handles_a_mix_of_steps_and_gaps():
    raw = (
        '[{"capability_name": "filesystem.write_file", "params": {"path": "x"}}, '
        '{"missing_capability": "generate an image"}]'
    )

    result = parse_plan_response("write a file and make an image", raw, _CAPS)

    assert len(result.steps) == 1
    assert len(result.gaps) == 1
    assert not result.fully_resolved


@pytest.mark.asyncio
async def test_universal_planner_drives_the_real_async_pipeline_end_to_end(tmp_path):
    db_url = f"sqlite:///{tmp_path}/planner.db"
    broker = ActionBroker(PolicyEngine(db_url), RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    connectors = ConnectorRegistry(broker)
    connectors.register(FilesystemConnector(str(tmp_path / "sandbox")))
    capabilities = CapabilityRegistry(connectors)

    provider = ScriptedProvider('[{"capability_name": "filesystem.write_file", "params": {"path": "x", "content": "y"}}]')
    router = ModelRouter(primary=provider, allow_test_fallback=False)

    planner = UniversalPlanner(router, capabilities)
    result = await planner.plan("write a file")

    assert result.fully_resolved
    assert result.steps[0].capability_name == "filesystem.write_file"
    assert "filesystem.write_file" in provider.last_prompt  # the real available-capability list reached the real prompt
