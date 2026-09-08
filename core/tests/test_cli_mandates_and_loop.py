from __future__ import annotations

import json

from click.testing import CliRunner

from aura_core.cli import main


def test_mandates_create_activate_list_and_report():
    runner = CliRunner()

    create_result = runner.invoke(main, [
        "mandates", "create", "Run Gridkeep", "Keep operations moving.",
        "--objective", "Answer inquiries fast",
        "--kpi", json.dumps({"name": "response_hours", "target": 24, "current": 0}),
        "--constraint", "never send without review",
    ])
    assert create_result.exit_code == 0, create_result.output
    mandate_id = create_result.output.split()[1]

    activate_result = runner.invoke(main, ["mandates", "activate", mandate_id])
    assert activate_result.exit_code == 0, activate_result.output
    assert "[active]" in activate_result.output

    list_result = runner.invoke(main, ["mandates", "list"])
    assert mandate_id in list_result.output

    report_result = runner.invoke(main, ["mandates", "report", mandate_id])
    assert report_result.exit_code == 0, report_result.output
    assert "Run Gridkeep" in report_result.output


def test_mandates_run_scaffolds_a_gridkeep_mandate_without_a_goal_form():
    runner = CliRunner()

    run_result = runner.invoke(main, ["mandates", "run", "Run Gridkeep"])

    assert run_result.exit_code == 0, run_result.output
    assert "[draft] Run Gridkeep" in run_result.output
    assert "Operate and grow Gridkeep" in run_result.output
    mandate_id = run_result.output.split()[1]

    # Departments are a generic scaffold, not real business facts -- the
    # activation gate still honestly refuses without real KPIs/constraints.
    activate_result = runner.invoke(main, ["mandates", "activate", mandate_id])
    assert activate_result.exit_code == 1
    assert "kpis" in activate_result.output and "constraints" in activate_result.output


def test_mandates_run_rejects_an_unrecognized_directive():
    runner = CliRunner()

    result = runner.invoke(main, ["mandates", "run", "What's happening with Gridkeep"])

    assert result.exit_code == 1
    assert "not a recognized directive" in result.output


def test_mandates_activate_without_required_fields_exits_nonzero():
    runner = CliRunner()
    create_result = runner.invoke(main, ["mandates", "create", "t", "m", "--objective", "o", "--constraint", "c"])
    mandate_id = create_result.output.split()[1]

    activate_result = runner.invoke(main, ["mandates", "activate", mandate_id])

    assert activate_result.exit_code == 1
    assert "Not ready" in activate_result.output


def test_goals_set_mandate_links_a_workstream_and_it_appears_in_the_report():
    runner = CliRunner()

    mandate_result = runner.invoke(main, [
        "mandates", "create", "Run Gridkeep", "m", "--objective", "o",
        "--kpi", json.dumps({"name": "k", "target": 1, "current": 0}), "--constraint", "c",
    ])
    mandate_id = mandate_result.output.split()[1]
    runner.invoke(main, ["mandates", "activate", mandate_id])

    goal_result = runner.invoke(main, [
        "goals", "create", "Write status note", "--success-metric", "written",
        "--budget", "{}", "--stop-condition", "s",
    ])
    goal_id = goal_result.output.split()[1]
    runner.invoke(main, ["goals", "activate", goal_id])

    link_result = runner.invoke(main, ["goals", "set-mandate", goal_id, mandate_id])
    assert link_result.exit_code == 0, link_result.output

    report_result = runner.invoke(main, ["mandates", "report", mandate_id])
    assert "Write status note" in report_result.output


def test_loop_run_once_executes_via_the_cli():
    runner = CliRunner()
    create_result = runner.invoke(main, [
        "goals", "create", "Say hello", "--success-metric", "greeted",
        "--budget", "{}", "--stop-condition", "stop if unclear", "--review-interval-seconds", "0",
    ])
    assert create_result.exit_code == 0, create_result.output
    goal_id = create_result.output.split()[1]
    activate_result = runner.invoke(main, ["goals", "activate", goal_id])
    assert activate_result.exit_code == 0, activate_result.output

    result = runner.invoke(main, ["loop", "run-once"])

    assert result.exit_code == 0, result.output
    assert "advisory" in result.output
