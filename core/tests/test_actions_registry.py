from __future__ import annotations

from aura_core.actions import build_default_registry
from aura_core.memory import MemoryStore
from aura_core.status import CapabilityStatus


def test_status_action_is_handled_deterministically(tmp_path):
    memory = MemoryStore(f"sqlite:///{tmp_path}/mem.db")
    registry = build_default_registry(memory)

    result = registry.dispatch("status")

    assert result is not None
    assert result.handled is True
    assert result.status == CapabilityStatus.LIVE


def test_unregistered_command_returns_none_for_model_lane(tmp_path):
    memory = MemoryStore(f"sqlite:///{tmp_path}/mem.db")
    registry = build_default_registry(memory)

    result = registry.dispatch("write me a haiku about databases")

    assert result is None  # falls through to the model lane, not swallowed


def test_open_chrome_is_honestly_not_connected(tmp_path):
    memory = MemoryStore(f"sqlite:///{tmp_path}/mem.db")
    registry = build_default_registry(memory)

    result = registry.dispatch("open chrome")

    assert result is not None
    assert result.status == CapabilityStatus.NOT_CONNECTED


def test_show_tasks_reflects_real_commitments(tmp_path):
    memory = MemoryStore(f"sqlite:///{tmp_path}/mem.db")
    memory.add_commitment(description="Send Q3 proposal to Gridkeep", source="unit-test")
    registry = build_default_registry(memory)

    result = registry.dispatch("show tasks")

    assert result is not None
    assert "Send Q3 proposal to Gridkeep" in result.message
