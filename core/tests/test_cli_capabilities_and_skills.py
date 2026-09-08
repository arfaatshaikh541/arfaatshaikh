from __future__ import annotations

import json

from click.testing import CliRunner

from aura_core.cli import main


def test_capabilities_list_shows_real_registered_capabilities():
    runner = CliRunner()

    result = runner.invoke(main, ["capabilities", "list", "--available-only"])

    assert result.exit_code == 0, result.output
    assert "filesystem.read_file" in result.output
    assert "(available)" in result.output


def test_capabilities_list_filters_by_domain():
    runner = CliRunner()

    result = runner.invoke(main, ["capabilities", "list", "--domain", "email"])

    assert result.exit_code == 0, result.output
    assert "email.send_external" in result.output
    assert "filesystem.read_file" not in result.output


def test_skills_compose_list_and_run_end_to_end(tmp_path):
    runner = CliRunner()

    compose_result = runner.invoke(main, [
        "skills", "compose", "write a note", "writes a file", "files",
        "--step", json.dumps({"capability_name": "filesystem.write_file", "params_template": {"path": "note.txt", "content": "hello"}}),
    ])
    assert compose_result.exit_code == 0, compose_result.output
    skill_id = compose_result.output.split()[2]

    list_result = runner.invoke(main, ["skills", "list"])
    assert skill_id in list_result.output

    from aura_core.runtime import build_runtime
    build_runtime().policy.set_autonomy_level("filesystem.write_file", 4)

    run_result = runner.invoke(main, ["skills", "run", skill_id])
    assert "[completed]" in run_result.output, run_result.output


def test_skills_compose_rejects_an_unknown_capability():
    runner = CliRunner()

    result = runner.invoke(main, [
        "skills", "compose", "bad", "d", "custom",
        "--step", json.dumps({"capability_name": "not.a.real.capability"}),
    ])

    assert result.exit_code == 1
    assert "not.a.real.capability" in result.output


def test_plan_command_reports_an_honest_gap_without_a_real_model():
    runner = CliRunner()

    result = runner.invoke(main, ["plan", "do something nobody defined a capability for"])

    assert result.exit_code == 0, result.output
    assert "Objective:" in result.output
    assert "Capability gaps:" in result.output
