from __future__ import annotations

import os
import stat

from aura_core.identity import default_token_path, load_token, save_token


def test_a_missing_token_file_returns_none(tmp_path):
    assert load_token(str(tmp_path / "does_not_exist")) is None


def test_a_saved_token_round_trips(tmp_path):
    path = str(tmp_path / "nested" / "device_token")

    save_token(path, "the-real-secret-token")

    assert load_token(path) == "the-real-secret-token"


def test_the_saved_token_file_is_owner_only_readable(tmp_path):
    path = str(tmp_path / "device_token")
    save_token(path, "secret")

    mode = stat.S_IMODE(os.stat(path).st_mode)

    assert mode == 0o600


def test_default_token_path_is_a_sibling_of_the_sandbox_dir(tmp_path):
    sandbox_dir = str(tmp_path / "aura_sandbox")

    path = default_token_path(sandbox_dir)

    assert path == str(tmp_path / ".aura" / "device_token")
