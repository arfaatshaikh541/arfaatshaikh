"""parse_plan is the safety-critical seam between "whatever text a model
produced" and "an action the system will actually submit to the Action
Broker" -- pure and independently testable on purpose, so every case
below never needs a real model, router, or database."""
from __future__ import annotations

from aura_core.executive.executive import parse_plan


def test_a_valid_registered_action_is_accepted():
    raw = '{"action_type": "email.send_external", "params": {"to": "x@example.com"}, "reasoning": "follow up"}'
    plan = parse_plan(raw, allowed_action_types=["email.send_external", "filesystem.write_file"])

    assert plan.action_type == "email.send_external"
    assert plan.params == {"to": "x@example.com"}
    assert "follow up" in plan.summary


def test_an_action_type_not_in_the_allowed_list_is_rejected_not_executed():
    """This is the core safety property: a hallucinated or unregistered
    action_type must never reach the Action Broker just because it was
    shaped like a valid plan."""
    raw = '{"action_type": "launch_the_nukes", "params": {}}'
    plan = parse_plan(raw, allowed_action_types=["email.send_external"])

    assert plan.action_type is None


def test_an_advisory_response_is_accepted_as_a_non_executable_plan():
    raw = '{"advisory": "Wait for the client to reply before doing anything else.", "reasoning": "no info yet"}'
    plan = parse_plan(raw, allowed_action_types=["email.send_external"])

    assert plan.action_type is None
    assert plan.summary == "Wait for the client to reply before doing anything else."


def test_unparseable_text_never_crashes_and_never_fabricates_an_action():
    raw = "I think we should probably follow up with them soon, maybe next week."
    plan = parse_plan(raw, allowed_action_types=["email.send_external"])

    assert plan.action_type is None
    assert raw in plan.summary


def test_json_wrapped_in_markdown_fences_and_prose_is_still_extracted():
    raw = 'Sure, here is my plan:\n```json\n{"action_type": "filesystem.write_file", "params": {"path": "a.txt"}}\n```\nLet me know if this looks right.'
    plan = parse_plan(raw, allowed_action_types=["filesystem.write_file"])

    assert plan.action_type == "filesystem.write_file"
    assert plan.params == {"path": "a.txt"}


def test_a_non_dict_params_field_is_replaced_with_an_empty_dict_not_trusted_as_is():
    raw = '{"action_type": "filesystem.write_file", "params": "not a dict"}'
    plan = parse_plan(raw, allowed_action_types=["filesystem.write_file"])

    assert plan.action_type == "filesystem.write_file"
    assert plan.params == {}


def test_no_registered_actions_at_all_still_produces_an_honest_advisory():
    raw = '{"action_type": "email.send_external", "params": {}}'
    plan = parse_plan(raw, allowed_action_types=[])

    assert plan.action_type is None
