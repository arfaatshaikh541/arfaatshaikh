"""End-to-end proof that TaskWorker actually wires observation in, not
just that the extractor functions work in isolation (see
test_observation.py for that): a real execute_goal_step task, executed
through the real broker against the real GitHub connector's fake server
(reused from test_connector_github.py's pattern), must leave a real
Entity behind in WorldModelStore with nothing else driving it.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aura_core.connectors import ConnectorRegistry, build_github_connector
from aura_core.executive import GoalEngine, TaskWorker
from aura_core.governance import ActionBroker, ApprovalEngine, AuditLog, CredentialBroker, PolicyEngine, RiskEngine
from aura_core.memory import MemoryStore, WorldModelStore


class _FakeGitHubHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/repos/acme/widgets/pulls/42":
            self._respond(200, {"number": 42, "title": "Fix the widget", "user": {"login": "grace"}})
        else:
            self._respond(404, {"message": "Not Found"})

    def _respond(self, status, payload):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_github():
    server = HTTPServer(("127.0.0.1", 0), _FakeGitHubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()


def test_a_real_execute_goal_step_task_populates_the_world_model(tmp_path, fake_github):
    db_url = f"sqlite:///{tmp_path}/loop_obs.db"
    memory = MemoryStore(db_url)
    world_model = WorldModelStore(db_url)
    policy = PolicyEngine(db_url)
    policy.set_autonomy_level("github.get_pull_request", 4)
    broker = ActionBroker(policy, RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    ConnectorRegistry(broker).register(build_github_connector(token="tok", base_url=fake_github))

    from aura_core.tasks import TaskEngine
    tasks = TaskEngine(db_url)
    goals = GoalEngine(db_url)
    worker = TaskWorker(tasks, broker, goals, memory, world_model)

    tasks.enqueue("execute_goal_step", {
        "goal_id": None, "action_type": "github.get_pull_request",
        "params": {"owner": "acme", "repo": "widgets", "number": 42}, "summary": "check the PR",
    })

    outcome = worker.run_once()

    assert outcome.outcome == "executed"
    entities = world_model.find_entities(entity_type="github_pull_request")
    assert len(entities) == 1
    assert entities[0].id == "github:acme/widgets#pr42"
    people = world_model.find_entities(entity_type="person")
    assert len(people) == 1
    assert people[0].name == "grace"


def test_a_worker_with_no_world_model_still_works_exactly_as_before(tmp_path, fake_github):
    """world_model is optional -- every existing caller that doesn't pass
    one (all the pre-existing TaskWorker tests) must be entirely
    unaffected by this feature's addition."""
    db_url = f"sqlite:///{tmp_path}/loop_obs_none.db"
    memory = MemoryStore(db_url)
    policy = PolicyEngine(db_url)
    policy.set_autonomy_level("github.get_pull_request", 4)
    broker = ActionBroker(policy, RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), AuditLog(db_url))
    ConnectorRegistry(broker).register(build_github_connector(token="tok", base_url=fake_github))

    from aura_core.tasks import TaskEngine
    tasks = TaskEngine(db_url)
    goals = GoalEngine(db_url)
    worker = TaskWorker(tasks, broker, goals, memory)  # no world_model

    tasks.enqueue("execute_goal_step", {
        "goal_id": None, "action_type": "github.get_pull_request",
        "params": {"owner": "acme", "repo": "widgets", "number": 42}, "summary": "check the PR",
    })

    outcome = worker.run_once()

    assert outcome.outcome == "executed"
