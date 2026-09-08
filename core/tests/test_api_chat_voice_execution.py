"""Voice/chat as a first-class channel into the same general-purpose
planner + Action Broker execution every other interface uses -- not a
hardcoded voice-command list. These tests swap in a scripted model
provider (the same technique test_universal_planner.py and
test_email_intent.py use) so the planner can actually resolve a plan,
then prove /chat drives it through the REAL Action Broker: a resolved
step really executes (a real file gets written), a step needing
approval is voiced naturally per section 19 rather than silently
executed or silently skipped, and a plan the planner cannot resolve at
all still falls through to the ordinary conversational model response
unchanged -- proving this addition doesn't hijack normal conversation.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from aura_core.api import create_app
from aura_core.config import load_settings
from aura_core.planning import UniversalPlanner
from aura_core.providers import ModelRouter


class ScriptedProvider:
    name = "scripted"

    def __init__(self, response: str) -> None:
        self.response = response

    async def is_available(self) -> bool:
        return True

    async def generate_stream(self, prompt: str, history: list[dict[str, str]]):
        for word in self.response.split(" "):
            yield word + " "


def _parse_events(lines: list[str]) -> list[dict]:
    events = []
    for line in lines:
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[len("data: "):]))
    return events


def _install_scripted_planner(app, response: str) -> None:
    scripted_router = ModelRouter(primary=ScriptedProvider(response), allow_test_fallback=False)
    app.state.runtime.planner = UniversalPlanner(scripted_router, app.state.runtime.capabilities)


def test_chat_executes_a_fully_resolved_plan_through_the_real_broker(tmp_path):
    app = create_app(load_settings())
    app.state.runtime.policy.set_autonomy_level("filesystem.write_file", 4)
    _install_scripted_planner(app, (
        '[{"capability_name": "filesystem.write_file", '
        f'"params": {{"path": "voice-note.txt", "content": "written from voice"}}}}]'
    ))
    client = TestClient(app)

    with client.stream("POST", "/chat", json={"message": "write a note for me"}) as response:
        events = _parse_events(list(response.iter_lines()))

    lanes = [e for e in events if e["event"] == "lane"]
    assert lanes[0]["data"] == "planner"
    chunks = [e for e in events if e["event"] == "chunk"]
    assert "wrote" in "".join(c["data"] for c in chunks)
    assert "voice-note.txt" in "".join(c["data"] for c in chunks)
    assert events[-1]["data"] == "ok"

    written_path = app.state.runtime.settings.filesystem_sandbox_dir + "/voice-note.txt"
    with open(written_path) as handle:
        assert handle.read() == "written from voice"


def test_chat_asks_naturally_for_approval_instead_of_silently_executing(tmp_path):
    app = create_app(load_settings())
    app.state.runtime.policy.set_autonomy_level("filesystem.write_file", 2)  # REQUIRE_APPROVAL tier
    _install_scripted_planner(app, (
        '[{"capability_name": "filesystem.write_file", "params": {"path": "x.txt", "content": "y"}}]'
    ))
    client = TestClient(app)

    with client.stream("POST", "/chat", json={"message": "write a note for me"}) as response:
        events = _parse_events(list(response.iter_lines()))

    chunks = "".join(e["data"] for e in events if e["event"] == "chunk")
    assert "Shall I proceed?" in chunks
    assert events[-1]["data"] == "pending_approval"

    # And the write genuinely did not happen -- this is a real gate, not
    # a UI-only confirmation dialog.
    import os
    assert not os.path.exists(os.path.join(app.state.runtime.settings.filesystem_sandbox_dir, "x.txt"))


def test_chat_reports_a_mixed_plan_honestly(tmp_path):
    app = create_app(load_settings())
    app.state.runtime.policy.set_autonomy_level("filesystem.write_file", 4)
    _install_scripted_planner(app, (
        '[{"capability_name": "filesystem.write_file", "params": {"path": "x.txt", "content": "y"}}, '
        '{"missing_capability": "post to Instagram", "required_provider": "Meta"}]'
    ))
    client = TestClient(app)

    with client.stream("POST", "/chat", json={"message": "write a note and post to instagram"}) as response:
        events = _parse_events(list(response.iter_lines()))

    chunks = "".join(e["data"] for e in events if e["event"] == "chunk")
    assert "wrote" in chunks.lower() or "x.txt" in chunks
    assert "Meta" in chunks
    assert events[-1]["data"] == "partial"


def test_chat_falls_through_to_the_model_when_the_planner_resolves_nothing():
    """Regression guard: a purely conversational request must still get
    a normal spoken answer, not a capability-gap message, when nothing
    concrete can be resolved -- the exact scenario the pre-existing
    AURA_ENV=test deterministic-provider path already covers."""
    client = TestClient(create_app(load_settings()))

    with client.stream("POST", "/chat", json={"message": "tell me about Gridkeep"}) as response:
        events = _parse_events(list(response.iter_lines()))

    lanes = [e for e in events if e["event"] == "lane"]
    assert lanes[0]["data"] == "model"
