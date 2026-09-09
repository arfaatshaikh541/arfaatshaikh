from __future__ import annotations

from click.testing import CliRunner

from aura_core.cli import main
from aura_core.identity import default_token_path, load_token
from aura_core.runtime import build_runtime


def test_enroll_creates_an_owner_and_saves_a_working_token():
    runner = CliRunner()

    result = runner.invoke(main, ["enroll", "--display-name", "Ada"])

    assert result.exit_code == 0, result.output
    assert "Enrolled owner 'Ada'" in result.output

    runtime = build_runtime()
    assert runtime.enrollment.is_enrolled() is True
    token_path = default_token_path(runtime.settings.filesystem_sandbox_dir)
    saved_token = load_token(token_path)
    assert saved_token is not None
    assert runtime.enrollment.verify_token(saved_token) is not None


def test_enrolling_twice_fails_honestly_without_minting_a_second_owner():
    runner = CliRunner()
    runner.invoke(main, ["enroll", "--display-name", "Ada"])

    result = runner.invoke(main, ["enroll", "--display-name", "Someone Else"])

    assert result.exit_code != 0
    assert "already enrolled" in result.output
    runtime = build_runtime()
    assert len(runtime.enrollment.list_devices()) == 1


def test_devices_list_before_enrollment_says_so():
    runner = CliRunner()

    result = runner.invoke(main, ["devices", "list"])

    assert result.exit_code == 0, result.output
    assert "No owner enrolled" in result.output


def test_devices_list_and_revoke_round_trip():
    runner = CliRunner()
    runner.invoke(main, ["enroll", "--display-name", "Ada"])
    runtime = build_runtime()
    device = runtime.enrollment.list_devices()[0]

    list_result = runner.invoke(main, ["devices", "list"])
    assert device.id in list_result.output
    assert "active" in list_result.output

    revoke_result = runner.invoke(main, ["devices", "revoke", device.id])
    assert revoke_result.exit_code == 0, revoke_result.output

    list_after = runner.invoke(main, ["devices", "list"])
    assert "revoked" in list_after.output
