"""Skills are compositions of real, already-governed capabilities. These
tests prove: a skill persists across a fresh SkillRegistry against the
same database (a real restart), the builder rejects an unknown/
hallucinated capability name outright, and running a skill drives every
step through the real Action Broker -- including a real deny when
autonomy is too low, and a real abort-on-failure when a step fails.
"""
from __future__ import annotations

from aura_core.capabilities import CapabilityRegistry
from aura_core.connectors import ConnectorRegistry, FilesystemConnector
from aura_core.governance.action_broker import ActionBroker, OutcomeStatus
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import RiskEngine
from aura_core.skills import DynamicSkillBuilder, SkillEngine, SkillRegistry, SkillStep, UnknownCapabilityError


def make_stack(tmp_path):
    db_url = f"sqlite:///{tmp_path}/skills.db"
    policy = PolicyEngine(db_url)
    broker = ActionBroker(policy, RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    connectors = ConnectorRegistry(broker)
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    connectors.register(FilesystemConnector(str(sandbox)))
    capabilities = CapabilityRegistry(connectors)
    skills = SkillRegistry(db_url)
    return policy, broker, capabilities, skills, sandbox


def test_builder_rejects_an_unknown_capability_name(tmp_path):
    _policy, _broker, capabilities, skills, _sandbox = make_stack(tmp_path)
    builder = DynamicSkillBuilder(capabilities, skills)

    try:
        builder.compose(
            "bad skill", "d", "custom",
            [SkillStep(capability_name="not.a.real.capability")],
        )
        assert False, "expected UnknownCapabilityError"
    except UnknownCapabilityError as exc:
        assert "not.a.real.capability" in exc.unknown_names


def test_builder_composes_and_persists_a_real_skill(tmp_path):
    _policy, _broker, capabilities, skills, _sandbox = make_stack(tmp_path)
    builder = DynamicSkillBuilder(capabilities, skills)

    skill = builder.compose(
        "write then read", "writes a file then reads it back", "files",
        [
            SkillStep(capability_name="filesystem.write_file", params_template={"path": "{{path}}", "content": "{{content}}"}),
            SkillStep(capability_name="filesystem.read_file", params_template={"path": "{{path}}"}),
        ],
    )

    assert skill.id
    reopened = SkillRegistry(f"sqlite:///{tmp_path}/skills.db")
    reloaded = reopened.get(skill.id)
    assert reloaded is not None
    assert reloaded.name == "write then read"
    assert len(reloaded.steps()) == 2


def test_skill_engine_runs_every_step_through_the_real_broker(tmp_path):
    policy, broker, capabilities, skills, _sandbox = make_stack(tmp_path)
    policy.set_autonomy_level("filesystem.write_file", 4)
    policy.set_autonomy_level("filesystem.read_file", 4)
    builder = DynamicSkillBuilder(capabilities, skills)
    skill = builder.compose(
        "write then read", "d", "files",
        [
            SkillStep(capability_name="filesystem.write_file", params_template={"path": "{{path}}", "content": "{{content}}"}),
            SkillStep(capability_name="filesystem.read_file", params_template={"path": "{{path}}"}),
        ],
    )

    engine = SkillEngine(broker)
    result = engine.run(skill, context={"path": "note.txt", "content": "hello from a skill"})

    assert result.succeeded
    assert len(result.step_results) == 2
    assert result.step_results[0].outcome.status == OutcomeStatus.EXECUTED
    assert "hello from a skill" in result.step_results[1].outcome.message


def test_skill_engine_aborts_on_the_first_denied_step_by_default(tmp_path):
    # No autonomy level set -> level 0 -> denied. Proves a skill cannot
    # be used to bypass the same governance a single capability call
    # would face.
    _policy, broker, capabilities, skills, _sandbox = make_stack(tmp_path)
    builder = DynamicSkillBuilder(capabilities, skills)
    skill = builder.compose(
        "write then read", "d", "files",
        [
            SkillStep(capability_name="filesystem.write_file", params_template={"path": "{{path}}", "content": "{{content}}"}),
            SkillStep(capability_name="filesystem.read_file", params_template={"path": "{{path}}"}),
        ],
    )

    engine = SkillEngine(broker)
    result = engine.run(skill, context={"path": "note.txt", "content": "hello"})

    assert not result.succeeded
    assert len(result.step_results) == 1  # never reached the second step
    assert result.step_results[0].outcome.status == OutcomeStatus.DENIED


def test_skill_step_with_continue_on_failure_keeps_running(tmp_path):
    policy, broker, capabilities, skills, _sandbox = make_stack(tmp_path)
    policy.set_autonomy_level("filesystem.read_file", 4)
    builder = DynamicSkillBuilder(capabilities, skills)
    skill = builder.compose(
        "best-effort read", "d", "files",
        [
            SkillStep(capability_name="filesystem.write_file", params_template={"path": "x", "content": "y"}, on_failure="continue"),
            SkillStep(capability_name="filesystem.read_file", params_template={"path": "does-not-exist.txt"}),
        ],
    )

    engine = SkillEngine(broker)
    result = engine.run(skill)

    assert len(result.step_results) == 2
    assert result.step_results[0].outcome.status == OutcomeStatus.DENIED  # write not authorized, but continued
