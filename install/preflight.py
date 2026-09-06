#!/usr/bin/env python3
"""AURA preflight checker — cross-platform (Windows/Linux/macOS), stdlib
only (must run before the venv exists). Real system inspection, not a
placeholder: each check does the actual thing it claims to check.

Usage: python3 preflight.py [--json]
Exit code: 0 if no FAIL-level checks, 1 otherwise.
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str


@dataclass
class Report:
    results: list[CheckResult] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str) -> None:
        self.results.append(CheckResult(name, status, detail))

    @property
    def exit_code(self) -> int:
        return 1 if any(r.status == FAIL for r in self.results) else 0


def check_python_version(report: Report) -> None:
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) >= (3, 11):
        report.add("python_version", PASS, f"{major}.{minor}.{sys.version_info.micro}")
    else:
        report.add("python_version", FAIL, f"found {major}.{minor}, need >=3.11")


def check_pip(report: Report) -> None:
    result = subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, text=True)
    if result.returncode == 0:
        report.add("pip", PASS, result.stdout.strip())
    else:
        report.add("pip", FAIL, "pip is not available for this Python interpreter")


def check_dotnet_sdk(report: Report) -> None:
    path = shutil.which("dotnet")
    if path is None:
        report.add("dotnet_sdk", WARN, "dotnet not found on PATH -- needed only for the Windows shell/voice C# projects")
        return
    result = subprocess.run(["dotnet", "--version"], capture_output=True, text=True)
    if result.returncode == 0:
        report.add("dotnet_sdk", PASS, f"dotnet {result.stdout.strip()} at {path}")
    else:
        report.add("dotnet_sdk", WARN, "dotnet found but `dotnet --version` failed")


def check_ollama_reachable(report: Report, host: str = "127.0.0.1", port: int = 11434) -> None:
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
    except OSError:
        report.add(
            "ollama", WARN,
            f"no Ollama server reachable at {host}:{port} -- real chat responses require it (see core/RUNBOOK.md); "
            "the deterministic action lane and test-mode chat work without it",
        )
        return
    try:
        urllib.request.urlopen(f"http://{host}:{port}/api/tags", timeout=2)
        report.add("ollama", PASS, f"reachable at {host}:{port}")
    except urllib.error.URLError as exc:
        report.add("ollama", WARN, f"port open but /api/tags failed: {exc}")


def check_disk_space(report: Report, path: str = ".", min_free_gb: float = 2.0) -> None:
    usage = shutil.disk_usage(path)
    free_gb = usage.free / (1024 ** 3)
    if free_gb >= min_free_gb:
        report.add("disk_space", PASS, f"{free_gb:.1f} GB free")
    else:
        report.add("disk_space", FAIL, f"only {free_gb:.1f} GB free, need >= {min_free_gb} GB")


def check_write_permission(report: Report, path: str = ".") -> None:
    import os
    import tempfile

    try:
        fd, tmp_path = tempfile.mkstemp(dir=path)
        os.close(fd)
        os.remove(tmp_path)
        report.add("write_permission", PASS, f"{path} is writable")
    except OSError as exc:
        report.add("write_permission", FAIL, f"{path} is not writable: {exc}")


def check_espeak_ng_data(report: Report) -> None:
    import os

    candidates = [
        "/usr/lib/x86_64-linux-gnu/espeak-ng-data",
        "/usr/share/espeak-ng-data",
        "/usr/local/share/espeak-ng-data",
    ]
    found = next((c for c in candidates if os.path.isdir(c)), None)
    if found:
        report.add("espeak_ng_data", PASS, found)
    else:
        report.add(
            "espeak_ng_data", WARN,
            "not found in common locations -- required for local TTS (voice.tts); "
            "set AURA_TTS_ESPEAK_DATA if installed elsewhere",
        )


def check_voice_models(report: Report) -> None:
    import os

    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "src"))
        from aura_core.voice import load_voice_model_paths

        paths = load_voice_model_paths()
        missing = [
            name for name, value in vars(paths).items()
            if name != "tts_espeak_data_dir" and not os.path.exists(value)
        ]
        if not missing:
            report.add("voice_models", PASS, "all wake-word/STT/TTS model files present")
        else:
            report.add("voice_models", WARN, f"missing: {', '.join(missing)} -- see core/RUNBOOK.md to download them")
    except ImportError:
        report.add("voice_models", WARN, "aura_core is not importable yet (venv not set up) -- skipping model check")


def run_all() -> Report:
    report = Report()
    check_python_version(report)
    check_pip(report)
    check_dotnet_sdk(report)
    check_ollama_reachable(report)
    check_disk_space(report)
    check_write_permission(report)
    check_espeak_ng_data(report)
    check_voice_models(report)
    return report


def main() -> int:
    report = run_all()
    if "--json" in sys.argv:
        print(json.dumps([r.__dict__ for r in report.results], indent=2))
    else:
        for r in report.results:
            print(f"[{r.status:4s}] {r.name:20s} {r.detail}")
        fails = sum(1 for r in report.results if r.status == FAIL)
        warns = sum(1 for r in report.results if r.status == WARN)
        print(f"\n{len(report.results)} checks: {fails} FAIL, {warns} WARN")
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
