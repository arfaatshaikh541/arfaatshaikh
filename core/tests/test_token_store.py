from __future__ import annotations

import os
import platform
import stat
import subprocess

import pytest

from aura_core.identity import default_token_path, load_token, save_token


def test_a_missing_token_file_returns_none(tmp_path):
    assert load_token(str(tmp_path / "does_not_exist")) is None


def test_a_saved_token_round_trips(tmp_path):
    path = str(tmp_path / "nested" / "device_token")

    save_token(path, "the-real-secret-token")

    assert load_token(path) == "the-real-secret-token"


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="POSIX mode bits don't restrict access on Windows at all -- os.chmod there only toggles "
    "the read-only attribute, so this assertion would be meaningless (confirmed on a real Windows "
    "install: the file came back as 0o666, not 0o600). See the ACL-based test below for Windows.",
)
def test_the_saved_token_file_is_owner_only_readable(tmp_path):
    path = str(tmp_path / "device_token")
    save_token(path, "secret")

    mode = stat.S_IMODE(os.stat(path).st_mode)

    assert mode == 0o600


@pytest.mark.windows
@pytest.mark.skipif(
    platform.system() != "Windows",
    reason="exercises the real icacls ACL restriction; only meaningful on Windows",
)
def test_the_saved_token_file_is_restricted_to_the_current_user_via_acl_on_windows(tmp_path):
    path = str(tmp_path / "device_token")
    save_token(path, "secret")

    result = subprocess.run(["icacls", path], capture_output=True, text=True)
    assert result.returncode == 0
    output = result.stdout
    # Broad, non-owner grants must be gone -- these are the groups a
    # freshly created file typically inherits access from.
    for broad_group in ("Everyone", "BUILTIN\\Users", "Authenticated Users"):
        assert broad_group not in output, f"{broad_group} still has access to the device token file"
    assert os.environ["USERNAME"] in output, "the current user has no explicit grant on the device token file"


def test_default_token_path_is_a_sibling_of_the_sandbox_dir(tmp_path):
    sandbox_dir = str(tmp_path / "aura_sandbox")

    path = default_token_path(sandbox_dir)

    assert path == str(tmp_path / ".aura" / "device_token")
