from __future__ import annotations

from click.testing import CliRunner

from aura_core.cli import main
from aura_core.runtime import build_runtime


def test_memory_search_cli_finds_and_ranks_real_records():
    runtime = build_runtime()
    runtime.memory.record_event(event_type="pricing", summary="Gridkeep moved to tiered pricing", source="s")

    runner = CliRunner()
    result = runner.invoke(main, ["memory", "search", "Gridkeep pricing"])

    assert result.exit_code == 0, result.output
    assert "Gridkeep" in result.output


def test_memory_search_cli_reports_no_matches_honestly():
    runner = CliRunner()
    result = runner.invoke(main, ["memory", "search", "nonexistent topic entirely"])

    assert result.exit_code == 0, result.output
    assert "No matching memory found." in result.output


def test_memory_ask_cli_answers_from_real_context():
    runtime = build_runtime()
    runtime.memory.record_decision(
        goal="pricing", statement="Charge Gridkeep customers a flat monthly fee",
        reasoning="simplest to bill", source="s",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["memory", "ask", "Why did we decide to charge Gridkeep that way?"])

    assert result.exit_code == 0, result.output
    assert "grounded in" in result.output


def test_memory_ask_cli_with_nothing_relevant_exits_nonzero():
    runner = CliRunner()
    result = runner.invoke(main, ["memory", "ask", "What happened with the flying saucers?"])

    assert result.exit_code == 1
    assert "Could not answer" in result.output
