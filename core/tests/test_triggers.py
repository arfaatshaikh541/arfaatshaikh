from __future__ import annotations

from aura_core.actions import build_default_triggers


def test_known_trigger_resolves_to_action_request():
    triggers = build_default_triggers()
    request = triggers.resolve("status")
    assert request is not None
    assert request.action_type == "status.read"


def test_trigger_matching_is_case_and_punctuation_insensitive():
    triggers = build_default_triggers()
    request = triggers.resolve("  Status! ")
    assert request is not None
    assert request.action_type == "status.read"


def test_unknown_text_does_not_resolve():
    triggers = build_default_triggers()
    assert triggers.resolve("write me a haiku about databases") is None


def test_computer_control_triggers_are_registered_but_not_silently_absent():
    triggers = build_default_triggers()
    request = triggers.resolve("open chrome")
    assert request is not None
    assert request.action_type == "computer_control.open_app"
