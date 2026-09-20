"""Local persistence for the device token issued at enrollment, so a CLI
invocation or a locally running API client can present it automatically
instead of asking the owner to log in every time. See enrollment.py's
module docstring for why owner-only file permissions (used here) are
real protection but not equivalent to a real OS secret store.

Restricting the file to its owner is platform-specific and cannot be
done with one code path: POSIX mode bits (os.chmod) are meaningless on
Windows, which controls access through ACLs instead -- os.chmod there
only toggles the read-only attribute, never who can read the file. A
`chmod 600` call that "succeeds" on Windows silently leaves the token
exactly as readable as it always was (confirmed: a real Windows install-
gate run reported the file at mode 0o666, not 0o600, after this exact
call). The real Windows equivalent is `icacls`, the standard tool present
on every Windows install, used here to strip inherited permissions and
grant Full control to only the current user.
"""
from __future__ import annotations

import os
import platform
import stat
import subprocess


def default_token_path(sandbox_dir: str) -> str:
    parent = os.path.dirname(os.path.abspath(sandbox_dir))
    return os.path.join(parent, ".aura", "device_token")


def save_token(path: str, raw_token: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(raw_token)
    if platform.system() == "Windows":
        _restrict_to_current_user_windows(path)
    else:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600: owner read/write only


def _restrict_to_current_user_windows(path: str) -> None:
    username = os.environ.get("USERNAME")
    if not username:
        raise OSError("cannot restrict device token file: USERNAME environment variable is not set")
    domain = os.environ.get("USERDOMAIN")
    account = f"{domain}\\{username}" if domain else username

    result = subprocess.run(
        ["icacls", path, "/inheritance:r", "/grant:r", f"{account}:(R,W)"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        # Fail closed: a token file whose permissions could not be
        # verified as restricted must not be silently left world-
        # readable on disk.
        raise OSError(f"failed to restrict {path} to {account} via icacls: {result.stderr.strip()}")


def load_token(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    with open(path) as handle:
        content = handle.read().strip()
    return content or None
