"""Local persistence for the device token issued at enrollment, so a CLI
invocation or a locally running API client can present it automatically
instead of asking the owner to log in every time. See enrollment.py's
module docstring for why owner-only file permissions (used here) are
real protection but not equivalent to a real OS secret store.
"""
from __future__ import annotations

import os
import stat


def default_token_path(sandbox_dir: str) -> str:
    parent = os.path.dirname(os.path.abspath(sandbox_dir))
    return os.path.join(parent, ".aura", "device_token")


def save_token(path: str, raw_token: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(raw_token)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600: owner read/write only


def load_token(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    with open(path) as handle:
        content = handle.read().strip()
    return content or None
