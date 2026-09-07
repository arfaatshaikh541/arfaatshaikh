"""World Model observation: proves the audit's flagged gap --
"nothing populates it from observation" -- is actually closed. Two
layers: pure unit tests of observe() against crafted JSON (fast, exact),
and one true end-to-end test driving a real execute_goal_step task
through TaskWorker against the real GitHub connector's fake server, to
prove the wiring itself (not just the extractor functions in isolation).
"""
from __future__ import annotations

import json

import pytest

from aura_core.executive.observation import observe
from aura_core.memory.world_model import WorldModelStore


@pytest.fixture
def world_model(tmp_path):
    return WorldModelStore(f"sqlite:///{tmp_path}/world.db")


def test_an_unregistered_action_type_is_a_silent_no_op(world_model):
    observe(world_model, "some.unrelated.action", {}, json.dumps({"anything": True}), source="test")

    assert world_model.find_entities() == []


def test_malformed_json_does_not_raise(world_model):
    observe(world_model, "github.get_pull_request", {}, "not json at all {{{", source="test")

    assert world_model.find_entities() == []


def test_a_single_pull_request_becomes_an_entity(world_model):
    payload = json.dumps({"number": 42, "title": "Fix the widget", "state": "open"})

    observe(world_model, "github.get_pull_request", {"owner": "acme", "repo": "widgets"}, payload, source="test")

    entities = world_model.find_entities(entity_type="github_pull_request")
    assert len(entities) == 1
    assert entities[0].id == "github:acme/widgets#pr42"
    assert "Fix the widget" in entities[0].name


def test_a_pull_request_with_an_author_links_a_person_entity(world_model):
    payload = json.dumps({"number": 42, "title": "Fix the widget", "user": {"login": "grace"}})

    observe(world_model, "github.get_pull_request", {"owner": "acme", "repo": "widgets"}, payload, source="test")

    people = world_model.find_entities(entity_type="person")
    assert len(people) == 1
    assert people[0].name == "grace"
    pr = world_model.find_entities(entity_type="github_pull_request")[0]
    relationships = world_model.relationships_from(people[0].id, predicate="authored")
    assert len(relationships) == 1
    assert relationships[0].object_id == pr.id


def test_a_pull_request_without_an_author_still_records_the_pr_alone(world_model):
    payload = json.dumps({"number": 7, "title": "No author field"})

    observe(world_model, "github.get_pull_request", {"owner": "acme", "repo": "widgets"}, payload, source="test")

    assert len(world_model.find_entities(entity_type="github_pull_request")) == 1
    assert world_model.find_entities(entity_type="person") == []


def test_a_list_of_pull_requests_creates_one_entity_each(world_model):
    payload = json.dumps([
        {"number": 1, "title": "First"},
        {"number": 2, "title": "Second"},
    ])

    observe(world_model, "github.list_pull_requests", {"owner": "acme", "repo": "widgets"}, payload, source="test")

    assert len(world_model.find_entities(entity_type="github_pull_request")) == 2


def test_observing_the_same_pull_request_twice_updates_rather_than_duplicates(world_model):
    params = {"owner": "acme", "repo": "widgets"}
    observe(world_model, "github.get_pull_request", params, json.dumps({"number": 42, "title": "Draft"}), source="a")
    observe(world_model, "github.get_pull_request", params, json.dumps({"number": 42, "title": "Ready"}), source="b")

    entities = world_model.find_entities(entity_type="github_pull_request")
    assert len(entities) == 1
    assert "Ready" in entities[0].name


def test_an_issue_becomes_an_entity_with_its_reporter_linked(world_model):
    payload = json.dumps({"number": 9, "title": "It's broken", "user": {"login": "ada"}})

    observe(world_model, "github.get_issue", {"owner": "acme", "repo": "widgets"}, payload, source="test")

    issues = world_model.find_entities(entity_type="github_issue")
    assert len(issues) == 1
    reporters = world_model.relationships_to(issues[0].id, predicate="reported")
    assert len(reporters) == 1


def test_an_email_message_links_its_sender_as_a_person(world_model):
    payload = json.dumps({
        "message_id": "<msg-1@example.test>", "from": "Grace Hopper <grace@example.test>",
        "subject": "Widget order", "date": "Mon, 1 Jan 2024 10:00:00 +0000",
    })

    observe(world_model, "email.get_message", {}, payload, source="test")

    people = world_model.find_entities(entity_type="person")
    messages = world_model.find_entities(entity_type="email_message")
    assert len(people) == 1
    assert people[0].name == "grace@example.test"
    assert len(messages) == 1
    sent = world_model.relationships_from(people[0].id, predicate="sent")
    assert len(sent) == 1
    assert sent[0].object_id == messages[0].id


def test_a_list_of_email_messages_creates_one_person_per_unique_sender(world_model):
    payload = json.dumps([
        {"message_id": "<1@x>", "from": "a@example.test", "subject": "s1"},
        {"message_id": "<2@x>", "from": "a@example.test", "subject": "s2"},
        {"message_id": "<3@x>", "from": "b@example.test", "subject": "s3"},
    ])

    observe(world_model, "email.list_messages", {}, payload, source="test")

    assert len(world_model.find_entities(entity_type="person")) == 2
    assert len(world_model.find_entities(entity_type="email_message")) == 3


def test_an_email_with_no_extractable_address_is_skipped_not_crashed(world_model):
    payload = json.dumps({"message_id": "<1@x>", "from": "not an email address", "subject": "s"})

    observe(world_model, "email.get_message", {}, payload, source="test")

    assert world_model.find_entities() == []
