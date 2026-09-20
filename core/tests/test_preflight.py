from __future__ import annotations

import json
import os
import subprocess
import sys

_PREFLIGHT_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "..", "install", "preflight.py")


def test_preflight_runs_and_exits_zero_on_a_healthy_system():
    result = subprocess.run([sys.executable, _PREFLIGHT_SCRIPT], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "python_version" in result.stdout
    assert "PASS" in result.stdout


def test_preflight_json_output_is_well_formed():
    result = subprocess.run(
        [sys.executable, _PREFLIGHT_SCRIPT, "--json"], capture_output=True, text=True, timeout=30,
    )
    checks = json.loads(result.stdout)
    assert isinstance(checks, list)
    assert len(checks) >= 6
    names = {c["name"] for c in checks}
    assert {"python_version", "pip", "disk_space", "write_permission"}.issubset(names)
    for check in checks:
        assert check["status"] in {"PASS", "WARN", "FAIL"}


def test_preflight_python_version_check_reflects_the_real_interpreter():
    result = subprocess.run(
        [sys.executable, _PREFLIGHT_SCRIPT, "--json"], capture_output=True, text=True, timeout=30,
    )
    checks = {c["name"]: c for c in json.loads(result.stdout)}
    assert checks["python_version"]["status"] == "PASS"
    assert f"{sys.version_info.major}.{sys.version_info.minor}" in checks["python_version"]["detail"]
